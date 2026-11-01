from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QLabel,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from priveopdf.app.settings import AppSettings
from priveopdf.domain.document_context import ToolLaunchContext
from priveopdf.domain.jobs import CompressionOptions, JobRequest, JobResult, OperationType
from priveopdf.ui.components import (
    ElidedLabel,
    GhostButton,
    OutputTargetField,
    PdfInputPanel,
    SourceCheck,
    SurfacePanel,
    ToolActionBar,
    job_result_message,
    open_output_folder_if_requested,
    output_suffix,
    proposed_output_directory,
)
from priveopdf.ui.components.tool_flow import format_bytes, format_decimal
from priveopdf.ui.i18n import Locale, tr
from priveopdf.ui.theme.tokens import SPACING
from priveopdf.ui.tool_pages.form_tool_page import FormToolPageMixin
from priveopdf.workers.job_runner import QtJobRunner


class CompressPdfPage(FormToolPageMixin, QWidget):
    back_requested = Signal()
    workspace_files_added = Signal(list, bool)
    job_completed = Signal(object)
    output_pdf_requested = Signal(object)

    def __init__(self, locale: Locale = "en", settings: AppSettings | None = None) -> None:
        super().__init__()
        self._locale = locale
        self._settings = settings or AppSettings()
        self._input_path: Path | None = None
        self._launch_context: ToolLaunchContext | None = None
        self._result: JobResult | None = None
        self._job_runner = QtJobRunner(self)
        self._job_runner.finished.connect(self._operation_finished)
        self._description = QLabel()
        self._description.setObjectName("HelpText")
        self._description.setWordWrap(True)
        self._back = GhostButton()
        self._back.clicked.connect(self.back_requested.emit)
        self._input = PdfInputPanel(multiple=False, locale=locale)
        self._input.paths_selected.connect(self._handle_files)
        self._document = ElidedLabel()
        # L4: the source is checked on load; a problem is shown under it.
        self._source_check = SourceCheck(locale)
        self._source_check.changed.connect(self._update_state)
        self._lossless = QRadioButton()
        self._strong = QRadioButton()
        self._lossless.setChecked(True)
        self._warning = QLabel()
        self._warning.setObjectName("HelpText")
        self._warning.setWordWrap(True)
        self._strong.toggled.connect(self._settings_changed)
        self._output = OutputTargetField("file", locale)
        self._output.changed.connect(self._settings_changed)
        self._action_bar = ToolActionBar(locale)
        self._action_bar.set_action_text_key("compress.action")
        self._action_bar.action_requested.connect(self._start)
        self._action_bar.cancel_requested.connect(self._job_runner.cancel)
        self._action_bar.open_pdf_requested.connect(self.output_pdf_requested.emit)
        panel = SurfacePanel(role="primary")
        controls = QVBoxLayout(panel)
        controls.setContentsMargins(*(SPACING["lg"],) * 4)
        controls.setSpacing(SPACING["md"])
        for widget in (self._lossless, self._strong, self._warning, self._output):
            controls.addWidget(widget)
        controls.addWidget(self._action_bar)
        self._install_form_layout(panel)
        self.set_locale(locale)

    def _set_input(self, path: Path) -> None:
        if self._job_runner.is_running():
            return
        if path == self._input_path:
            # L4: the same file may have changed (unlocked in place): check it again.
            self._source_check.check([path])
            return
        self._input_path = path
        self._result = None
        self._document.setText(path.name)
        self._input.set_loaded(True)
        self._output.clear()
        self._propose_output()
        self._action_bar.clear_result()
        self._source_check.check([path])
        self._update_state()

    def _propose_output(self) -> None:
        source = self._input_path
        if source is not None:
            directory = proposed_output_directory(source, self._settings)
            self._output.propose(directory, source.stem, output_suffix("compress", self._locale))

    def _settings_changed(self, *_args: object) -> None:
        self._result = None
        self._action_bar.clear_result()
        self._update_state()

    def _build_job(self) -> JobRequest:
        output_path = self._output.path()
        if self._input_path is None or output_path is None:
            raise ValueError("compression input or destination missing")
        return JobRequest(
            OperationType.COMPRESS_PDF,
            (self._input_path,),
            output_path.parent,
            CompressionOptions(output_path, "strong" if self._strong.isChecked() else "lossless"),
        )

    def _start(self) -> None:
        if self._job_runner.is_running() or self._blocker():
            return
        self._result = None
        self._job_runner.start(self._build_job())
        self._action_bar.set_running(tr("compress.progress", self._locale))
        self._update_state()

    def _operation_finished(self, result: JobResult) -> None:
        if result.success:
            # Next free name first: a destination change clears the displayed result.
            self._output.refresh()
        self._result = result
        self._action_bar.finish(result, self._result_message(result), show_size=False)
        if result.success:
            open_output_folder_if_requested(self._settings, result)
        self._update_state()
        # Keep the measurement visible even when launched from a PDF (contract adaptation).
        self.job_completed.emit(result)

    def _result_message(self, result: JobResult) -> str:
        if result.technical_detail == "compression_no_gain":
            return tr("compress.no_gain", self._locale)
        message = job_result_message(result, self._locale, "compress")
        sizes = result.compression
        if result.success and sizes is not None:
            message += "\n" + tr(
                "compress.result",
                self._locale,
                before=format_bytes(sizes.source_bytes, self._locale),
                after=format_bytes(sizes.candidate_bytes, self._locale),
                gain=format_decimal(sizes.reduction_percent, self._locale),
                duration=format_decimal(result.duration_ms / 1000, self._locale, 2),
            )
        return message

    def _blocker(self) -> str:
        if self._input_path is None:
            return tr("tool.required.source", self._locale)
        problem = self._source_check.blocker_text()
        if problem:
            return problem
        if self._output.path() is None:
            return tr("tool.required.output", self._locale)
        return ""

    def _update_state(self, *_args: object) -> None:
        busy = self._job_runner.is_running()
        for widget in (self._input, self._lossless, self._strong, self._output):
            widget.setEnabled(not busy)
        self._warning.setVisible(self._strong.isChecked())
        self._action_bar.set_blocker(self._blocker())

    def set_locale(self, locale: Locale) -> None:
        self._locale = locale
        for widget, key in (
            (self._description, "tool.compress.description"),
            (self._back, "button.back"),
            (self._lossless, "compress.lossless"),
            (self._strong, "compress.strong"),
            (self._warning, "compress.warning"),
        ):
            widget.setText(tr(key, locale))
        self._input.set_locale(locale)
        self._source_check.set_locale(locale)
        self._output.set_locale(locale)
        self._action_bar.set_locale(locale)
        self._propose_output()
        if self._result is not None:
            self._action_bar.finish(
                self._result, self._result_message(self._result), show_size=False
            )
        self._update_state()
