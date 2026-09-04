from __future__ import annotations

import uuid
from pathlib import Path

from PySide6.QtCore import QMimeData, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pdfmod.app.settings import AppSettings
from pdfmod.domain.document_context import ToolLaunchContext
from pdfmod.domain.jobs import JobRequest, JobResult, OperationType
from pdfmod.ui.components import (
    DangerButton,
    GhostButton,
    GuidedActionCue,
    PdfInputPanel,
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


class PdfDropList(QListWidget):
    files_dropped = Signal(list)

    def __init__(self) -> None:
        super().__init__()
        self.setAcceptDrops(True)
        self.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.setAlternatingRowColors(True)
        self.setMinimumHeight(260)
        self.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)

    def dragEnterEvent(self, event) -> None:  # noqa: ANN001
        if self._has_pdf_urls(event.mimeData()):
            event.acceptProposedAction()
            return
        event.ignore()

    def dragMoveEvent(self, event) -> None:  # noqa: ANN001
        if self._has_pdf_urls(event.mimeData()):
            event.acceptProposedAction()
            return
        event.ignore()

    def dropEvent(self, event) -> None:  # noqa: ANN001
        if not event.mimeData().hasUrls():
            super().dropEvent(event)
            return
        paths = [Path(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile()]
        pdfs = [path for path in paths if path.suffix.lower() == ".pdf"]
        if pdfs:
            self.files_dropped.emit(pdfs)
            event.acceptProposedAction()
            return
        event.ignore()

    def _has_pdf_urls(self, mime_data: QMimeData) -> bool:
        return any(
            url.isLocalFile() and Path(url.toLocalFile()).suffix.lower() == ".pdf"
            for url in mime_data.urls()
        )


class MergePdfPage(QWidget):
    back_requested = Signal()
    workspace_files_added = Signal(list)
    output_pdf_requested = Signal(object)
    job_completed = Signal(object)

    def __init__(self, locale: Locale = "en", settings: AppSettings | None = None) -> None:
        super().__init__()
        self._spec = TOOL_SPECS_BY_KEY["merge"]
        self._locale = locale
        self._settings = settings or AppSettings()
        self._output_path: Path | None = None
        self._last_success_output_path: Path | None = None
        self._required_step_button: QWidget | None = None
        self._launch_context: ToolLaunchContext | None = None
        self._job_runner = QtJobRunner(self)
        self._job_runner.finished.connect(self._merge_finished)
        self._guided_action_cue = GuidedActionCue(
            reduce_motion=self._settings.reduce_motion(),
        )

        self._file_list = PdfDropList()
        self._file_list.files_dropped.connect(self._handle_files)
        self._input_panel = PdfInputPanel(multiple=True, locale=locale)
        self._input_panel.paths_selected.connect(self._handle_files)

        self._output_label = QLabel(tr("output.none_file", locale))
        self._output_label.setObjectName("HelpText")
        self._output_label.setWordWrap(True)
        self._status_label = QLabel("")
        self._status_label.setObjectName("StatusText")
        self._status_label.setWordWrap(True)
        self._required_step_label = QLabel("")
        self._required_step_label.setObjectName("StatusText")
        self._required_step_label.setWordWrap(True)
        self._progress_overlay = ProgressOverlay()

        self._back_button = GhostButton()
        self._back_button.clicked.connect(self.back_requested.emit)

        self._remove_button = DangerButton()
        self._remove_button.clicked.connect(self._remove_selected)

        self._up_button = SecondaryButton()
        self._up_button.clicked.connect(self._move_selected_up)

        self._down_button = SecondaryButton()
        self._down_button.clicked.connect(self._move_selected_down)

        self._output_button = SecondaryButton()
        self._output_button.clicked.connect(self._choose_output)

        self._merge_button = PrimaryButton()
        self._merge_button.clicked.connect(self._start_merge)
        self._merge_button.setEnabled(False)

        self._view_output_button = PrimaryButton()
        self._view_output_button.clicked.connect(self._view_merged_pdf)
        self._view_output_button.setVisible(False)
        for button in (self._output_button, self._merge_button, self._view_output_button):
            _set_required_step(button, False)

        self._description_label = QLabel()
        self._description_label.setObjectName("HelpText")
        self._description_label.setWordWrap(True)

        page_toolbar = QHBoxLayout()
        page_toolbar.addWidget(self._back_button)
        page_toolbar.addStretch(1)

        file_toolbar = QHBoxLayout()
        file_toolbar.addStretch(1)
        file_toolbar.addWidget(self._remove_button)
        file_toolbar.addWidget(self._up_button)
        file_toolbar.addWidget(self._down_button)

        output_row = QHBoxLayout()
        output_row.addWidget(self._output_label, 1)
        output_row.addWidget(self._output_button)

        file_panel = SurfacePanel(role="primary")
        file_panel_layout = QVBoxLayout(file_panel)
        file_panel_layout.setContentsMargins(16, 16, 16, 16)
        file_panel_layout.setSpacing(10)
        file_panel_layout.addLayout(file_toolbar)
        file_panel_layout.addWidget(self._file_list)
        file_panel_layout.addLayout(output_row)
        file_panel_layout.addWidget(self._required_step_label)
        file_panel_layout.addWidget(self._merge_button)
        file_panel_layout.addWidget(self._view_output_button)
        file_panel_layout.addWidget(self._progress_overlay)
        file_panel_layout.addWidget(self._status_label)
        self._file_panel = file_panel

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)
        layout.addWidget(self._description_label)
        layout.addLayout(page_toolbar)
        layout.addWidget(self._input_panel)
        layout.addWidget(file_panel)
        layout.addStretch(1)
        self.set_locale(locale)
        self._update_action_state()

    def _handle_files(self, paths: list[Path]) -> None:
        self._add_files(paths)
        self.workspace_files_added.emit(paths)

    def _add_files(self, paths: list[Path]) -> None:
        existing = {self._file_list.item(i).data(0x0100) for i in range(self._file_list.count())}
        added = False
        for path in paths:
            normalized = _path_key(path)
            if normalized in existing:
                continue
            item = QListWidgetItem(path.name)
            item.setToolTip(str(path))
            item.setData(0x0100, normalized)
            self._file_list.addItem(item)
            existing.add(normalized)
            added = True
        if added:
            self._clear_success_output()
        self._update_action_state()

    def _remove_selected(self) -> None:
        row = self._file_list.currentRow()
        if row >= 0:
            self._file_list.takeItem(row)
            self._clear_success_output()
        self._update_action_state()

    def _move_selected_up(self) -> None:
        self._move_selected(-1)

    def _move_selected_down(self) -> None:
        self._move_selected(1)

    def _move_selected(self, offset: int) -> None:
        row = self._file_list.currentRow()
        target = row + offset
        if row < 0 or target < 0 or target >= self._file_list.count():
            return
        item = self._file_list.takeItem(row)
        self._file_list.insertItem(target, item)
        self._file_list.setCurrentRow(target)
        self._clear_success_output()

    def _choose_output(self) -> None:
        file_name, _ = QFileDialog.getSaveFileName(
            self,
            tr("merge.dialog.output_title", self._locale),
            self._default_output_file_name(),
            "PDF (*.pdf)",
        )
        if file_name:
            output_path = Path(file_name)
            if output_path.suffix.lower() != ".pdf":
                output_path = output_path.with_suffix(".pdf")
            self._output_path = output_path
            self._output_label.setText(str(output_path))
            self._output_label.setToolTip(str(output_path))
            self._clear_success_output()
        self._update_action_state()

    def _start_merge(self) -> None:
        if self._job_runner.is_running():
            return
        input_files = [
            Path(self._file_list.item(i).data(0x0100)) for i in range(self._file_list.count())
        ]
        if len(input_files) < 2:
            self._show_error(tr("merge.error.no_files", self._locale))
            return
        if self._output_path is None:
            self._show_error(tr("merge.error.no_output", self._locale))
            return

        job = JobRequest(
            operation=OperationType.MERGE_PDFS,
            input_files=tuple(input_files),
            output_dir=self._output_path.parent,
            options={"output_path": self._output_path},
            naming_strategy="explicit",
            job_id=str(uuid.uuid4()),
        )

        self._set_required_step_button(None)
        self._merge_button.setEnabled(False)
        self._clear_success_output()
        self._status_label.setText(tr("merge.status.running", self._locale))
        self._progress_overlay.show_message(tr("merge.status.running", self._locale))
        self._job_runner.start(job)

    def _merge_finished(self, result: JobResult) -> None:
        self._progress_overlay.hide_overlay()

        self._status_label.setText(result.user_message)
        if result.success:
            self._set_success_output(result)
            self._update_action_state()
            self._open_output_folder_if_requested(result)
            show_info(self, tr("merge.success.title", self._locale), result.user_message)
            self.job_completed.emit(result)
            return
        self._clear_success_output()
        self._update_action_state()
        self.job_completed.emit(result)
        self._show_error(result.user_message, result.technical_detail)

    def _show_error(self, message: str, detail: str = "") -> None:
        self._progress_overlay.hide_overlay()
        show_error(self, tr("merge.error.title", self._locale), message, detail)

    def _update_action_state(self) -> None:
        has_files = self._file_list.count() > 0
        self._input_panel.set_loaded(has_files)
        self._file_panel.setVisible(has_files)
        has_enough_files = self._file_list.count() >= 2
        has_output = self._output_path is not None
        has_success_output = self._last_success_output_path is not None
        is_running = self._job_runner.is_running()
        ready = has_enough_files and has_output
        self._merge_button.setEnabled(ready and not is_running)
        required_button: QWidget | None = None
        if has_success_output and not is_running:
            required_button = self._view_output_button
        elif ready and not is_running:
            required_button = self._merge_button
        elif has_enough_files and not has_output and not is_running:
            required_button = self._output_button
        self._set_required_step_button(required_button)
        self._required_step_label.setVisible(has_files and not is_running)
        if not has_files or is_running:
            self._required_step_label.setText("")
        elif not has_enough_files:
            self._required_step_label.setText(tr("merge.required.files", self._locale))
        elif has_success_output:
            self._required_step_label.setText(tr("guidance.next.view_result", self._locale))
        elif not has_output:
            self._required_step_label.setText(tr("guidance.next.choose_output", self._locale))
        else:
            self._required_step_label.setText(
                tr(
                    "guidance.next.execute",
                    self._locale,
                    action=tr("button.merge", self._locale).lower(),
                )
            )

    def _set_success_output(self, result: JobResult) -> None:
        output_path = result.output_files[0] if len(result.output_files) == 1 else None
        if output_path is not None and output_path.suffix.lower() == ".pdf":
            self._last_success_output_path = output_path
            self._view_output_button.setVisible(True)
            return
        self._clear_success_output()

    def _clear_success_output(self) -> None:
        self._last_success_output_path = None
        self._view_output_button.setVisible(False)
        if self._required_step_button is self._view_output_button:
            self._set_required_step_button(None)

    def _view_merged_pdf(self) -> None:
        if self._last_success_output_path is not None:
            self.output_pdf_requested.emit(self._last_success_output_path)

    def _set_required_step_button(self, button: QWidget | None) -> None:
        if self._required_step_button is button:
            return
        if self._required_step_button is not None:
            _set_required_step(self._required_step_button, False)
        self._required_step_button = button
        if button is None:
            self._guided_action_cue.clear()
            return
        _set_required_step(button, True)
        self._guided_action_cue.set_reduce_motion(self._settings.reduce_motion())
        self._guided_action_cue.set_target(button)

    def _default_output_file_name(self) -> str:
        if (
            self._launch_context is not None
            and self._launch_context.suggested_output_dir is not None
            and self._launch_context.suggested_output_basename
        ):
            return str(
                self._launch_context.suggested_output_dir
                / self._launch_context.suggested_output_basename
            )
        output_dir = self._settings.default_output_dir()
        if output_dir is None:
            return "fusion.pdf"
        return str(output_dir / "fusion.pdf")

    def _open_output_folder_if_requested(self, result: JobResult) -> None:
        if self._settings.after_job_behavior() != "open_output_folder" or not result.output_files:
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(result.output_files[0].parent)))

    def set_workspace_documents(self, documents: tuple[WorkspaceDocument, ...]) -> None:
        if self._job_runner.is_running():
            return
        self._file_list.clear()
        self._add_files([document.path for document in documents])

    def set_tool_launch_context(self, context: ToolLaunchContext | None) -> None:
        self._launch_context = context
        if context is None or self._job_runner.is_running():
            return
        self._file_list.clear()
        self._add_files(list(context.input_files))

    def set_locale(self, locale: Locale) -> None:
        self._locale = locale
        self._description_label.setText(tr(self._spec.description_key, locale))
        self._back_button.setText(tr("button.back", locale))
        self._back_button.setToolTip(tr("button.back", locale))
        self._remove_button.setText(tr("button.remove", locale))
        self._remove_button.setToolTip(tr("button.remove", locale))
        self._up_button.setText(tr("button.up", locale))
        self._up_button.setToolTip(tr("button.up", locale))
        self._down_button.setText(tr("button.down", locale))
        self._down_button.setToolTip(tr("button.down", locale))
        self._output_button.setText(tr("button.choose_output", locale))
        self._output_button.setToolTip(tr("button.choose_output", locale))
        self._merge_button.setText(tr("button.merge", locale))
        self._merge_button.setToolTip(tr("button.merge", locale))
        self._view_output_button.setText(tr("button.view_merged_pdf", locale))
        self._view_output_button.setToolTip(tr("button.view_merged_pdf", locale))
        self._input_panel.set_locale(locale)
        if self._output_path is None:
            self._output_label.setText(tr("output.none_file", locale))
        self._update_action_state()

    def busy_document_paths(self) -> tuple[Path, ...]:
        if not self._job_runner.is_running():
            return ()
        return tuple(
            Path(self._file_list.item(index).data(0x0100))
            for index in range(self._file_list.count())
        )


def _path_key(path: Path) -> str:
    return str(path.resolve(strict=False))


def _set_required_step(button: QWidget, required: bool) -> None:
    if button.property("requiredStep") == required:
        return
    button.setProperty("requiredStep", required)
    button.style().unpolish(button)
    button.style().polish(button)
