from __future__ import annotations

import uuid
from pathlib import Path

from PySide6.QtCore import QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from pdfmod.app.settings import AppSettings
from pdfmod.domain.document_context import ToolLaunchContext
from pdfmod.domain.jobs import JobRequest, JobResult, OperationType
from pdfmod.domain.page_ranges import (
    parse_page_order,
    parse_page_range_groups,
    parse_page_ranges,
    validate_page_assembly,
    validate_page_numbers,
    validate_page_ranges,
)
from pdfmod.ui.components import (
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
from pdfmod.ui.tool_specs import ToolSpec, tool_spec_for_operation
from pdfmod.ui.workspace_state import WorkspaceDocument
from pdfmod.workers.job_runner import PageCountResult, QtJobRunner, QtPageCountRunner


class PageOperationPage(QWidget):
    back_requested = Signal()
    workspace_files_added = Signal(list)
    page_count_ready = Signal(object, int)
    page_count_failed = Signal(object)
    job_completed = Signal(object)

    def __init__(
        self,
        operation: OperationType,
        locale: Locale = "en",
        settings: AppSettings | None = None,
    ) -> None:
        super().__init__()
        self._operation = operation
        self._spec: ToolSpec = tool_spec_for_operation(operation)
        self._locale = locale
        self._settings = settings or AppSettings()
        self._input_path: Path | None = None
        self._page_count: int | None = None
        self._queued_page_count_path: Path | None = None
        self._output_path: Path | None = None
        self._output_dir: Path | None = None
        self._launch_context: ToolLaunchContext | None = None
        self._guidance_completed = False
        self._job_runner = QtJobRunner(self)
        self._page_count_runner = QtPageCountRunner(self)
        self._job_runner.finished.connect(self._operation_finished)
        self._page_count_runner.finished.connect(self._page_count_finished)
        self._syncing_visual_selection = False
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

        self._thumbnail_grid = PdfPageThumbnailGrid(
            mode=self._thumbnail_mode(),
            layout_mode=self._thumbnail_layout_mode(),
            locale=locale,
        )
        self._thumbnail_grid.selection_changed.connect(self._thumbnail_selection_changed)
        self._thumbnail_grid.order_changed.connect(self._thumbnail_order_changed)
        self._thumbnail_grid.split_ranges_changed.connect(self._thumbnail_split_ranges_changed)
        self._thumbnail_grid.setVisible(False)

        self._input_label = QLabel(tr("input.none_pdf", locale))
        self._input_label.setObjectName("HelpText")
        self._input_label.setWordWrap(True)
        self._page_count_label = QLabel(tr("page_count.empty", locale))
        self._page_count_label.setObjectName("HelpText")

        self._ranges_label = QLabel()
        self._ranges_label.setObjectName("SectionTitle")
        self._ranges_input = QLineEdit()
        self._ranges_input.setPlaceholderText(self._ranges_placeholder())
        self._ranges_input.textChanged.connect(self._plan_changed)
        self._advanced_button = SecondaryButton()
        self._advanced_button.clicked.connect(self._toggle_advanced)
        self._advanced_button.setVisible(self._spec.input_mode == "complete_order")
        if self._spec.input_mode == "complete_order":
            self._ranges_label.setVisible(False)
            self._ranges_input.setVisible(False)

        self._help_label = QLabel()
        self._help_label.setObjectName("HelpText")
        self._help_label.setWordWrap(True)
        self._help_label.setVisible(bool(self._help_text()))
        if self._spec.input_mode == "complete_order":
            self._help_label.setVisible(False)

        self._angle_input = QComboBox()
        self._angle_input.addItem("90", 90)
        self._angle_input.addItem("180", 180)
        self._angle_input.addItem("270", 270)
        self._angle_input.currentIndexChanged.connect(self._update_action_state)
        self._angle_input.setVisible(self._spec.requires_rotation_angle)
        self._angle_label = QLabel()
        self._angle_label.setObjectName("SectionTitle")
        self._angle_label.setVisible(self._spec.requires_rotation_angle)

        self._move_page_up_button = SecondaryButton()
        self._move_page_up_button.clicked.connect(lambda: self._move_selected_thumbnail(-1))
        self._move_page_down_button = SecondaryButton()
        self._move_page_down_button.clicked.connect(lambda: self._move_selected_thumbnail(1))
        self._duplicate_page_button = SecondaryButton()
        self._duplicate_page_button.clicked.connect(self._duplicate_selected_thumbnail)
        self._move_page_up_button.setVisible(self._spec.input_mode == "complete_order")
        self._move_page_down_button.setVisible(self._spec.input_mode == "complete_order")
        self._duplicate_page_button.setVisible(self._spec.input_mode == "complete_order")

        self._output_label = QLabel(self._empty_output_text())
        self._output_label.setObjectName("HelpText")
        self._output_label.setWordWrap(True)

        self._output_button = SecondaryButton()
        self._output_button.clicked.connect(self._choose_output)

        self._action_button = PrimaryButton()
        self._action_button.clicked.connect(self._start_operation)
        self._action_button.setEnabled(False)
        self._required_step_label = QLabel()
        self._required_step_label.setObjectName("StatusText")
        self._required_step_label.setWordWrap(True)
        self._required_step_label.setVisible(False)

        self._status_label = QLabel("")
        self._status_label.setObjectName("StatusText")
        self._status_label.setWordWrap(True)
        self._progress_overlay = ProgressOverlay()

        toolbar = QHBoxLayout()
        toolbar.addWidget(self._back_button)
        toolbar.addStretch(1)

        output_row = QHBoxLayout()
        output_row.addWidget(self._output_label, 1)
        output_row.addWidget(self._output_button)

        angle_row = QHBoxLayout()
        angle_row.addWidget(self._angle_label)
        angle_row.addWidget(self._angle_input)
        angle_row.addStretch(1)

        reorder_buttons_row = QHBoxLayout()
        reorder_buttons_row.addWidget(self._duplicate_page_button)
        reorder_buttons_row.addWidget(self._move_page_up_button)
        reorder_buttons_row.addWidget(self._move_page_down_button)
        reorder_buttons_row.addStretch(1)

        form_panel = SurfacePanel(role="primary")
        form_panel_layout = QVBoxLayout(form_panel)
        form_panel_layout.setContentsMargins(18, 18, 18, 18)
        form_panel_layout.setSpacing(12)
        form_panel_layout.addWidget(self._input_label)
        form_panel_layout.addWidget(self._page_count_label)
        form_panel_layout.addWidget(self._advanced_button)
        form_panel_layout.addWidget(self._ranges_label)
        form_panel_layout.addWidget(self._ranges_input)
        form_panel_layout.addWidget(self._help_label)
        form_panel_layout.addLayout(angle_row)
        form_panel_layout.addLayout(reorder_buttons_row)
        form_panel_layout.addLayout(output_row)
        form_panel_layout.addWidget(self._required_step_label)
        form_panel_layout.addWidget(self._action_button)
        form_panel_layout.addWidget(self._progress_overlay)
        form_panel_layout.addWidget(self._status_label)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 30, 32, 30)
        layout.setSpacing(16)
        layout.addWidget(self._description_label)
        layout.addLayout(toolbar)
        layout.addWidget(self._input_panel)
        layout.addWidget(self._thumbnail_grid, 1)
        layout.addWidget(form_panel)
        layout.addStretch(1)
        self.set_locale(locale)

    def _handle_files(self, paths: list[Path]) -> None:
        if not paths:
            return
        self._set_input_path(paths[0])
        self.workspace_files_added.emit(paths)

    def _set_input_path(self, path: Path) -> None:
        self._guidance_completed = False
        self._input_path = path
        self._page_count = None
        self._thumbnail_grid.clear_document()
        self._thumbnail_grid.setVisible(False)
        self._ranges_input.clear()
        self._input_label.setText(str(path))
        self._input_label.setToolTip(str(path))
        self._page_count_label.setText(tr("page_count.loading", self._locale))
        self._status_label.setText("")
        self._input_panel.set_loaded(True)
        self._update_action_state()
        if self._page_count_runner.is_running():
            self._queued_page_count_path = path
            return
        self._page_count_runner.start(path)

    def _clear_input_path(self) -> None:
        self._guidance_completed = False
        self._input_path = None
        self._page_count = None
        self._queued_page_count_path = None
        self._input_label.setText(tr("input.none_pdf", self._locale))
        self._input_label.setToolTip("")
        self._page_count_label.setText(tr("page_count.empty", self._locale))
        self._status_label.setText("")
        self._input_panel.set_loaded(False)
        self._thumbnail_grid.clear_document()
        self._thumbnail_grid.setVisible(False)
        self._update_action_state()

    def _page_count_finished(self, result: PageCountResult) -> None:
        queued_path = self._queued_page_count_path
        self._queued_page_count_path = None
        if result.success:
            self.page_count_ready.emit(result.pdf_path, result.page_count)
        else:
            self.page_count_failed.emit(result.pdf_path)

        if self._input_path == result.pdf_path:
            if result.success:
                self._page_count = result.page_count
                self._page_count_label.setText(
                    tr("page_count.value", self._locale, count=result.page_count)
                )
                self._status_label.setText(result.user_message)
                self._thumbnail_grid.set_document(result.pdf_path, result.page_count)
                self._thumbnail_grid.setVisible(True)
                self._input_panel.set_loaded(True)
            else:
                self._page_count = None
                self._page_count_label.setText(tr("page_count.empty", self._locale))
                self._status_label.setText(result.user_message)
                self._thumbnail_grid.setVisible(False)
                self._input_panel.set_loaded(False)

        if queued_path is not None and queued_path != result.pdf_path:
            self._page_count_runner.start(queued_path)
            self._update_action_state()
            return
        if self._input_path != result.pdf_path:
            self._page_count = None
        self._update_action_state()

    def _choose_output(self) -> None:
        if self._spec.output_mode == "directory":
            directory = QFileDialog.getExistingDirectory(
                self,
                "Choisir le dossier de sortie",
                self._default_output_directory(),
            )
            if directory:
                self._guidance_completed = False
                self._output_dir = Path(directory)
                self._output_label.setText(str(self._output_dir))
                self._output_label.setToolTip(str(self._output_dir))
        else:
            file_name, _ = QFileDialog.getSaveFileName(
                self,
                "Choisir le fichier de sortie",
                self._default_output_path_text(),
                "PDF (*.pdf)",
            )
            if file_name:
                self._guidance_completed = False
                output_path = Path(file_name)
                if output_path.suffix.lower() != ".pdf":
                    output_path = output_path.with_suffix(".pdf")
                self._output_path = output_path
                self._output_label.setText(str(output_path))
                self._output_label.setToolTip(str(output_path))
        self._update_action_state()

    def _start_operation(self) -> None:
        if self._job_runner.is_running():
            return
        try:
            job = self._build_job()
        except ValueError as exc:
            self._show_error(str(exc))
            return

        self._set_guided_step(None)
        self._action_button.setEnabled(False)
        self._status_label.setText(self._progress_message())
        self._progress_overlay.show_message(self._progress_message())
        self._job_runner.start(job)

    def _operation_finished(self, result: JobResult) -> None:
        self._guidance_completed = result.success
        self._update_action_state()
        self._progress_overlay.hide_overlay()
        self._status_label.setText(self._result_message(result))
        if result.success:
            self._open_output_folder_if_requested(result)
            show_info(self, self._success_title(), self._result_message(result))
            self.job_completed.emit(result)
            return
        self.job_completed.emit(result)
        self._show_error(result.user_message, result.technical_detail)

    def _build_job(self) -> JobRequest:
        if self._input_path is None or self._page_count is None:
            raise ValueError("Choisis un PDF valide avant de lancer l'operation.")

        options: dict[str, object]
        output_dir: Path
        if self._spec.output_mode == "directory":
            if self._output_dir is None:
                raise ValueError("Choisis un dossier de sortie.")
            output_dir = self._output_dir
        else:
            if self._output_path is None:
                raise ValueError("Choisis un fichier de sortie.")
            output_dir = self._output_path.parent

        if self._spec.input_mode == "range_groups":
            page_ranges = parse_page_range_groups(self._ranges_input.text())
            validate_page_ranges(page_ranges, self._page_count)
            options = {"ranges": page_ranges}
        elif self._spec.input_mode == "complete_order":
            page_order = tuple(parse_page_order(self._ranges_input.text()))
            validate_page_assembly(page_order, self._page_count)
            options = {"page_order": page_order, "output_path": self._output_path}
        else:
            page_numbers = tuple(parse_page_ranges(self._ranges_input.text()))
            validate_page_numbers(page_numbers, self._page_count)
            options = {"page_numbers": page_numbers, "output_path": self._output_path}
            if self._spec.requires_rotation_angle:
                options["angle"] = int(self._angle_input.currentData())

        return JobRequest(
            operation=self._operation,
            input_files=(self._input_path,),
            output_dir=output_dir,
            options=options,
            naming_strategy="explicit",
            job_id=str(uuid.uuid4()),
        )

    def _update_action_state(self) -> None:
        plan_ready = (
            self._input_path is not None
            and self._page_count is not None
            and self._has_valid_ranges()
            and not self._job_runner.is_running()
            and not self._page_count_runner.is_running()
        )
        ready = plan_ready and self._has_output()
        self._action_button.setEnabled(ready)
        self._duplicate_page_button.setEnabled(
            self._spec.input_mode == "complete_order"
            and self._page_count is not None
            and not self._job_runner.is_running()
            and not self._page_count_runner.is_running()
        )
        guided_button: QWidget | None = None
        if (
            self._spec.input_mode == "complete_order"
            and plan_ready
            and not self._guidance_completed
        ):
            guided_button = self._action_button if self._has_output() else self._output_button
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

    def _plan_changed(self, _text: str) -> None:
        self._guidance_completed = False
        self._update_action_state()

    def _has_valid_ranges(self) -> bool:
        if self._page_count is None:
            return False
        try:
            if self._spec.input_mode == "range_groups":
                validate_page_ranges(
                    parse_page_range_groups(self._ranges_input.text()), self._page_count
                )
            elif self._spec.input_mode == "complete_order":
                validate_page_assembly(
                    parse_page_order(self._ranges_input.text()), self._page_count
                )
            else:
                validate_page_numbers(
                    parse_page_ranges(self._ranges_input.text()), self._page_count
                )
        except ValueError:
            return False
        return True

    def _has_output(self) -> bool:
        if self._spec.output_mode == "directory":
            return self._output_dir is not None
        return self._output_path is not None

    def _empty_output_text(self) -> str:
        return tr(self._spec.output_label_key, self._locale)

    def _default_output_name(self) -> str:
        if self._launch_context is not None and self._launch_context.suggested_output_basename:
            return self._launch_context.suggested_output_basename
        stem = self._input_path.stem if self._input_path is not None else "document"
        suffix = self._spec.default_output_suffix
        return f"{stem}{suffix}.pdf"

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

    def _default_output_directory(self) -> str:
        output_dir = self._settings.default_output_dir()
        return str(output_dir) if output_dir is not None else ""

    def _success_title(self) -> str:
        return self._spec.success_title

    def _progress_message(self) -> str:
        return self._spec.progress_message

    def _ranges_placeholder(self) -> str:
        return self._spec.page_range_placeholder

    def _help_text(self) -> str:
        if not self._spec.help_key:
            return ""
        return tr(self._spec.help_key, self._locale)

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

    def set_workspace_document(self, document: WorkspaceDocument | None) -> None:
        if document is None:
            self._clear_input_path()
            return
        if self._input_path != document.path:
            self._set_input_path(document.path)

    def set_tool_launch_context(self, context: ToolLaunchContext | None) -> None:
        self._launch_context = context
        if context is None or not context.input_files:
            return
        if self._input_path != context.input_files[0]:
            self._set_input_path(context.input_files[0])

    def set_locale(self, locale: Locale) -> None:
        self._locale = locale
        self._description_label.setText(tr(self._spec.description_key, locale))
        self._back_button.setText(tr("button.back", locale))
        self._advanced_button.setText(tr("visual.advanced_mode", locale))
        self._ranges_label.setText(self._ranges_label_key_text().upper())
        self._help_label.setText(self._help_key_text())
        self._help_label.setVisible(self._ranges_input.isVisible() and bool(self._help_key_text()))
        self._angle_label.setText(tr("label.rotation_angle", locale))
        self._move_page_up_button.setText(tr("button.up", locale))
        self._move_page_down_button.setText(tr("button.down", locale))
        self._duplicate_page_button.setText(tr("button.duplicate_pages", locale))
        self._output_button.setText(self._output_button_key_text().upper())
        self._action_button.setText(self._action_button_key_text().upper())
        self._input_panel.set_locale(locale)
        self._thumbnail_grid.set_locale(locale)
        if self._input_path is None:
            self._input_label.setText(tr("input.none_pdf", locale))
        if self._page_count is None:
            self._page_count_label.setText(tr("page_count.empty", locale))
        if self._output_path is None and self._output_dir is None:
            self._output_label.setText(self._empty_output_text())
        self._update_action_state()

    def busy_document_paths(self) -> tuple[Path, ...]:
        if not self._job_runner.is_running() or self._input_path is None:
            return ()
        return (self._input_path,)

    def _title_key_text(self) -> str:
        return tr(self._spec.title_key, self._locale)

    def _ranges_label_key_text(self) -> str:
        return tr(self._spec.ranges_label_key, self._locale)

    def _help_key_text(self) -> str:
        if not self._spec.help_key:
            return ""
        return tr(self._spec.help_key, self._locale)

    def _output_button_key_text(self) -> str:
        return tr(self._spec.output_button_key, self._locale)

    def _action_button_key_text(self) -> str:
        return tr(self._spec.action_button_key, self._locale)

    def _thumbnail_mode(self) -> str:
        if self._spec.input_mode == "range_groups":
            return "split"
        if self._spec.input_mode == "complete_order":
            return "ordered"
        return "selection"

    def _thumbnail_layout_mode(self) -> str:
        if self._spec.input_mode == "complete_order":
            return "grid_reorder"
        return "horizontal_strip"

    def _thumbnail_selection_changed(self, pages: tuple[int, ...]) -> None:
        if self._syncing_visual_selection or not pages:
            return
        if self._spec.input_mode not in {"ranges"}:
            return
        self._syncing_visual_selection = True
        self._ranges_input.setText(self._thumbnail_grid.range_expression())
        self._syncing_visual_selection = False

    def _thumbnail_order_changed(self, page_order: tuple[int, ...]) -> None:
        if self._syncing_visual_selection or self._spec.input_mode != "complete_order":
            return
        self._syncing_visual_selection = True
        self._ranges_input.setText(",".join(str(page) for page in page_order))
        self._syncing_visual_selection = False

    def _thumbnail_split_ranges_changed(self, page_ranges: tuple) -> None:
        if self._syncing_visual_selection or self._spec.input_mode != "range_groups":
            return
        if not page_ranges:
            return
        self._syncing_visual_selection = True
        self._ranges_input.setText(",".join(page_range.label for page_range in page_ranges))
        self._syncing_visual_selection = False

    def _duplicate_selected_thumbnail(self) -> None:
        if self._spec.input_mode != "complete_order":
            return
        self._thumbnail_grid.duplicate_selected()
        self._update_action_state()

    def _move_selected_thumbnail(self, offset: int) -> None:
        if self._spec.input_mode != "complete_order":
            return
        self._thumbnail_grid.move_selected(offset)

    def _toggle_advanced(self) -> None:
        visible = not self._ranges_input.isVisible()
        self._ranges_label.setVisible(visible)
        self._ranges_input.setVisible(visible)
        self._help_label.setVisible(visible and bool(self._help_key_text()))
