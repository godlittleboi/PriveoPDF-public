from __future__ import annotations

import uuid
from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QImage, QPainter, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from priveopdf.app.settings import AppSettings
from priveopdf.domain.document_context import ToolLaunchContext
from priveopdf.domain.jobs import JobRequest, JobResult, OperationType
from priveopdf.ui.components import (
    GhostButton,
    OutputTargetField,
    PdfInputPanel,
    PdfPageThumbnailGrid,
    SecondaryButton,
    SourceCheck,
    SurfacePanel,
    ToolActionBar,
    expected_output_pages,
    install_page_tool_layout,
    job_result_message,
    open_output_folder_if_requested,
    output_suffix,
    proposed_output_directory,
)
from priveopdf.ui.components.tool_flow import page_count_text
from priveopdf.ui.i18n import Locale, tr
from priveopdf.ui.theme.tokens import SPACING
from priveopdf.ui.tool_pages.viewer_tool_page import RenderedSourceMixin
from priveopdf.ui.tool_specs import TOOL_SPECS_BY_KEY
from priveopdf.workers.job_runner import QtJobRunner
from priveopdf.workers.render_client import RemotePageRenderer as QPdfPageRenderer
from priveopdf.workers.render_client import RemotePdfDocument as QPdfDocument
from priveopdf.workers.render_client import RemoteRenderOptions as QPdfDocumentRenderOptions

ROTATION_ANGLES = (0, 90, 180, 270)
# Smallest preview that keeps the page strip visible below it at 1366 x 768.
PREVIEW_MIN_HEIGHT = 160


