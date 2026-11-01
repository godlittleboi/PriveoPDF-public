"""One read-only inspection and two explicit sharing transformations."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from priveopdf.app.settings import AppSettings
from priveopdf.domain.document_context import ToolLaunchContext
from priveopdf.domain.jobs import (
    JobRequest,
    JobResult,
    OperationType,
    PhotocopyOptions,
    RemoveMetadataOptions,
)
from priveopdf.domain.share_inspection import CATEGORIES, COMMON_INFO, ShareInspection
from priveopdf.ui.components import (
    ElidedLabel,
    GhostButton,
    OutputTargetField,
    PdfInputPanel,
    ProgressOverlay,
    SecondaryButton,
    SourceCheck,
    SurfacePanel,
    ToolActionBar,
    job_result_message,
    open_output_folder_if_requested,
    output_suffix,
    proposed_output_directory,
)
from priveopdf.ui.components.isolated_pdf_view import IsolatedPdfView as QPdfView
from priveopdf.ui.components.tool_flow import error_detail, format_bytes
from priveopdf.ui.i18n import TRANSLATIONS, Locale, tr
from priveopdf.ui.theme.tokens import SPACING
from priveopdf.ui.tool_pages.view_pdf_page import ReaderPdfView
from priveopdf.ui.workspace_state import WorkspaceDocument
from priveopdf.workers.document_inspection_runner import (
    DocumentInspectionResult,
    QtDocumentInspectionRunner,
)
from priveopdf.workers.job_runner import QtJobRunner
from priveopdf.workers.render_client import RemotePdfDocument as QPdfDocument


def _identity(path: Path | None) -> tuple | None:
    if path is None:
        return None
    try:
        s = path.stat(follow_symlinks=False)
        return s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns
    except OSError:
        return None


class SharePdfPage(QWidget):
    back_requested = Signal()
    workspace_files_added = Signal(list, bool)
    job_completed = Signal(object)
    output_pdf_requested = Signal(object)

    def __init__(self, locale: Locale = "en", settings: AppSettings | None = None):
        super().__init__()
        self._locale = locale
        self._settings = settings or AppSettings()
        self._input_path = None
        self._launch_context = None
        self._report = None
        self._result = None
        self._inspection_path = None
        self._inspection_identity = None
        self._inspection_pending = False
        self._preview_identity = None
        self._preview_temp = None
        self._preview_running = False
        self._preview_loading = False
        self._preview_ready = False
        self._status_key = ""
        self._discard_results = False
        self._final_running = False
        self._replaced_input = False
        self._input_size = 0
        self._job_runner = QtJobRunner(self)
        self._job_runner.finished.connect(self._operation_finished)
        self._job_runner.progress.connect(self._progress_changed)
        self._inspection_runner = QtDocumentInspectionRunner(self, deep=True)
        self._inspection_runner.finished.connect(self._inspection_finished)
        self._back = GhostButton()
        self._back.clicked.connect(self.back_requested.emit)
        self._description = QLabel()
        self._description.setObjectName("HelpText")
        self._description.setWordWrap(True)
        self._input = PdfInputPanel(multiple=False, locale=locale)
        self._input.paths_selected.connect(self._handle_files)
        self._document = ElidedLabel()
        # L4: the source is checked on load; a problem is shown under it.
        self._source_check = SourceCheck(locale)
        self._source_check.changed.connect(self._update_state)
        self._refresh = SecondaryButton()
        self._refresh.clicked.connect(self._inspect_source)
        # L7 / E8: a synthesis sentence, then a table Item · In this PDF · To do;
        # technical terms (Info, XMP, raw properties) stay in the folded details.
        self._synthesis = QLabel()
        self._synthesis.setObjectName("ShareSynthesis")
        self._synthesis.setWordWrap(True)
        self._synthesis.setTextFormat(Qt.TextFormat.PlainText)
        self._report_table = QTableWidget(0, 3)
        self._report_table.setObjectName("ShareReportTable")
        self._report_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._report_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._report_table.setWordWrap(True)
        self._report_table.verticalHeader().setVisible(False)
        header = self._report_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        # Wrapped rows change height with the width: the table follows (review of PR 382).
        header.sectionResized.connect(self._fit_report_table)
        self._report_table.verticalHeader().sectionResized.connect(self._fit_report_table)
        self._report_table.verticalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self._details_toggle = QCheckBox()
        self._details = QPlainTextEdit()
        self._details.setReadOnly(True)
        self._details_toggle.toggled.connect(self._details.setVisible)
        self._mode = QComboBox()
        self._mode.addItems(["", ""])
        self._mode.currentIndexChanged.connect(self._mode_changed)
        self._warning = QLabel()
        self._warning.setWordWrap(True)
        self._warning.setTextFormat(Qt.TextFormat.PlainText)
        self._preview_button = SecondaryButton()
        self._preview_button.clicked.connect(self._start_preview)
        self._preview_document = QPdfDocument(self)
        self._preview_document.loaded.connect(self._preview_loaded)
        self._preview = ReaderPdfView()
        self._preview.setMinimumHeight(SPACING["xxl"] * 12)
        self._preview.setDocument(self._preview_document)
        self._preview.setPageMode(QPdfView.PageMode.SinglePage)
        self._preview.setZoomMode(QPdfView.ZoomMode.FitInView)
        self._page = QSpinBox()
        self._page.setRange(1, 1)
        self._page.valueChanged.connect(self._go_to_page)
        self._zoom = QComboBox()
        self._zoom.addItems(["", "", "", ""])
        self._zoom.currentIndexChanged.connect(self._zoom_changed)
        self._preview.page_step_requested.connect(
            lambda n: self._page.setValue(self._page.value() + n)
        )
        self._preview_status = QLabel()
        self._preview_status.setObjectName("HelpText")
        self._preview_status.setWordWrap(True)
        self._preview_status.setTextFormat(Qt.TextFormat.PlainText)
        self._cancel = SecondaryButton()
        self._cancel.clicked.connect(self._cancel_running)
        self._progress = ProgressOverlay()
        self._output = OutputTargetField("file", locale, allow_replace=True)
        self._output.changed.connect(self._destination_changed)
        self._action_bar = ToolActionBar(locale)
        self._action_bar.action_requested.connect(self._start)
        self._action_bar.cancel_requested.connect(self._cancel_running)
        self._action_bar.open_pdf_requested.connect(self.output_pdf_requested.emit)
        panel = SurfacePanel(role="primary")
        controls = QVBoxLayout(panel)
        controls.setContentsMargins(*(SPACING["lg"],) * 4)
        controls.setSpacing(SPACING["md"])
        for widget in (
            self._synthesis,
            self._report_table,
            self._details_toggle,
            self._details,
            self._refresh,
            self._mode,
            self._warning,
            self._preview_button,
            self._progress,
        ):
            controls.addWidget(widget)
        cancel_row = QHBoxLayout()
        cancel_row.addWidget(self._cancel)
        cancel_row.addStretch()
        controls.addLayout(cancel_row)
        navigation = QHBoxLayout()
        navigation.addWidget(self._page)
        navigation.addWidget(self._zoom)
        navigation.addStretch()
        controls.addLayout(navigation)
        controls.addWidget(self._preview)
        controls.addWidget(self._preview_status)
        controls.addWidget(self._output)
        controls.addWidget(self._action_bar)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(*(SPACING["xxl"],) * 4)
        layout.setSpacing(SPACING["md"])
        navigation_row = QHBoxLayout()
        navigation_row.addWidget(self._back)
        navigation_row.addStretch()
        layout.addLayout(navigation_row)
        for widget in (self._description, self._input, self._document, self._source_check, panel):
            layout.addWidget(widget)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(content)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)
        self.set_locale(locale)

    def _busy(self):
        return (
            self._job_runner.is_running()
            or self._inspection_runner.is_running()
            or self._preview_loading
        )

    def _handle_files(self, paths):
        if paths and not self._job_runner.is_running():
            self._set_input(paths[0])
            self.workspace_files_added.emit([paths[0]], True)

    def _set_input(self, path):
        if self._job_runner.is_running():
            return
        path = Path(path)
        # The shell sends both the workspace document and the launch context.
        # Keep the same live inspection instead of cancelling it on the second call.
        if (
            not self._discard_results
            and not self._inspection_pending
            and self._inspection_runner.is_running()
            and path == self._input_path == self._inspection_path
            and _identity(path) == self._inspection_identity
        ):
            return
        self._discard_results = False
        self._input_path = path
        self._report = self._result = None
        self._status_key = ""
        self._output.clear()
        self._propose_output()
        self._action_bar.clear_result()
        self._clear_preview()
        self._document.setText(path.name)
        self._input.set_loaded(True)
        self._source_check.check([path])
        self._render_report()
        if self._inspection_runner.is_running():
            self._inspection_pending = True
            self._inspection_runner.cancel()
        else:
            self._inspect_source()
        self._update_state()

    def _propose_output(self):
        source = self._input_path
        if source is not None:
            suffix = output_suffix("share_photo" if self._photo() else "share_check", self._locale)
            directory = proposed_output_directory(source, self._settings)
            self._output.propose(directory, source.stem, suffix, source=source)

    def _photo(self):
        return self._mode.currentIndex() == 1

    def _inspect_source(self):
        if self._input_path and not self._busy():
            self._inspect(self._input_path)

    def _inspect(self, path):
        self._inspection_pending = False
        self._inspection_path = path
        self._inspection_identity = _identity(path)
        self._report = None
        self._render_report()
        self._inspection_runner.start(path)
        self._progress.show_message(tr("share.inspecting", self._locale))
        self._update_state()

    def _inspection_finished(self, result: DocumentInspectionResult):
        self._progress.hide_overlay()
        if self._discard_results:
            return
        # The runner emits only after thread cleanup. Coalesce selection changes,
        # including A -> B -> A, without accepting the cancelled A report.
        if self._inspection_pending:
            self._inspect_source()
            return
        expected = (
            self._result.output_files[0]
            if self._result and self._result.success
            else self._input_path
        )
        if result.pdf_path != expected:
            self._update_state()
            return
        if _identity(result.pdf_path) != self._inspection_identity:
            self._status_key = "share.changed"
            self._report = None
        elif isinstance(result.inspection, ShareInspection):
            self._report = result.inspection
        self._render_report()
        self._update_state()

    def _render_report(self):
        report = self._report
        if report is None:
            self._synthesis.setText(tr("share.no_report", self._locale))
            self._set_report_rows(())
            self._details.clear()
            return
        rows = share_report_rows(report, self._locale)
        lines = []
        if not report.complete:
            lines.append(tr("share.partial", self._locale))
            cause = _incomplete_cause(report, self._locale)
            if cause:
                lines.append(cause)
        # Only a PDF that needs a password; restrictions alone do not block (issue 446).
        if "encrypted" in report.warnings:
            lines.append(tr("share.encrypted", self._locale))
        items = sum(1 for row in rows if row.attention)
        if not report.complete:
            # Never "nothing to report" for an inspection that did not finish.
            lines.append(tr("share.synthesis.incomplete", self._locale))
        elif items == 0:
            lines.append(tr("share.synthesis.none", self._locale))
        else:
            key = "share.synthesis.one" if items == 1 else "share.synthesis.many"
            lines.append(tr(key, self._locale, count=items))
        self._synthesis.setText("\n".join(lines))
        self._set_report_rows(rows)
        self._details.setPlainText(_technical_details(report, self._locale))

    def _set_report_rows(self, rows: tuple[ShareReportRow, ...]) -> None:
        table = self._report_table
        table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            for column, text in enumerate((row.item, row.value, row.todo)):
                # Plain text only: no tooltip, which would interpret document values
                # as rich text (review of PR 382).
                table.setItem(index, column, QTableWidgetItem(text))
        self._fit_report_table()

    def _fit_report_table(self, *_args: object) -> None:
        """The table shows every row; the page scrolls, not the table."""

        table = self._report_table
        table.resizeRowsToContents()
        height = table.horizontalHeader().height() + 2 * table.frameWidth()
        height += sum(table.rowHeight(index) for index in range(table.rowCount()))
        if table.height() != height:
            table.setFixedHeight(height)

    def report_text(self) -> str:
        """Everything the report shows, synthesis, table and details (tests, copy)."""

        cells = [
            self._report_table.item(row, column).text()
            for row in range(self._report_table.rowCount())
            for column in range(3)
            if self._report_table.item(row, column) is not None
        ]
        return "\n".join([self._synthesis.text(), *cells, self._details.toPlainText()])

    def _mode_changed(self):
        self._result = None
        self._status_key = ""
        self._action_bar.clear_result()
        self._propose_output()
        self._clear_preview()
        self._inspect_source()
        self._update_state()

    def _destination_changed(self):
        if not self._final_running:
            self._result = None
            self._action_bar.clear_result()
        self._update_state()

    def _build_job(self, destination=None, preview=False):
        target = destination or self._output.path()
        photo = preview or self._photo()
        replacing = False if preview else self._output.replacing()
        options = (
            PhotocopyOptions(
                target, replace_input=replacing, source_identity=self._preview_identity or ()
            )
            if photo
            else RemoveMetadataOptions(target, replace_input=replacing)
        )
        return JobRequest(
            OperationType.PHOTOCOPY_PDF if photo else OperationType.REMOVE_METADATA,
            (self._input_path,),
            target.parent,
            options,
        )

    def _start_preview(self):
        if self._busy() or self._input_path is None:
            return
        self._clear_preview()
        self._preview_temp = tempfile.TemporaryDirectory(prefix="priveopdf-preview-")
        self._preview_identity = _identity(self._input_path)
        self._preview_running = True
        self._result = None
        self._action_bar.clear_result()
        self._launch(self._build_job(Path(self._preview_temp.name) / "preview.pdf", preview=True))

    def _start(self):
        if self._busy() or self._blocker():
            return
        if self._photo() and _identity(self._input_path) != self._preview_identity:
            self._clear_preview()
            self._status_key = "share.changed"
            self._update_state()
            return
        if self._output.replacing():
            dialog = QMessageBox(self)
            dialog.setWindowTitle(tr("password.replace_title", self._locale))
            dialog.setTextFormat(Qt.TextFormat.PlainText)
            dialog.setText(
                tr(
                    "share.replace_photo" if self._photo() else "share.replace",
                    self._locale,
                )
            )
            dialog.setStandardButtons(
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            dialog.setDefaultButton(QMessageBox.StandardButton.No)
            if dialog.exec() != QMessageBox.StandardButton.Yes:
                return
        identity = _identity(self._input_path)
        if identity is None:
            self._status_key = "share.changed"
            self._update_state()
            return
        self._input_size = identity[2]
        self._result = None
        self._replaced_input = self._output.replacing()
        self._final_running = True
        self._action_bar.set_running(tr("share.processing", self._locale))
        self._launch(self._build_job())

    def _launch(self, job):
        self._status_key = ""
        self._job_runner.start(job)
        if not self._final_running:
            self._progress.show_message(tr("share.processing", self._locale))
        self._update_state()

    def _progress_changed(self, done, total):
        message = tr("share.progress", self._locale, done=done, total=total)
        if self._final_running:
            self._action_bar.set_progress(done, total, message)
        else:
            self._progress.show_progress(message, done, total)

    def _operation_finished(self, result):
        self._progress.hide_overlay()
        if self._preview_running:
            self._preview_running = False
            if (
                result.success
                and _identity(self._input_path) == self._preview_identity
                and self.isVisible()
            ):
                self._preview_ready = False
                self._preview_loading = True
                self._status_key = "viewer.loading"
                self._preview_document.load(str(result.output_files[0]))
            else:
                self._clear_preview()
                self._status_key = self._error_key(result)
        else:
            self._final_running = False
            if result.success and not self._replaced_input:
                # Next free name first: a destination change clears the displayed result.
                self._output.refresh()
            self._result = result
            self._action_bar.finish(result, self._result_message(result))
            if result.success:
                open_output_folder_if_requested(self._settings, result)
                self._clear_preview()
                if not self._discard_results and not self._inspection_runner.is_running():
                    self._inspect(result.output_files[0])
                self.job_completed.emit(result)
        self._update_state()

    def _result_message(self, result):
        if not result.success:
            if result.technical_detail == "dangerous_output" and self._replaced_input:
                return tr("password.error.replacement_refused", self._locale)
            return job_result_message(result, self._locale, "share")
        done = tr("share.photo_done" if self._photo() else "share.metadata_done", self._locale)
        size_after = (_identity(result.output_files[0]) or (0, 0, 0))[2]
        sizes = tr(
            "share.sizes",
            self._locale,
            before=format_bytes(self._input_size, self._locale),
            after=format_bytes(size_after, self._locale),
        )
        lines = [done, sizes]
        if not self._replaced_input:
            lines.insert(0, job_result_message(result, self._locale))
        return "\n".join(lines)

    def _preview_loaded(self, error):
        if not self._preview_loading:
            return
        self._preview_loading = False
        if not self.isVisible() or _identity(self._input_path) != self._preview_identity:
            self._clear_preview()
            self._status_key = "share.changed"
        elif error != QPdfDocument.Error.None_ or self._preview_document.pageCount() < 1:
            self._clear_preview()
            self._status_key = (
                "share.error.network_isolation_unavailable"
                if error == QPdfDocument.Error.IsolationUnavailable
                else "share.error.generic"
            )
        else:
            self._preview_ready = True
            self._page.setRange(1, self._preview_document.pageCount())
            self._page.setValue(1)
            self._go_to_page(1)
            self._status_key = "share.preview_ready"
        self._update_state()

    def _error_key(self, result):
        code = result.technical_detail
        known = {
            "metadata_absent",
            "share_signed",
            "encrypted_pdf",
            "photocopy_limit",
            "photocopy_unsupported",
            "user_cancelled",
            "worker_timeout",
            "render_memory_unavailable",
            "render_memory_or_worker_failed",
            "photocopy_renderer_unavailable",
            "network_isolation_unavailable",
        }
        return "share.error." + (code if code in known else "generic")

    def _blocker(self):
        if self._input_path is None:
            return tr("tool.required.source", self._locale)
        problem = self._source_check.blocker_text()
        if problem:
            return problem
        if self._inspection_runner.is_running():
            return tr("share.inspecting", self._locale)
        if self._photo() and not self._preview_ready:
            return tr("share.required.preview", self._locale)
        if self._output.path() is None:
            return tr("tool.required.output", self._locale)
        return ""

    def _clear_preview(self):
        self._preview_loading = False
        self._preview_document.close()
        self._preview_ready = False
        self._preview_identity = None
        if self._preview_temp and not self._job_runner.is_running():
            self._preview_temp.cleanup()
            self._preview_temp = None

    def _go_to_page(self, page):
        self._preview.pageNavigator().jump(page - 1, QPointF())

    def _zoom_changed(self, index):
        self._preview.setZoomMode(
            QPdfView.ZoomMode.Custom if index else QPdfView.ZoomMode.FitInView
        )
        if index:
            self._preview.setZoomFactor((1, 2, 4)[index - 1])

    def _cancel_running(self):
        self._inspection_pending = False
        self._job_runner.cancel()
        self._inspection_runner.cancel()
        if self._preview_loading:
            self._clear_preview()
            self._status_key = "share.error.user_cancelled"
            self._update_state()

    def _update_state(self):
        busy = self._busy()
        photo = self._photo()
        for widget in (self._input, self._refresh, self._mode, self._output):
            widget.setEnabled(not busy)
        self._refresh.setEnabled(not busy and self._input_path is not None)
        self._details.setVisible(self._details_toggle.isChecked())
        self._warning.setText(tr("share.warning" if photo else "share.standard_help", self._locale))
        self._preview_button.setVisible(photo)
        self._preview_button.setEnabled(not busy and self._input_path is not None)
        for widget in (self._preview, self._page, self._zoom):
            widget.setVisible(photo and self._preview_ready)
        self._action_bar.set_action_text_key(
            "share.photo_action" if photo else "share.metadata_action"
        )
        self._action_bar.set_blocker(self._blocker())
        self._cancel.setVisible(busy and not self._final_running)
        key = self._status_key
        error = key == "share.changed" or key.startswith("share.error.")
        self._preview_status.setText("" if error or not key else tr(key, self._locale))
        self._preview_status.setVisible(bool(key) and not error)
        if error:
            message = tr(key, self._locale)
            detail = error_detail(key.removeprefix("share.error."), self._locale)
            self._action_bar.show_error(f"{message}\n{detail}" if detail else message)
        elif self._result is None and not self._final_running:
            self._action_bar.clear_result()

    def set_locale(self, locale: Locale):
        self._locale = locale
        self._preview.set_locale(locale)
        for widget, key in (
            (self._back, "button.back"),
            (self._description, "tool.share_check.description"),
            (self._refresh, "share.refresh"),
            (self._details_toggle, "share.details_toggle"),
            (self._preview_button, "share.preview"),
            (self._cancel, "button.cancel"),
        ):
            widget.setText(tr(key, locale))
        self._mode.setItemText(0, tr("share.metadata_action", locale))
        self._mode.setItemText(1, tr("share.photo_mode", locale))
        self._zoom.setItemText(0, tr("share.fit", locale))
        for index, value in enumerate((100, 200, 400), start=1):
            self._zoom.setItemText(index, tr("share.zoom_value", locale, value=value))
        for widget, key in (
            (self._mode, "share.mode"),
            (self._page, "share.page"),
            (self._zoom, "share.zoom"),
            (self._report_table, "share.report"),
            (self._details, "share.details"),
        ):
            widget.setAccessibleName(tr(key, locale))
        self._report_table.setHorizontalHeaderLabels(
            [tr(f"share.column.{name}", locale) for name in ("item", "value", "todo")]
        )
        self._input.set_locale(locale)
        self._source_check.set_locale(locale)
        self._output.set_locale(locale)
        self._action_bar.set_locale(locale)
        self._propose_output()
        self._render_report()
        if self._result is not None:
            self._action_bar.finish(self._result, self._result_message(self._result))
        self._update_state()

    def set_workspace_document(self, document: WorkspaceDocument | None):
        if document and (
            self._discard_results
            or document.path != self._input_path
            or (self._report is None and not self._busy())
        ):
            self._set_input(document.path)

    def set_tool_launch_context(self, context: ToolLaunchContext | None):
        self._launch_context = context
        if context and context.input_files:
            self._set_input(
                context.active_document.source_path
                if context.active_document
                else context.input_files[0]
            )

    def busy_document_paths(self):
        return (self._input_path,) if self._busy() and self._input_path else ()

    def hideEvent(self, event):
        if self._final_running:
            # Like every other tool, the copy being written keeps running and its
            # result waits on the page; only what shows the document stops.
            self._inspection_pending = False
            self._inspection_runner.cancel()
            self._clear_preview()
            super().hideEvent(event)
            return
        self._discard_results = True
        self._cancel_running()
        self._clear_preview()
        self._report = None
        self._synthesis.clear()
        self._set_report_rows(())
        self._details.clear()
        super().hideEvent(event)


@dataclass(frozen=True)
class ShareReportRow:
    item: str
    value: str
    todo: str
    attention: bool


def share_report_rows(report: ShareInspection, locale: Locale) -> tuple[ShareReportRow, ...]:
    """Rows of the report table (L7): metadata first, then what was found."""

    rows: list[ShareReportRow] = []
    # A signed PDF can only be inspected: no row may suggest a transformation.
    signed = report.count("signatures") > 0
    metadata_todo = tr("share.todo.signed" if signed else "share.todo.metadata", locale)
    values: dict[str, list[str]] = {}
    for prop in report.properties:
        if prop.name not in COMMON_INFO:
            continue
        value = prop.value or tr("share.empty", locale)
        if prop.truncated:
            value += " " + tr("share.truncated", locale)
        if value not in values.setdefault(prop.name, []):
            values[prop.name].append(value)
    for name in COMMON_INFO:
        if name in values:
            item = tr(f"share.property.{name}", locale)
            rows.append(ShareReportRow(item, " / ".join(values[name]), metadata_todo, True))
    states = {report.info_state, report.xmp_state}
    item = tr("share.element.metadata", locale)
    if not rows and "present" in states:
        value = tr("share.value.present", locale)
        rows.append(ShareReportRow(item, value, metadata_todo, True))
    # Metadata not read is never reported as absent (review of PR 382), and stays
    # visible next to the common fields read elsewhere (Codex review of PR 385).
    unread = next((s for s in ("unreadable", "limited", "not_analyzed") if s in states), None)
    if unread is not None:
        value = tr(f"share.state.{unread}", locale)
        rows.append(ShareReportRow(item, value, tr("share.todo.details", locale), True))
    if not rows:
        value = tr("share.value.none", locale)
        rows.append(ShareReportRow(item, value, tr("share.todo.nothing", locale), False))
    for category in CATEGORIES:
        count = report.count(category)
        if count == 0:
            continue
        value = str(count)
        if not report.complete:
            value = tr("share.at_least", locale, count=value)
        if signed:
            todo = tr("share.todo.signed", locale)
        elif category in {"forms", "widgets"}:
            # A form the photocopy cannot render faithfully makes it refuse.
            todo = tr("share.todo.form", locale)
        else:
            todo = tr("share.todo.kept", locale)
        rows.append(ShareReportRow(tr(f"share.category.{category}", locale), value, todo, True))
    return tuple(rows)


def _technical_details(report: ShareInspection, locale: Locale) -> str:
    """Folded details: scope of the analysis, Info and XMP, every raw property."""

    lines = [tr("share.complete" if report.complete else "share.partial", locale)]
    for name, state in (("Info", report.info_state), ("XMP", report.xmp_state)):
        value = tr("share.state." + state, locale)
        lines.append(tr("share.line", locale, name=name, value=value))
    for category in CATEGORIES:
        count = str(report.count(category))
        if not report.complete:
            count = tr("share.at_least", locale, count=count)
        name = tr("share.category." + category, locale)
        lines.append(tr("share.line", locale, name=name, value=count))
    properties = []
    for prop in report.properties:
        value = prop.value or tr("share.empty", locale)
        line = f"[{prop.origin}] " + tr("share.line", locale, name=prop.name, value=value)
        if prop.truncated:
            line += " " + tr("share.truncated", locale)
        properties.append(line)
    lines.extend(properties or [tr("share.no_extra", locale)])
    return "\n".join(lines)


def _incomplete_cause(report: ShareInspection, locale: Locale) -> str:
    """B14: why an inspection is incomplete, in the interface language."""

    if report.complete:
        return ""
    for code in report.warnings:
        # An encrypted PDF already gets its own line (share.encrypted).
        if code == "encrypted":
            continue
        known = any(
            key in TRANSLATIONS[locale] for key in (f"share.error.{code}", f"job.error.{code}")
        )
        # The generic share message speaks of a destination: wrong for an inspection.
        failure = JobResult(False, (), (), "-", code if known else "analysis_failed")
        return job_result_message(failure, locale, "share")
    return ""
