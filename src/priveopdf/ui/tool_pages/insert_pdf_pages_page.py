from __future__ import annotations

import uuid
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSpinBox,
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
    SourceCheck,
    SurfacePanel,
    ToolActionBar,
    expected_output_pages,
    job_result_message,
    open_output_folder_if_requested,
    output_suffix,
    proposed_output_directory,
)
from priveopdf.ui.components.tool_flow import page_count_text
from priveopdf.ui.i18n import Locale, tr
from priveopdf.ui.theme.tokens import SPACING
from priveopdf.ui.workspace_state import WorkspaceDocument
from priveopdf.workers.job_runner import PageCountResult, QtJobRunner, QtPageCountRunner


class InsertPdfPagesPage(QWidget):
    back_requested = Signal()
    workspace_files_added = Signal(list, bool)
    page_count_ready = Signal(object, int)
    page_count_failed = Signal(object, str)
    job_completed = Signal(object)
    output_pdf_requested = Signal(object)

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
        # L4: each source is checked on load; the message names the file.
        self._primary_check = SourceCheck(locale, name_files=True)
        self._primary_check.changed.connect(self._update_action_state)

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
        self._inserted_check = SourceCheck(locale, name_files=True)
        self._inserted_check.changed.connect(self._update_action_state)

        self._position_label = QLabel()
        self._position_label.setObjectName("SectionTitle")
        self._position_input = QSpinBox()
        self._position_input.valueChanged.connect(self._plan_changed)
        self._position_input.setEnabled(False)

        self._summary_label = QLabel()
        self._summary_label.setObjectName("HelpText")
        self._summary_label.setWordWrap(True)

        self._output = OutputTargetField("file", locale)
        self._output.changed.connect(self._output_changed)
        self._action_bar = ToolActionBar(locale)
        self._action_bar.set_action_text_key("button.insert_pages")
        self._action_bar.action_requested.connect(self._start_operation)
        self._action_bar.cancel_requested.connect(self._job_runner.cancel)
        self._action_bar.open_pdf_requested.connect(self.output_pdf_requested.emit)
        self._action_button = self._action_bar.action_button()

        toolbar = QHBoxLayout()
        toolbar.addWidget(self._back_button)
        toolbar.addStretch(1)

        plan_panel = SurfacePanel(role="primary")
        plan_layout = QVBoxLayout(plan_panel)
        plan_layout.setContentsMargins(*(SPACING["lg"],) * 4)
        plan_layout.setSpacing(SPACING["md"])
        plan_layout.addWidget(self._position_label)
        plan_layout.addWidget(self._position_input)
        plan_layout.addWidget(self._summary_label)
        plan_layout.addWidget(self._output)
        plan_layout.addWidget(self._action_bar)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(*(SPACING["xxl"],) * 4)
        layout.setSpacing(SPACING["md"])
        layout.addLayout(toolbar)
        layout.addWidget(self._description_label)
        layout.addWidget(self._primary_title)
        layout.addWidget(self._primary_input)
        layout.addWidget(self._primary_status)
        layout.addWidget(self._primary_check)
        layout.addWidget(self._primary_grid)
        layout.addWidget(self._inserted_title)
        layout.addWidget(self._inserted_input)
        layout.addWidget(self._inserted_status)
        layout.addWidget(self._inserted_check)
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
        self._primary_check.set_sources([path])
        self._primary_status.setText(tr("insert.document.loading", self._locale, name=path.name))
        self._primary_status.setToolTip(str(path))
        self._position_input.clear()
        self._position_input.setEnabled(False)
        self._action_bar.clear_result()
        self._output.clear()
        self._propose_output()
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
        self._inserted_check.set_sources([path])
        self._inserted_status.setText(tr("insert.document.loading", self._locale, name=path.name))
        self._inserted_status.setToolTip(str(path))
        self._action_bar.clear_result()
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
            self.page_count_failed.emit(result.pdf_path, result.technical_detail)
        check = self._primary_check if primary else self._inserted_check
        check.record(result)
        if expected != result.pdf_path:
            if queued is not None:
                runner = self._primary_count_runner if primary else self._inserted_count_runner
                runner.start(queued)
            return

        status = self._primary_status if primary else self._inserted_status
        input_panel = self._primary_input if primary else self._inserted_input
        grid = self._primary_grid if primary else self._inserted_grid
        if not result.success:
            # L4: a protected or damaged PDF is reported under its source, with
            # `Change PDF` kept; other failures stay in the status line.
            reported = bool(check.problem())
            input_panel.set_loaded(reported)
            if reported:
                status.setText(result.pdf_path.name)
            else:
                code = result.technical_detail or "invalid_pdf"
                failure = JobResult(False, (), (), "-", code)
                status.setText(job_result_message(failure, self._locale))
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
                pages=page_count_text(result.page_count, self._locale),
            )
        )
        grid.set_document(result.pdf_path, result.page_count)
        grid.setVisible(True)
        if primary:
            self._primary_page_count = result.page_count
            self._populate_positions()
        else:
            self._inserted_page_count = result.page_count
            # L5: every page of the second PDF is selected on load.
            grid.select_all_pages()
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
        self._plan_changed()

    def _plan_changed(self, *_args: object) -> None:
        self._action_bar.clear_result()  # rule 8
        self._update_action_state()

    def _propose_output(self) -> None:
        source = self._primary_path
        if source is not None:
            directory = proposed_output_directory(source, self._settings)
            self._output.propose(directory, source.stem, output_suffix("insert", self._locale))

    def _output_changed(self) -> None:
        self._action_bar.clear_result()
        self._update_action_state()

    def _start_operation(self) -> None:
        if self._job_runner.is_running() or self._blocker():
            return
        try:
            job = self._build_job()
        except ValueError as exc:
            self._action_bar.show_error(str(exc))
            return
        self._action_bar.set_running(
            tr("insert.progress", self._locale),
            expected_pages=expected_output_pages(job, self._primary_page_count),
        )
        self._job_runner.start(job)
        self._update_action_state()

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
        output_path = self._output.path()
        if output_path is None:
            raise ValueError(tr("insert.error.output", self._locale))
        return JobRequest(
            operation=OperationType.INSERT_PDF_PAGES,
            input_files=(self._primary_path, self._inserted_path),
            output_dir=output_path.parent,
            options={
                "page_numbers": pages,
                "insert_after_page": insert_after_page,
                "output_path": output_path,
            },
            naming_strategy="explicit",
            job_id=str(uuid.uuid4()),
        )

    def _operation_finished(self, result: JobResult) -> None:
        if result.success:
            # Next free name first: a destination change clears the displayed result.
            self._output.refresh()
        self._action_bar.finish(result, self._result_message(result))
        self._update_action_state()
        if result.success:
            open_output_folder_if_requested(self._settings, result)
        self.job_completed.emit(result)

    def _result_message(self, result: JobResult) -> str:
        message = job_result_message(result, self._locale, "insert")
        if result.success:
            message += "\n" + tr("insert.success.message", self._locale)
        return message

    def _blocker(self) -> str:
        problem = self._primary_check.blocker_text() or self._inserted_check.blocker_text()
        if problem:
            return problem
        if self._primary_path is None or self._primary_page_count is None:
            if self._primary_count_runner.is_running():
                return tr("page_count.loading", self._locale)
            return tr("insert.error.primary", self._locale)
        if self._inserted_path is None or self._inserted_page_count is None:
            if self._inserted_count_runner.is_running():
                return tr("page_count.loading", self._locale)
            return tr("insert.error.source", self._locale)
        if self._primary_path.resolve(strict=False) == self._inserted_path.resolve(strict=False):
            return tr("insert.error.same_file", self._locale)
        if not self._inserted_grid.selected_pages():
            return tr("insert.error.selection", self._locale)
        if self._output.path() is None:
            return tr("insert.error.output", self._locale)
        return ""

    def _update_action_state(self) -> None:
        pages = self._inserted_grid.selected_pages()
        position = self._position_input.value()
        running = self._job_runner.is_running()
        self._output.setEnabled(not running)
        # Settings are frozen while the job runs: the result shown at the end
        # always matches the settings that produced it.
        for widget in (
            self._primary_input,
            self._inserted_input,
            self._primary_grid,
            self._inserted_grid,
        ):
            widget.setEnabled(not running)
        self._position_input.setEnabled(not running and self._primary_page_count is not None)
        self._action_bar.set_blocker(self._blocker())
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

    def set_workspace_document(self, document: WorkspaceDocument | None) -> None:
        if document is not None and (
            self._primary_path != document.path or self._primary_check.is_stale(document.path)
        ):
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
        if self._primary_path != primary_path or self._primary_check.is_stale(primary_path):
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
        self._output.set_locale(locale)
        self._action_bar.set_locale(locale)
        self._propose_output()
        self._primary_input.set_locale(locale)
        self._inserted_input.set_locale(locale)
        self._primary_check.set_locale(locale)
        self._inserted_check.set_locale(locale)
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
                    pages=page_count_text(self._primary_page_count, locale),
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
                    pages=page_count_text(self._inserted_page_count, locale),
                )
            )
        if self._primary_page_count is not None:
            self._populate_positions()
        self._update_action_state()
