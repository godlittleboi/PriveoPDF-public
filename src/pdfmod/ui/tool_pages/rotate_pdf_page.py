from __future__ import annotations

import uuid
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QImage, QPainter, QPixmap
from PySide6.QtPdf import QPdfDocument, QPdfDocumentRenderOptions, QPdfPageRenderer
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from pdfmod.app.settings import AppSettings
from pdfmod.domain.document_context import ToolLaunchContext
from pdfmod.domain.jobs import JobRequest, JobResult, OperationType
from pdfmod.ui.components import (
    ElidedLabel,
    GhostButton,
    GuidedActionCue,
    PdfInputPanel,
    PdfPageThumbnailGrid,
    PrimaryButton,
    ProgressOverlay,
    SecondaryButton,
    SurfacePanel,
    show_error,
    show_info,
)
from pdfmod.ui.i18n import Locale, tr
from pdfmod.ui.tool_specs import TOOL_SPECS_BY_KEY
from pdfmod.ui.workspace_state import WorkspaceDocument
from pdfmod.workers.job_runner import QtJobRunner

ROTATION_ANGLES = (0, 90, 180, 270)


class RotatePdfPage(QWidget):
    back_requested = Signal()
    workspace_files_added = Signal(list)
    page_count_ready = Signal(object, int)
    page_count_failed = Signal(object)
    job_completed = Signal(object)

    def __init__(self, locale: Locale = "en", settings: AppSettings | None = None) -> None:
        super().__init__()
        self._locale = locale
        self._settings = settings or AppSettings()
        self._spec = TOOL_SPECS_BY_KEY["rotate"]
        self._input_path: Path | None = None
        self._page_count: int | None = None
        self._active_page = 1
        self._selected_pages: tuple[int, ...] = ()
        self._output_path: Path | None = None
        self._launch_context: ToolLaunchContext | None = None
        self._preview_generation = 0
        self._preview_requests: dict[int, int] = {}
        self._preview_rotation_enabled = False
        self._last_valid_angle = 0
        self._guidance_completed = False

        self._document = QPdfDocument(self)
        self._renderer = QPdfPageRenderer(self)
        self._renderer.setDocument(self._document)
        self._renderer.pageRendered.connect(self._preview_rendered)
        self._job_runner = QtJobRunner(self)
        self._job_runner.finished.connect(self._rotation_finished)
        self._guided_action_cue = GuidedActionCue(
            reduce_motion=self._settings.reduce_motion(),
        )

        self._description_label = QLabel()
        self._description_label.setObjectName("HelpText")
        self._description_label.setWordWrap(True)

        self._back_button = GhostButton()
        self._back_button.clicked.connect(self.back_requested.emit)

        self._input_panel = PdfInputPanel(multiple=False, locale=locale)
        self._input_panel.paths_selected.connect(self._handle_files)

        self._preview_label = QLabel()
        self._preview_label.setObjectName("PdfPreviewCanvas")
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setMinimumHeight(360)

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
        self._angle_combo = QComboBox()
        self._angle_combo.setObjectName("RotationAngleCombo")
        self._angle_combo.setFixedWidth(96)
        for angle in ROTATION_ANGLES:
            self._angle_combo.addItem(f"{angle}°", angle)
        self._angle_combo.currentIndexChanged.connect(self._angle_index_changed)

        self._target_label = QLabel()
        self._target_label.setObjectName("SectionTitle")
        self._target_combo = QComboBox()
        self._target_combo.currentIndexChanged.connect(self._rotation_options_changed)

        self._output_title_label = QLabel()
        self._output_title_label.setObjectName("SectionTitle")
        self._output_label = ElidedLabel()
        self._output_label.setObjectName("OutputFileName")
        self._output_path_label = ElidedLabel()
        self._output_path_label.setObjectName("HelpText")
        self._output_path_label.setVisible(False)
        self._output_button = SecondaryButton()
        self._output_button.clicked.connect(self._choose_output)

        self._action_button = PrimaryButton()
        self._action_button.clicked.connect(self._start_rotation)
        self._action_button.setEnabled(False)
        self._required_step_label = QLabel()
        self._required_step_label.setObjectName("StatusText")
        self._required_step_label.setWordWrap(True)
        self._required_step_label.setVisible(False)

        self._status_label = QLabel()
        self._status_label.setObjectName("StatusText")
        self._status_label.setWordWrap(True)
        self._status_title_label = QLabel()
        self._status_title_label.setObjectName("SectionTitle")
        self._progress_overlay = ProgressOverlay()

        toolbar = QHBoxLayout()
        toolbar.addWidget(self._back_button)
        toolbar.addStretch(1)
        toolbar.addWidget(self._angle_label)
        toolbar.addWidget(self._angle_combo)
        toolbar.addWidget(self._rotate_left_button)
        toolbar.addWidget(self._rotate_right_button)
        toolbar.addWidget(self._target_label)
        toolbar.addWidget(self._target_combo)
        toolbar.addWidget(self._output_button)
        toolbar.addWidget(self._action_button)

        viewer_panel = SurfacePanel(role="primary")
        viewer_layout = QVBoxLayout(viewer_panel)
        viewer_layout.setContentsMargins(18, 18, 18, 18)
        viewer_layout.setSpacing(12)
        viewer_layout.addWidget(self._preview_label, 1)
        viewer_layout.addWidget(self._thumbnail_grid)

        self._output_panel = SurfacePanel(role="primary")
        form_layout = QVBoxLayout(self._output_panel)
        form_layout.setContentsMargins(18, 18, 18, 18)
        form_layout.setSpacing(8)
        form_layout.addWidget(self._output_title_label)
        form_layout.addWidget(self._output_label)
        form_layout.addWidget(self._output_path_label)
        form_layout.addWidget(self._required_step_label)
        form_layout.addSpacing(4)
        form_layout.addWidget(self._status_title_label)
        form_layout.addWidget(self._progress_overlay)
        form_layout.addWidget(self._status_label)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 30, 32, 30)
        layout.setSpacing(16)
        layout.addWidget(self._description_label)
        layout.addLayout(toolbar)
        layout.addWidget(self._input_panel)
        layout.addWidget(viewer_panel, 1)
        layout.addWidget(self._output_panel)
        self.set_locale(locale)
        self._clear_document()

    def set_locale(self, locale: Locale) -> None:
        self._locale = locale
        self._description_label.setText(tr(self._spec.description_key, locale))
        self._back_button.setText(tr("button.back", locale))
        self._rotate_left_button.setText(tr("button.rotate_left", locale))
        self._rotate_right_button.setText(tr("button.rotate_right", locale))
        self._angle_label.setText(tr("label.rotation_angle_short", locale))
        self._target_label.setText(tr("label.rotation_target_short", locale))
        self._output_title_label.setText(tr("output.panel.title", locale))
        self._status_title_label.setText(tr("output.panel.status_title", locale))
        self._output_button.setText(tr("button.choose_output", locale))
        self._action_button.setText(tr(self._spec.action_button_key, locale))
        self._input_panel.set_locale(locale)
        self._thumbnail_grid.set_locale(locale)
        self._target_combo.blockSignals(True)
        current_target = self._target_combo.currentData()
        self._target_combo.clear()
        self._target_combo.addItem(tr("rotation.target.active", locale), "active")
        self._target_combo.addItem(tr("rotation.target.selected", locale), "selected")
        self._target_combo.addItem(tr("rotation.target.all", locale), "all")
        if isinstance(current_target, str):
            for index in range(self._target_combo.count()):
                if self._target_combo.itemData(index) == current_target:
                    self._target_combo.setCurrentIndex(index)
                    break
        self._target_combo.blockSignals(False)
        self._refresh_output_destination()
        if self._input_path is None:
            self._status_label.setText(tr("viewer.no_pdf", locale))
        self._update_action_state()

    def busy_document_paths(self) -> tuple[Path, ...]:
        if not self._job_runner.is_running() or self._input_path is None:
            return ()
        return (self._input_path,)

    def set_workspace_document(self, document: WorkspaceDocument | None) -> None:
        if document is None:
            self._clear_document()
            return
        if self._input_path != document.path:
            self.load_document(document.path)

    def set_tool_launch_context(self, context: ToolLaunchContext | None) -> None:
        self._launch_context = context
        if context is None or not context.input_files:
            return
        if self._input_path != context.input_files[0]:
            self.load_document(context.input_files[0])

    def load_document(self, path: Path) -> None:
        self._guidance_completed = False
        self._input_path = path
        self._page_count = None
        self._active_page = 1
        self._selected_pages = ()
        self._set_angle(0, preview_enabled=False)
        self._preview_generation += 1
        self._preview_requests.clear()
        self._thumbnail_grid.clear_document()
        self._thumbnail_grid.setVisible(False)
        self._document.close()
        error = self._document.load(str(path))
        if error != QPdfDocument.Error.None_:
            self.page_count_failed.emit(path)
            self._status_label.setText(tr("viewer.load_error", self._locale))
            self._input_panel.set_loaded(False)
            self._thumbnail_grid.clear_document()
            self._thumbnail_grid.setVisible(False)
            self._preview_label.setText(tr("rotation.preview_unavailable", self._locale))
            self._update_action_state()
            return

        self._page_count = self._document.pageCount()
        self.page_count_ready.emit(path, self._page_count)
        self._input_panel.set_loaded(True)
        self._thumbnail_grid.set_document(path, self._page_count)
        self._thumbnail_grid.setVisible(True)
        self._status_label.setText(tr("viewer.loaded", self._locale, name=path.name))
        self._render_preview()
        self._update_action_state()

    def _handle_files(self, paths: list[Path]) -> None:
        if not paths:
            return
        self.load_document(paths[0])
        self.workspace_files_added.emit(paths)

    def _clear_document(self) -> None:
        self._guidance_completed = False
        self._input_path = None
        self._page_count = None
        self._active_page = 1
        self._selected_pages = ()
        self._set_angle(0, preview_enabled=False)
        self._preview_generation += 1
        self._preview_requests.clear()
        self._document.close()
        self._input_panel.set_loaded(False)
        self._thumbnail_grid.clear_document()
        self._thumbnail_grid.setVisible(False)
        self._preview_label.setText(tr("viewer.no_pdf", self._locale))
        self._status_label.setText(tr("viewer.no_pdf", self._locale))
        self._update_action_state()

    def _rotate_right(self) -> None:
        self._set_angle((self._current_or_last_angle() + 90) % 360)

    def _rotate_left(self) -> None:
        self._set_angle((self._current_or_last_angle() - 90) % 360)

    def _set_angle(self, angle: int, *, preview_enabled: bool = True) -> None:
        self._last_valid_angle = angle
        self._preview_rotation_enabled = preview_enabled
        self._angle_combo.blockSignals(True)
        index = self._angle_combo.findData(angle)
        if index >= 0:
            self._angle_combo.setCurrentIndex(index)
        self._angle_combo.blockSignals(False)
        self._rotation_options_changed()

    def _angle_index_changed(self, _index: int) -> None:
        angle = self._angle()
        if angle is None:
            self._set_angle(self._last_valid_angle)
            return
        self._last_valid_angle = angle
        self._preview_rotation_enabled = True
        self._set_angle(angle)

    def _rotation_options_changed(self) -> None:
        self._guidance_completed = False
        self._render_preview()
        self._update_action_state()

    def _thumbnail_selection_changed(self, pages: tuple[int, ...]) -> None:
        self._selected_pages = pages
        self._rotation_options_changed()

    def _active_page_changed(self, page_number: int) -> None:
        self._active_page = page_number
        self._render_preview()
        self._update_action_state()

    def _choose_output(self) -> None:
        file_name, _ = QFileDialog.getSaveFileName(
            self,
            tr("button.choose_output", self._locale),
            self._default_output_path_text(),
            "PDF (*.pdf)",
        )
        if file_name:
            self._guidance_completed = False
            output_path = Path(file_name)
            if output_path.suffix.lower() != ".pdf":
                output_path = output_path.with_suffix(".pdf")
            self._output_path = output_path
            self._refresh_output_destination()
        self._update_action_state()

    def _refresh_output_destination(self) -> None:
        accessible_name = tr("output.panel.destination", self._locale)
        self._output_label.setAccessibleName(accessible_name)
        self._output_path_label.setAccessibleName(accessible_name)
        if self._output_path is None:
            empty_text = tr("output.none_file", self._locale)
            self._output_label.setText(empty_text)
            self._output_label.setToolTip("")
            self._output_label.setAccessibleDescription(empty_text)
            self._output_path_label.setText("")
            self._output_path_label.setToolTip("")
            self._output_path_label.setAccessibleDescription("")
            self._output_path_label.setVisible(False)
            return

        full_path = str(self._output_path)
        self._output_label.setText(self._output_path.name)
        self._output_label.setToolTip(full_path)
        self._output_label.setAccessibleDescription(full_path)
        self._output_path_label.setText(str(self._output_path.parent))
        self._output_path_label.setToolTip(full_path)
        self._output_path_label.setAccessibleDescription(full_path)
        self._output_path_label.setVisible(True)

    def _start_rotation(self) -> None:
        if self._job_runner.is_running():
            return
        try:
            job = self._build_job()
        except ValueError as exc:
            self._show_error(str(exc))
            return
        self._set_guided_step(None)
        self._action_button.setEnabled(False)
        self._status_label.setText(self._spec.progress_message)
        self._progress_overlay.show_message(self._spec.progress_message)
        self._job_runner.start(job)

    def _build_job(self) -> JobRequest:
        if self._input_path is None or self._page_count is None:
            raise ValueError(tr("rotation.error.no_pdf", self._locale))
        if self._output_path is None:
            raise ValueError(tr("rotation.error.no_output", self._locale))
        angle = self._angle()
        if angle is None:
            raise ValueError(tr("rotation.error.invalid_angle", self._locale))
        pages = self._target_pages()
        if not pages:
            raise ValueError(tr("rotation.error.no_pages", self._locale))
        return JobRequest(
            operation=OperationType.ROTATE_PAGES,
            input_files=(self._input_path,),
            output_dir=self._output_path.parent,
            options={"page_numbers": pages, "output_path": self._output_path, "angle": angle},
            naming_strategy="explicit",
            job_id=str(uuid.uuid4()),
        )

    def _rotation_finished(self, result: JobResult) -> None:
        self._guidance_completed = result.success
        self._update_action_state()
        self._progress_overlay.hide_overlay()
        self._status_label.setText(self._result_message(result))
        if result.success:
            self._open_output_folder_if_requested(result)
            show_info(self, self._spec.success_title, self._result_message(result))
            self.job_completed.emit(result)
            return
        self.job_completed.emit(result)
        self._show_error(result.user_message, result.technical_detail)

    def _render_preview(self) -> None:
        if (
            self._input_path is None
            or self._page_count is None
            or self._document.status() != QPdfDocument.Status.Ready
        ):
            return
        self._preview_generation += 1
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
        angle = self._angle_combo.currentData()
        return angle if isinstance(angle, int) and angle in ROTATION_ANGLES else None

    def _current_or_last_angle(self) -> int:
        angle = self._angle()
        return self._last_valid_angle if angle is None else angle

    def _update_action_state(self) -> None:
        angle_valid = self._angle() is not None
        target_pages = self._target_pages()
        if self._input_path is not None and not angle_valid:
            self._status_label.setText(tr("rotation.error.invalid_angle", self._locale))
        elif self._input_path is not None and self._page_count is not None:
            self._status_label.setText(
                tr("viewer.loaded", self._locale, name=self._input_path.name)
            )
        plan_ready = (
            self._input_path is not None
            and self._page_count is not None
            and angle_valid
            and bool(target_pages)
            and not self._job_runner.is_running()
        )
        ready = plan_ready and self._output_path is not None
        self._action_button.setEnabled(ready)
        guided_button: QWidget | None = None
        if plan_ready and not self._guidance_completed:
            guided_button = (
                self._action_button if self._output_path is not None else self._output_button
            )
        self._set_guided_step(guided_button)

    def _set_guided_step(self, button: QWidget | None) -> None:
        self._guided_action_cue.set_reduce_motion(self._settings.reduce_motion())
        self._guided_action_cue.set_target(button)
        self._required_step_label.setVisible(button is not None)
        if button is None:
            self._required_step_label.setText("")
            return
        if button is self._output_button:
            text = tr("guidance.next.choose_output", self._locale)
        else:
            text = tr(
                "guidance.next.execute",
                self._locale,
                action=tr(self._spec.action_button_key, self._locale).lower(),
            )
        self._required_step_label.setText(text)

    def _default_output_name(self) -> str:
        if self._launch_context is not None and self._launch_context.suggested_output_basename:
            return self._launch_context.suggested_output_basename
        stem = self._input_path.stem if self._input_path is not None else "document"
        return f"{stem}{self._spec.default_output_suffix}.pdf"

    def _default_output_path_text(self) -> str:
        if (
            self._launch_context is not None
            and self._launch_context.suggested_output_dir is not None
        ):
            return str(self._launch_context.suggested_output_dir / self._default_output_name())
        output_dir = self._settings.default_output_dir()
        if output_dir is None:
            return self._default_output_name()
        return str(output_dir / self._default_output_name())

    def _result_message(self, result: JobResult) -> str:
        if not result.output_files:
            return result.user_message
        files = "\n".join(str(path) for path in result.output_files)
        return f"{result.user_message}\n\nFichier(s) genere(s) :\n{files}"

    def _show_error(self, message: str, detail: str = "") -> None:
        self._progress_overlay.hide_overlay()
        show_error(self, "Operation impossible", message, detail)

    def _open_output_folder_if_requested(self, result: JobResult) -> None:
        if self._settings.after_job_behavior() != "open_output_folder" or not result.output_files:
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(result.output_files[0].parent)))


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
