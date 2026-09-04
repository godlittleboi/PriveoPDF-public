from __future__ import annotations

import uuid
from pathlib import Path

from PySide6.QtCore import QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from pdfmod.app.settings import AppSettings
from pdfmod.domain.document_context import ToolLaunchContext
from pdfmod.domain.jobs import JobRequest, JobResult, OperationType
from pdfmod.ui.components import (
    GhostButton,
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
from pdfmod.ui.theme.tokens import SPACING
from pdfmod.ui.workspace_state import WorkspaceDocument
from pdfmod.workers.job_runner import PageCountResult, QtJobRunner, QtPageCountRunner


class InsertPdfPagesPage(QWidget):
    back_requested = Signal()
    workspace_files_added = Signal(list, bool)
    page_count_ready = Signal(object, int)
    page_count_failed = Signal(object)
    job_completed = Signal(object)

    def __init__(
        self,
        locale: Locale = "en",
        settings: AppSettings | None = None,
    ) -> None:
        super().__init__()
        self._locale = locale
        self._settings = settings or AppSettings()
        self._primary_path: Path | None = None
        self._inserted_path: Path | None = None
        self._primary_page_count: int | None = None
        self._inserted_page_count: int | None = None
        self._queued_primary_path: Path | None = None
        self._queued_inserted_path: Path | None = None
        self._output_path: Path | None = None
        self._launch_context: ToolLaunchContext | None = None
        self._workspace_documents: tuple[WorkspaceDocument, ...] = ()

        self._job_runner = QtJobRunner(self)
        self._primary_count_runner = QtPageCountRunner(self)
        self._inserted_count_runner = QtPageCountRunner(self)
        self._job_runner.finished.connect(self._operation_finished)
        self._primary_count_runner.finished.connect(self._primary_count_finished)
        self._inserted_count_runner.finished.connect(self._inserted_count_finished)

        self._description_label = QLabel()
        self._description_label.setObjectName("HelpText")
        self._description_label.setWordWrap(True)

        self._back_button = GhostButton()
        self._back_button.clicked.connect(self.back_requested.emit)

        self._primary_title = QLabel()
        self._primary_title.setObjectName("SectionTitle")
        self._primary_input = PdfInputPanel(multiple=False, locale=locale)
        self._primary_input.paths_selected.connect(self._handle_primary_files)
        self._primary_status = QLabel()
        self._primary_status.setObjectName("HelpText")
        self._primary_status.setWordWrap(True)
        self._primary_grid = PdfPageThumbnailGrid(
            mode="preview_only",
            layout_mode="horizontal_strip",
            locale=locale,
        )
        self._primary_grid.setVisible(False)

        self._inserted_title = QLabel()
        self._inserted_title.setObjectName("SectionTitle")
        self._inserted_input = PdfInputPanel(multiple=False, locale=locale)
        self._inserted_input.paths_selected.connect(self._handle_inserted_files)
        self._inserted_status = QLabel()
        self._inserted_status.setObjectName("HelpText")
        self._inserted_status.setWordWrap(True)
        self._inserted_grid = PdfPageThumbnailGrid(
            mode="selection",
            layout_mode="horizontal_strip",
            locale=locale,
        )
        self._inserted_grid.selection_changed.connect(self._selection_changed)
        self._inserted_grid.setVisible(False)

        self._position_label = QLabel()
        self._position_label.setObjectName("SectionTitle")
        self._position_input = QSpinBox()
        self._position_input.valueChanged.connect(self._update_action_state)
        self._position_input.setEnabled(False)

        self._summary_label = QLabel()
        self._summary_label.setObjectName("HelpText")
        self._summary_label.setWordWrap(True)

        self._output_label = QLabel()
        self._output_label.setObjectName("HelpText")
        self._output_label.setWordWrap(True)
        self._output_button = SecondaryButton()
        self._output_button.clicked.connect(self._choose_output)

        self._action_button = PrimaryButton()
        self._action_button.clicked.connect(self._start_operation)
        self._action_button.setEnabled(False)
        self._status_label = QLabel()
        self._status_label.setObjectName("StatusText")
        self._status_label.setWordWrap(True)
        self._progress_overlay = ProgressOverlay()

        toolbar = QHBoxLayout()
        toolbar.addWidget(self._back_button)
        toolbar.addStretch(1)

        output_row = QHBoxLayout()
        output_row.addWidget(self._output_label, 1)
        output_row.addWidget(self._output_button)

        plan_panel = SurfacePanel(role="primary")
        plan_layout = QVBoxLayout(plan_panel)
        plan_layout.setContentsMargins(*(SPACING["lg"],) * 4)
        plan_layout.setSpacing(SPACING["md"])
        plan_layout.addWidget(self._position_label)
        plan_layout.addWidget(self._position_input)
        plan_layout.addWidget(self._summary_label)
        plan_layout.addLayout(output_row)
        plan_layout.addWidget(self._action_button)
        plan_layout.addWidget(self._progress_overlay)
        plan_layout.addWidget(self._status_label)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(*(SPACING["xxl"],) * 4)
        layout.setSpacing(SPACING["md"])
        layout.addWidget(self._description_label)
        layout.addLayout(toolbar)
        layout.addWidget(self._primary_title)
        layout.addWidget(self._primary_input)
        layout.addWidget(self._primary_status)
        layout.addWidget(self._primary_grid)
        layout.addWidget(self._inserted_title)
        layout.addWidget(self._inserted_input)
        layout.addWidget(self._inserted_status)
        layout.addWidget(self._inserted_grid)
        layout.addWidget(plan_panel)
        layout.addStretch(1)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll_area.setWidget(content)
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.addWidget(scroll_area)
        self.set_locale(locale)

    def _handle_primary_files(self, paths: list[Path]) -> None:
        if not paths:
            return
        self._set_primary_path(paths[0])
        self.workspace_files_added.emit(paths, True)

    def _handle_inserted_files(self, paths: list[Path]) -> None:
        if not paths:
            return
        self._set_inserted_path(paths[0])
        self.workspace_files_added.emit(paths, False)

    def _set_primary_path(self, path: Path) -> None:
        self._primary_path = path
        self._primary_page_count = None
        self._primary_grid.clear_document()
        self._primary_grid.setVisible(False)
        self._primary_input.set_loaded(True)
        self._primary_status.setText(tr("insert.document.loading", self._locale, name=path.name))
        self._primary_status.setToolTip(str(path))
        self._position_input.clear()
        self._position_input.setEnabled(False)
        self._status_label.setText("")
        if self._primary_count_runner.is_running():
            self._queued_primary_path = path
        else:
            self._primary_count_runner.start(path)
        self._update_action_state()

    def _set_inserted_path(self, path: Path) -> None:
        self._inserted_path = path
        self._inserted_page_count = None
        self._inserted_grid.clear_document()
        self._inserted_grid.setVisible(False)
        self._inserted_input.set_loaded(True)
        self._inserted_status.setText(tr("insert.document.loading", self._locale, name=path.name))
        self._inserted_status.setToolTip(str(path))
        self._status_label.setText("")
        if self._inserted_count_runner.is_running():
            self._queued_inserted_path = path
        else:
            self._inserted_count_runner.start(path)
        self._update_action_state()

    def _primary_count_finished(self, result: PageCountResult) -> None:
        self._handle_count_result(result, primary=True)

    def _inserted_count_finished(self, result: PageCountResult) -> None:
        self._handle_count_result(result, primary=False)

    def _handle_count_result(self, result: PageCountResult, *, primary: bool) -> None:
        expected = self._primary_path if primary else self._inserted_path
        queued = self._queued_primary_path if primary else self._queued_inserted_path
        if primary:
            self._queued_primary_path = None
        else:
            self._queued_inserted_path = None
        if result.success:
            self.page_count_ready.emit(result.pdf_path, result.page_count)
        else:
            self.page_count_failed.emit(result.pdf_path)
        if expected != result.pdf_path:
            if queued is not None:
                runner = self._primary_count_runner if primary else self._inserted_count_runner
                runner.start(queued)
            return

        status = self._primary_status if primary else self._inserted_status
        input_panel = self._primary_input if primary else self._inserted_input
        grid = self._primary_grid if primary else self._inserted_grid
        if not result.success:
            status.setText(result.user_message)
            input_panel.set_loaded(False)
            grid.setVisible(False)
            if primary:
                self._primary_page_count = None
            else:
                self._inserted_page_count = None
            self._update_action_state()
            if queued is not None and queued != result.pdf_path:
                runner = self._primary_count_runner if primary else self._inserted_count_runner
                runner.start(queued)
            return

        status.setText(
            tr(
                "insert.document.ready",
                self._locale,
                name=result.pdf_path.name,
                count=result.page_count,
            )
        )
        grid.set_document(result.pdf_path, result.page_count)
        grid.setVisible(True)
        if primary:
            self._primary_page_count = result.page_count
            self._populate_positions()
        else:
            self._inserted_page_count = result.page_count
        self._update_action_state()
        if queued is not None and queued != result.pdf_path:
            runner = self._primary_count_runner if primary else self._inserted_count_runner
            runner.start(queued)

    def _populate_positions(self) -> None:
        current = self._position_input.value()
        page_count = self._primary_page_count or 0
        self._position_input.blockSignals(True)
        self._position_input.setRange(0, page_count)
        self._position_input.setSpecialValueText(tr("insert.position.start", self._locale))
        self._position_input.setValue(min(current, page_count))
        self._position_input.setEnabled(self._primary_page_count is not None)
        self._position_input.blockSignals(False)

    def _selection_changed(self, _pages: tuple[int, ...]) -> None:
        self._update_action_state()

    def _choose_output(self) -> None:
        file_name, _ = QFileDialog.getSaveFileName(
            self,
            tr("insert.output.dialog", self._locale),
            self._default_output_path_text(),
            "PDF (*.pdf)",
        )
        if not file_name:
            return
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
            show_error(self, tr("error.operation.title", self._locale), str(exc))
            return
        self._action_button.setEnabled(False)
        progress = tr("insert.progress", self._locale)
        self._status_label.setText(progress)
        self._progress_overlay.show_message(progress)
        self._job_runner.start(job)

    def _build_job(self) -> JobRequest:
        if self._primary_path is None or self._primary_page_count is None:
            raise ValueError(tr("insert.error.primary", self._locale))
        if self._inserted_path is None or self._inserted_page_count is None:
            raise ValueError(tr("insert.error.source", self._locale))
        if self._primary_path.resolve(strict=False) == self._inserted_path.resolve(strict=False):
            raise ValueError(tr("insert.error.same_file", self._locale))
        pages = self._inserted_grid.selected_pages()
        if not pages:
            raise ValueError(tr("insert.error.selection", self._locale))
        insert_after_page = self._position_input.value()
        if self._output_path is None:
            raise ValueError(tr("insert.error.output", self._locale))
        return JobRequest(
            operation=OperationType.INSERT_PDF_PAGES,
            input_files=(self._primary_path, self._inserted_path),
            output_dir=self._output_path.parent,
            options={
                "page_numbers": pages,
                "insert_after_page": insert_after_page,
                "output_path": self._output_path,
            },
            naming_strategy="explicit",
            job_id=str(uuid.uuid4()),
        )

    def _operation_finished(self, result: JobResult) -> None:
        self._progress_overlay.hide_overlay()
        self._update_action_state()
        self.job_completed.emit(result)
        if not result.success:
            self._status_label.setText(result.user_message)
            show_error(
                self,
                tr("error.operation.title", self._locale),
                result.user_message,
                result.technical_detail,
            )
            return
        output_name = result.output_files[0].name
        success_message = tr("insert.success.message", self._locale, name=output_name)
        self._status_label.setText(success_message)
        if self._settings.after_job_behavior() == "open_output_folder":
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(result.output_files[0].parent)))
        show_info(self, tr("insert.success.title", self._locale), success_message)

    def _update_action_state(self) -> None:
        pages = self._inserted_grid.selected_pages()
        position = self._position_input.value()
        ready = (
            self._primary_path is not None
            and self._inserted_path is not None
            and self._primary_page_count is not None
            and self._inserted_page_count is not None
            and self._primary_path.resolve(strict=False)
            != self._inserted_path.resolve(strict=False)
            and bool(pages)
            and self._output_path is not None
            and not self._job_runner.is_running()
            and not self._primary_count_runner.is_running()
            and not self._inserted_count_runner.is_running()
        )
        self._action_button.setEnabled(ready)
        if pages and self._primary_page_count is not None:
            position_text = tr(
                "insert.summary.start" if position == 0 else "insert.summary.after",
                self._locale,
                page=position,
            )
            self._summary_label.setText(
                tr(
                    "insert.summary.ready",
                    self._locale,
                    count=len(pages),
                    pages=", ".join(str(page) for page in pages),
                    position=position_text,
                    total=self._primary_page_count + len(pages),
                )
            )
        else:
            self._summary_label.setText(tr("insert.summary.empty", self._locale))

    def _default_output_name(self) -> str:
        stem = self._primary_path.stem if self._primary_path is not None else "document"
        return f"{stem}_avec-pages.pdf"

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

    def set_workspace_document(self, document: WorkspaceDocument | None) -> None:
        if document is not None and self._primary_path != document.path:
            self._set_primary_path(document.path)
        if document is not None and self._inserted_path is None:
            secondary = next(
                (item for item in self._workspace_documents if item.path != document.path),
                None,
            )
            if secondary is not None:
                self._set_inserted_path(secondary.path)

    def set_workspace_documents(
        self,
        documents: tuple[WorkspaceDocument, ...],
    ) -> None:
        self._workspace_documents = documents

    def set_tool_launch_context(self, context: ToolLaunchContext | None) -> None:
        self._launch_context = context
        if context is None or not context.input_files:
            return
        primary_path = (
            context.active_document.source_path
            if context.active_document is not None
            else context.input_files[0]
        )
        if self._primary_path != primary_path:
            self._set_primary_path(primary_path)
        secondary_path = next((path for path in context.input_files if path != primary_path), None)
        if secondary_path is not None and self._inserted_path != secondary_path:
            self._set_inserted_path(secondary_path)

    def busy_document_paths(self) -> tuple[Path, ...]:
        if not self._job_runner.is_running():
            return ()
        return tuple(path for path in (self._primary_path, self._inserted_path) if path is not None)

    def set_locale(self, locale: Locale) -> None:
        self._locale = locale
        self._description_label.setText(tr("tool.insert_pages.subtitle", locale))
        self._back_button.setText(tr("button.back", locale))
        self._primary_title.setText(tr("insert.primary.title", locale))
        self._inserted_title.setText(tr("insert.source.title", locale))
        self._position_label.setText(tr("insert.position.title", locale))
        self._output_button.setText(tr("button.choose_output", locale))
        self._action_button.setText(tr("button.insert_pages", locale))
        self._primary_input.set_locale(locale)
        self._inserted_input.set_locale(locale)
        self._primary_grid.set_locale(locale)
        self._inserted_grid.set_locale(locale)
        if self._primary_page_count is None:
            self._primary_status.setText(tr("insert.primary.empty", locale))
        elif self._primary_path is not None:
            self._primary_status.setText(
                tr(
                    "insert.document.ready",
                    locale,
                    name=self._primary_path.name,
                    count=self._primary_page_count,
                )
            )
        if self._inserted_page_count is None:
            self._inserted_status.setText(tr("insert.source.empty", locale))
        elif self._inserted_path is not None:
            self._inserted_status.setText(
                tr(
                    "insert.document.ready",
                    locale,
                    name=self._inserted_path.name,
                    count=self._inserted_page_count,
                )
            )
        if self._output_path is None:
            self._output_label.setText(tr("output.none_file", locale))
        if self._primary_page_count is not None:
            self._populate_positions()
        self._update_action_state()