class RotatePdfPage(RenderedSourceMixin, QWidget):
    back_requested = Signal()
    workspace_files_added = Signal(list)
    page_count_ready = Signal(object, int)
    page_count_failed = Signal(object, str)
    job_completed = Signal(object)
    output_pdf_requested = Signal(object)

    def __init__(self, locale: Locale = "en", settings: AppSettings | None = None) -> None:
        super().__init__()
        self._locale = locale
        self._settings = settings or AppSettings()
        self._spec = TOOL_SPECS_BY_KEY["rotate"]
        self._input_path: Path | None = None
        self._page_count: int | None = None
        self._active_page = 1
        self._selected_pages: tuple[int, ...] = ()
        self._load_error = ""
        self._launch_context: ToolLaunchContext | None = None
        self._preview_generation = 0
        self._preview_requests: dict[int, int] = {}
        self._preview_rotation_enabled = False
        self._last_valid_angle = 0

        self._document = QPdfDocument(self)
        self._document.loaded.connect(self._document_loaded)
        self._renderer = QPdfPageRenderer(self)
        self._renderer.setDocument(self._document)
        self._renderer.pageRendered.connect(self._preview_rendered)
        self._job_runner = QtJobRunner(self)
        self._job_runner.finished.connect(self._rotation_finished)

        self._description_label = QLabel()
        self._description_label.setObjectName("HelpText")
        self._description_label.setWordWrap(True)

        self._back_button = GhostButton()
        self._back_button.clicked.connect(self.back_requested.emit)

        self._input_panel = PdfInputPanel(multiple=False, locale=locale)
        self._input_panel.paths_selected.connect(self._handle_files)
        # L4: a protected or damaged source is reported under it.
        self._source_check = SourceCheck(locale)
        self._source_check.changed.connect(self._source_check_changed)
        # E2: the page names the file it will act on, with its page count.
        self._input_status = QLabel()
        self._input_status.setObjectName("HelpText")
        self._input_status.setWordWrap(True)

        self._preview_label = QLabel()
        self._preview_label.setObjectName("PdfPreviewCanvas")
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Ignored: the rendered pixmap must follow the label size, never enlarge it.
        self._preview_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self._preview_label.setMinimumHeight(PREVIEW_MIN_HEIGHT)

        self._thumbnail_grid = PdfPageThumbnailGrid(
            mode="selection",
            layout_mode="horizontal_strip",
            locale=locale,
        )
        self._thumbnail_grid.selection_changed.connect(self._thumbnail_selection_changed)
        self._thumbnail_grid.active_page_changed.connect(self._active_page_changed)
        self._thumbnail_grid.setVisible(False)

        self._rotate_left_button = SecondaryButton()
        self._rotate_left_button.clicked.connect(self._rotate_left)
        self._rotate_right_button = SecondaryButton()
        self._rotate_right_button.clicked.connect(self._rotate_right)

        self._angle_label = QLabel()
        self._angle_label.setObjectName("SectionTitle")
        # L5 / E6: the angle is set by the two buttons only and shown here.
        self._angle_value = QLabel("0°")
        self._angle_value.setObjectName("RotationAngleValue")

        self._target_label = QLabel()
        self._target_label.setObjectName("SectionTitle")
        self._target_combo = QComboBox()
        self._target_combo.currentIndexChanged.connect(self._rotation_options_changed)

        self._output = OutputTargetField("file", locale)
        self._output.changed.connect(self._output_changed)
        self._action_bar = ToolActionBar(locale)
        self._action_bar.set_action_text_key(self._spec.action_button_key)
        self._action_bar.action_requested.connect(self._start_rotation)
        self._action_bar.cancel_requested.connect(self._job_runner.cancel)
        self._action_bar.open_pdf_requested.connect(self.output_pdf_requested.emit)
        self._action_button = self._action_bar.action_button()

        # Rule 1, page-editing adaptation: source on the left; settings, output,
        # action and result stacked in that order in the right column.
        viewer_panel = SurfacePanel(role="primary")
        viewer_layout = QVBoxLayout(viewer_panel)
        viewer_layout.setContentsMargins(*(SPACING["lg"],) * 4)
        viewer_layout.setSpacing(SPACING["md"])
        viewer_layout.addWidget(self._preview_label, 1)
        viewer_layout.addWidget(self._thumbnail_grid)

        self._settings_panel = SurfacePanel(role="primary")
        settings_layout = QGridLayout(self._settings_panel)
        settings_layout.setContentsMargins(*(SPACING["lg"],) * 4)
        settings_layout.setHorizontalSpacing(SPACING["md"])
        settings_layout.setVerticalSpacing(SPACING["sm"])
        settings_layout.setColumnStretch(1, 1)
        settings_layout.addWidget(self._angle_label, 0, 0)
        settings_layout.addWidget(self._angle_value, 0, 1)
        settings_layout.addWidget(self._rotate_left_button, 1, 0, 1, 2)
        settings_layout.addWidget(self._rotate_right_button, 2, 0, 1, 2)
        settings_layout.addWidget(self._target_label, 3, 0)
        settings_layout.addWidget(self._target_combo, 3, 1)

        self._output_panel = SurfacePanel(role="primary")
        form_layout = QVBoxLayout(self._output_panel)
        form_layout.setContentsMargins(*(SPACING["lg"],) * 4)
        form_layout.setSpacing(SPACING["sm"])
        form_layout.addWidget(self._output)
        form_layout.addWidget(self._action_bar)

        install_page_tool_layout(
            self,
            back=self._back_button,
            header=(
                self._description_label,
                self._input_panel,
                self._input_status,
                self._source_check,
            ),
            pages=viewer_panel,
            side_panels=(self._settings_panel, self._output_panel),
        )
        self.set_locale(locale)
        self._clear_document()

    def set_locale(self, locale: Locale) -> None:
        self._locale = locale
        if self._input_path is not None and self._page_count is not None:
            self._input_status.setText(
                tr(
                    "blank.ready",
                    locale,
                    name=self._input_path.name,
                    pages=page_count_text(self._page_count, locale),
                )
            )
        self._description_label.setText(tr(self._spec.description_key, locale))
        self._back_button.setText(tr("button.back", locale))
        self._rotate_left_button.setText(tr("button.rotate_left", locale))
        self._rotate_right_button.setText(tr("button.rotate_right", locale))
        self._rotate_left_button.setAccessibleName(tr("rotation.accessible.left", locale))
        self._rotate_right_button.setAccessibleName(tr("rotation.accessible.right", locale))
        self._angle_label.setText(tr("label.rotation_angle_short", locale))
        self._angle_value.setAccessibleName(tr("label.rotation_angle", locale))
        self._target_label.setText(tr("label.rotation_target_short", locale))
        self._input_panel.set_locale(locale)
        self._source_check.set_locale(locale)
        self._output.set_locale(locale)
        self._action_bar.set_locale(locale)
        self._propose_output()
        self._thumbnail_grid.set_locale(locale)
        self._target_combo.blockSignals(True)
        current_target = self._target_combo.currentData()
        self._target_combo.clear()
        # L5: "All pages" is the default target, first in the list.
        self._target_combo.addItem(tr("rotation.target.all", locale), "all")
        self._target_combo.addItem(tr("rotation.target.selected", locale), "selected")
        self._target_combo.addItem(tr("rotation.target.active", locale), "active")
        if isinstance(current_target, str):
            for index in range(self._target_combo.count()):
                if self._target_combo.itemData(index) == current_target:
                    self._target_combo.setCurrentIndex(index)
                    break
        self._target_combo.blockSignals(False)
        self._update_action_state()

    def load_document(self, path: Path) -> None:
        self._input_path = path
        self._page_count = None
        self._active_page = 1
        self._selected_pages = ()
        self._set_angle(0, preview_enabled=False)
        self._preview_generation += 1
        self._renderer.cancel_pending()
        self._preview_requests.clear()
        self._thumbnail_grid.clear_document()
        self._thumbnail_grid.setVisible(False)
        self._document.close()
        self._load_error = ""
        self._action_bar.clear_result()
        self._output.clear()
        self._propose_output()
        self._source_check.check([path])
        self._input_status.setText(tr("blank.loading", self._locale, name=path.name))
        # L7 / E10 (B35): the preview says what is happening while it loads.
        self._preview_label.setText(tr("rotation.preview_loading", self._locale))
        self._document.load(str(path))
        self._update_action_state()

    def _document_loaded(self, error) -> None:
        path = self._input_path
        if path is None:
            return
        if error != QPdfDocument.Error.None_:
            self._record_load_failure(path, error)
            self._thumbnail_grid.clear_document()
            self._thumbnail_grid.setVisible(False)
            self._preview_label.setText(tr("rotation.preview_unavailable", self._locale))
            self._update_action_state()
            return

        self._page_count = self._document.pageCount()
        self.page_count_ready.emit(path, self._page_count)
        self._input_panel.set_loaded(True)
        self._input_status.setText(
            tr(
                "blank.ready",
                self._locale,
                name=path.name,
                pages=page_count_text(self._page_count, self._locale),
            )
        )
        self._thumbnail_grid.set_document(path, self._page_count)
        self._thumbnail_grid.setVisible(True)
        self._render_preview()
        self._update_action_state()

    def _handle_files(self, paths: list[Path]) -> None:
        if not paths:
            return
        self.load_document(paths[0])
        self.workspace_files_added.emit(paths)

    def _clear_document(self) -> None:
        self._input_path = None
        self._page_count = None
        self._active_page = 1
        self._selected_pages = ()
        self._set_angle(0, preview_enabled=False)
        self._preview_generation += 1
        self._renderer.cancel_pending()
        self._preview_requests.clear()
        self._document.close()
        self._input_panel.set_loaded(False)
        self._input_status.setText("")
        self._source_check.clear()
        self._thumbnail_grid.clear_document()
        self._thumbnail_grid.setVisible(False)
        self._preview_label.setText(tr("viewer.no_pdf", self._locale))
        self._load_error = ""
        self._action_bar.clear_result()
        self._output.clear()
        self._update_action_state()

    def _rotate_right(self) -> None:
        self._set_angle((self._current_or_last_angle() + 90) % 360)

    def _rotate_left(self) -> None:
        self._set_angle((self._current_or_last_angle() - 90) % 360)

    def _set_angle(self, angle: int, *, preview_enabled: bool = True) -> None:
        if angle not in ROTATION_ANGLES:
            return
        self._last_valid_angle = angle
        self._preview_rotation_enabled = preview_enabled
        self._angle_value.setText(f"{angle}°")
        self._rotation_options_changed()

    def _rotation_options_changed(self) -> None:
        # Rule 8: a change of angle, target or selection after a success clears
        # the displayed result.
        self._action_bar.clear_result()
        self._render_preview()
        self._update_action_state()

    def _thumbnail_selection_changed(self, pages: tuple[int, ...]) -> None:
        self._selected_pages = pages
        self._rotation_options_changed()

    def _active_page_changed(self, page_number: int) -> None:
        if page_number != self._active_page:
            self._action_bar.clear_result()  # rule 8: « Page active » changed
        self._active_page = page_number
        self._render_preview()
        self._update_action_state()

    def _propose_output(self) -> None:
        source = self._input_path
        if source is not None:
            directory = proposed_output_directory(source, self._settings)
            self._output.propose(directory, source.stem, output_suffix("rotate", self._locale))

    def _output_changed(self) -> None:
        self._action_bar.clear_result()
        self._update_action_state()

    def _start_rotation(self) -> None:
        if self._job_runner.is_running() or self._blocker():
            return
        try:
            job = self._build_job()
        except ValueError as exc:
            self._action_bar.show_error(str(exc))
            return
        self._action_bar.set_running(
            tr("job.running", self._locale),
            expected_pages=expected_output_pages(job, self._page_count),
        )
        self._job_runner.start(job)
        self._update_action_state()

    def _build_job(self) -> JobRequest:
        if self._input_path is None or self._page_count is None:
            raise ValueError(tr("rotation.error.no_pdf", self._locale))
        output_path = self._output.path()
        if output_path is None:
            raise ValueError(tr("rotation.error.no_output", self._locale))
        angle = self._angle()
        if angle is None:
            raise ValueError(tr("rotation.error.invalid_angle", self._locale))
        if angle == 0:
            raise ValueError(tr("rotation.required.angle", self._locale))
        pages = self._target_pages()
        if not pages:
            raise ValueError(tr("rotation.error.no_pages", self._locale))
        return JobRequest(
            operation=OperationType.ROTATE_PAGES,
            input_files=(self._input_path,),
            output_dir=output_path.parent,
            options={"page_numbers": pages, "output_path": output_path, "angle": angle},
            naming_strategy="explicit",
            job_id=str(uuid.uuid4()),
        )

    def _rotation_finished(self, result: JobResult) -> None:
        if result.success:
            # Next free name first: a destination change clears the displayed result.
            self._output.refresh()
        self._action_bar.finish(result, job_result_message(result, self._locale, "rotate"))
        self._update_action_state()
        if result.success:
            open_output_folder_if_requested(self._settings, result)
        self.job_completed.emit(result)

    def _render_preview(self) -> None:
        if (
            self._input_path is None
            or self._page_count is None
            or self._document.status() != QPdfDocument.Status.Ready
        ):
            return
        self._preview_generation += 1
        self._renderer.cancel_pending()
        self._preview_requests.clear()
        page_index = max(0, min(self._page_count - 1, self._active_page - 1))
        point_size = self._document.pagePointSize(page_index)
        width = max(1.0, point_size.width())
        height = max(1.0, point_size.height())
        preview_angle = self._preview_angle_for_active_page()
        effective_width = height if preview_angle in {90, 270} else width
        effective_height = width if preview_angle in {90, 270} else height
        bounds = QSize(
            max(240, self._preview_label.width() - 24),
            max(320, self._preview_label.height() - 24),
        )
        scale = min(bounds.width() / effective_width, bounds.height() / effective_height)
        render_size = QSize(
            max(1, int(effective_width * scale)),
            max(1, int(effective_height * scale)),
        )
        options = QPdfDocumentRenderOptions()
        options.setScaledSize(render_size)
        if preview_angle in {90, 180, 270}:
            options.setRotation(_rotation_option(preview_angle))
        request_id = int(self._renderer.requestPage(page_index, render_size, options))
        self._preview_requests[request_id] = self._preview_generation

    def _preview_rendered(
        self,
        page_number: int,
        size: QSize,
        image: QImage,
        options: QPdfDocumentRenderOptions,
        request_id: int,
    ) -> None:
        del page_number, size, options
        generation = self._preview_requests.pop(int(request_id), None)
        if generation != self._preview_generation:
            return
        if image.isNull():
            self._preview_label.setText(tr("rotation.preview_unavailable", self._locale))
            return
        self._preview_label.setPixmap(QPixmap.fromImage(_compose_on_paper(image)))

    def _preview_angle_for_active_page(self) -> int | None:
        if not self._preview_rotation_enabled:
            return None
        angle = self._angle()
        if angle is None:
            return None
        target = self._target_combo.currentData()
        if target == "all":
            return angle
        if target == "active":
            return angle
        if target == "selected" and self._active_page in self._selected_pages:
            return angle
        return None

    def _target_pages(self) -> tuple[int, ...]:
        if self._page_count is None:
            return ()
        target = self._target_combo.currentData()
        if target == "all":
            return tuple(range(1, self._page_count + 1))
        if target == "active":
            return (self._active_page,)
        if target == "selected":
            return self._selected_pages
        return ()

    def _angle(self) -> int | None:
        angle = self._last_valid_angle
        return angle if angle in ROTATION_ANGLES else None

    def _current_or_last_angle(self) -> int:
        return self._last_valid_angle

    def _source_check_changed(self) -> None:
        # The check may end after the preview failed: its message replaces the
        # generic loading error.
        if self._load_error and self._source_check.problem():
            self._action_bar.clear_result()
            self._input_panel.set_loaded(True)
        self._update_action_state()

    def _blocker(self) -> str:
        if self._input_path is None:
            return tr("tool.required.source", self._locale)
        problem = self._source_check.blocker_text()
        if problem:
            return problem
        if self._load_error:
            return tr("tool.required.valid_source", self._locale)
        if self._page_count is None:
            return tr("viewer.loading", self._locale)
        if self._angle() is None:
            return tr("rotation.error.invalid_angle", self._locale)
        if self._angle() == 0:
            # 0° would only copy the document (B18).
            return tr("rotation.required.angle", self._locale)
        if not self._target_pages():
            return tr("rotation.error.no_pages", self._locale)
        if self._output.path() is None:
            return tr("tool.required.output", self._locale)
        return ""

    def _update_action_state(self) -> None:
        running = self._job_runner.is_running()
        self._output.setEnabled(not running)
        self._input_panel.setEnabled(not running)
        # Settings are frozen while the job runs: the result shown at the end
        # always matches the settings that produced it.
        self._settings_panel.setEnabled(not running)
        self._thumbnail_grid.setEnabled(not running)
        blocker = self._blocker()
        self._action_bar.set_blocker(blocker)


def _rotation_option(angle: int) -> QPdfDocumentRenderOptions.Rotation:
    if angle == 90:
        return QPdfDocumentRenderOptions.Rotation.Clockwise90
    if angle == 180:
        return QPdfDocumentRenderOptions.Rotation.Clockwise180
    return QPdfDocumentRenderOptions.Rotation.Clockwise270


def _compose_on_paper(image: QImage) -> QImage:
    composed = QImage(image.size(), QImage.Format.Format_ARGB32_Premultiplied)
    composed.fill(Qt.GlobalColor.white)
    painter = QPainter(composed)
    painter.drawImage(0, 0, image)
    painter.end()
    return composed
