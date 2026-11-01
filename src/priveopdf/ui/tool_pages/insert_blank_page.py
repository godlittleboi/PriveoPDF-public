from __future__ import annotations

import uuid
from pathlib import Path

from PySide6.QtCore import QLocale, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from priveopdf.app.settings import AppSettings
from priveopdf.domain.document_context import ToolLaunchContext
from priveopdf.domain.jobs import JobRequest, JobResult, OperationType
from priveopdf.domain.paper_sizes import (
    MAX_PDF_PAGE_MM,
    MIN_PDF_PAGE_MM,
    PAPER_SIZES_MM,
    orient_page_dimensions,
)
from priveopdf.ui.components import (
    GhostButton,
    OutputTargetField,
    PdfInputPanel,
    SourceCheck,
    SurfacePanel,
    ToolActionBar,
    expected_output_pages,
    job_result_message,
    open_output_folder_if_requested,
    output_suffix,
    proposed_output_directory,
)
from priveopdf.ui.components.tool_flow import format_decimal, page_count_text
from priveopdf.ui.i18n import Locale, tr
from priveopdf.ui.theme.tokens import SPACING
from priveopdf.ui.workspace_state import WorkspaceDocument
from priveopdf.workers.job_runner import PageCountResult, QtJobRunner, QtPageCountRunner


class InsertBlankPage(QWidget):
    back_requested = Signal()
    workspace_files_added = Signal(list, bool)
    page_count_ready = Signal(object, int)
    page_count_failed = Signal(object, str)
    job_completed = Signal(object)
    output_pdf_requested = Signal(object)

    def __init__(self, locale: Locale = "en", settings: AppSettings | None = None) -> None:
        super().__init__()
        self._locale = locale
        self._settings = settings or AppSettings()
        self._input_path: Path | None = None
        self._page_count: int | None = None
        self._queued_page_count_path: Path | None = None
        self._launch_context: ToolLaunchContext | None = None
        self._job_runner = QtJobRunner(self)
        self._count_runner = QtPageCountRunner(self)
        self._job_runner.finished.connect(self._operation_finished)
        self._count_runner.finished.connect(self._count_finished)

        self._description = QLabel()
        self._description.setObjectName("HelpText")
        self._description.setWordWrap(True)
        self._back = GhostButton()
        self._back.clicked.connect(self.back_requested.emit)
        self._input = PdfInputPanel(multiple=False, locale=locale)
        self._input.paths_selected.connect(self._handle_files)
        self._input_status = QLabel()
        self._input_status.setObjectName("HelpText")
        # L4: a protected or damaged source is reported under it.
        self._source_check = SourceCheck(locale)
        self._source_check.changed.connect(self._update_state)
        self._format = QComboBox()
        for key in (*PAPER_SIZES_MM, "custom"):
            self._format.addItem(key.upper() if key != "custom" else "", key)
        self._format.setCurrentIndex(1)
        self._width = self._dimension_input()
        self._height = self._dimension_input()
        self._format_label = QLabel()
        self._width_label = QLabel()
        self._height_label = QLabel()
        self._orientation_label = QLabel()
        self._position_label = QLabel()
        self._after_page_label = QLabel()
        self._portrait = QRadioButton()
        self._landscape = QRadioButton()
        self._portrait.setChecked(True)
        self._position = QComboBox()
        self._after_page = QSpinBox()
        self._after_page.setEnabled(False)
        self._effective = QLabel()
        self._effective.setObjectName("HelpText")
        self._output = OutputTargetField("file", locale)
        self._output.changed.connect(self._output_changed)
        self._action_bar = ToolActionBar(locale)
        self._action_bar.set_action_text_key("button.blank_page")
        self._action_bar.action_requested.connect(self._start)
        self._action_bar.cancel_requested.connect(self._job_runner.cancel)
        self._action_bar.open_pdf_requested.connect(self.output_pdf_requested.emit)
        self._action = self._action_bar.action_button()

        for widget in (
            self._format,
            self._width,
            self._height,
            self._portrait,
            self._landscape,
            self._position,
            self._after_page,
        ):
            if isinstance(widget, QComboBox):
                widget.currentIndexChanged.connect(self._options_changed)
            elif isinstance(widget, (QDoubleSpinBox, QSpinBox)):
                widget.valueChanged.connect(self._options_changed)
            else:
                widget.toggled.connect(self._options_changed)

        form = QFormLayout()
        form.addRow(self._format_label, self._format)
        form.addRow(self._width_label, self._width)
        form.addRow(self._height_label, self._height)
        orientation = QHBoxLayout()
        orientation.addWidget(self._portrait)
        orientation.addWidget(self._landscape)
        orientation.addStretch(1)
        form.addRow(self._orientation_label, orientation)
        form.addRow(self._position_label, self._position)
        form.addRow(self._after_page_label, self._after_page)
        form.addRow(self._effective)
        self._form = form
        panel = SurfacePanel(role="primary")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(*(SPACING["lg"],) * 4)
        panel_layout.addLayout(form)
        panel_layout.addWidget(self._output)
        panel_layout.addWidget(self._action_bar)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(*(SPACING["xxl"],) * 4)
        layout.setSpacing(SPACING["md"])
        toolbar = QHBoxLayout()
        toolbar.addWidget(self._back)
        toolbar.addStretch(1)
        layout.addLayout(toolbar)
        layout.addWidget(self._description)
        layout.addWidget(self._input)
        layout.addWidget(self._input_status)
        layout.addWidget(self._source_check)
        layout.addWidget(panel)
        layout.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(content)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)
        self.set_locale(locale)
        self._apply_preset()

    @staticmethod
    def _dimension_input() -> QDoubleSpinBox:
        value = QDoubleSpinBox()
        value.setRange(MIN_PDF_PAGE_MM, MAX_PDF_PAGE_MM)
        value.setDecimals(2)
        return value

    def _handle_files(self, paths: list[Path]) -> None:
        if paths:
            self._set_input(paths[0])
            self.workspace_files_added.emit(paths, True)

    def _set_input(self, path: Path) -> None:
        self._input_path = path
        self._page_count = None
        self._input.set_loaded(True)
        self._source_check.set_sources([path])
        self._input_status.setText(tr("blank.loading", self._locale, name=path.name))
        self._action_bar.clear_result()
        self._output.clear()
        self._propose_output()
        self._update_state()
        if self._count_runner.is_running():
            self._queued_page_count_path = path
            return
        self._count_runner.start(path)

    def _count_finished(self, result: PageCountResult) -> None:
        queued_path = self._queued_page_count_path
        self._queued_page_count_path = None
        if result.success:
            self.page_count_ready.emit(result.pdf_path, result.page_count)
        else:
            self.page_count_failed.emit(result.pdf_path, result.technical_detail)
        self._source_check.record(result)

        if result.pdf_path == self._input_path:
            if result.success:
                self._page_count = result.page_count
                self._after_page.setRange(1, result.page_count)
                self._after_page.setValue(min(1, result.page_count))
                self._input_status.setText(
                    tr(
                        "blank.ready",
                        self._locale,
                        name=result.pdf_path.name,
                        pages=page_count_text(result.page_count, self._locale),
                    )
                )
            else:
                self._page_count = None
                # L4: a protected or damaged PDF is reported under the source,
                # with `Change PDF` kept.
                reported = bool(self._source_check.problem())
                self._input.set_loaded(reported)
                if reported:
                    self._input_status.setText(result.pdf_path.name)
                else:
                    code = result.technical_detail or "invalid_pdf"
                    failure = JobResult(False, (), (), "-", code)
                    self._input_status.setText(job_result_message(failure, self._locale))
        if queued_path is not None and queued_path != result.pdf_path:
            self._count_runner.start(queued_path)
            self._update_state()
            return
        self._update_state()

    def _options_changed(self, *_args: object) -> None:
        self._action_bar.clear_result()
        self._apply_preset()
        self._after_page.setEnabled(
            self._position.currentData() == "after" and self._page_count is not None
        )
        self._update_state()

    def _refresh_field_visibility(self) -> None:
        """L5 / E5: a field without effect in the current state is hidden."""

        custom = self._format.currentData() == "custom"
        self._form.setRowVisible(self._width, custom)
        self._form.setRowVisible(self._height, custom)
        self._form.setRowVisible(self._after_page, self._position.currentData() == "after")

    def _apply_preset(self) -> None:
        preset = self._format.currentData()
        custom = preset == "custom"
        self._width.setEnabled(custom)
        self._height.setEnabled(custom)
        if hasattr(self, "_form"):
            self._refresh_field_visibility()
        if not custom and preset in PAPER_SIZES_MM:
            width, height = PAPER_SIZES_MM[preset]
            self._width.blockSignals(True)
            self._height.blockSignals(True)
            self._width.setValue(width)
            self._height.setValue(height)
            self._width.blockSignals(False)
            self._height.blockSignals(False)
        width, height = self._dimensions()
        self._effective.setText(
            tr(
                "blank.effective",
                self._locale,
                width=format_decimal(width, self._locale, 2),
                height=format_decimal(height, self._locale, 2),
            )
        )

    def _dimensions(self) -> tuple[float, float]:
        return orient_page_dimensions(
            self._width.value(), self._height.value(), landscape=self._landscape.isChecked()
        )

    def _propose_output(self) -> None:
        source = self._input_path
        if source is not None:
            directory = proposed_output_directory(source, self._settings)
            self._output.propose(directory, source.stem, output_suffix("blank_page", self._locale))

    def _output_changed(self) -> None:
        self._action_bar.clear_result()
        self._update_state()

    def _insert_after_page(self) -> int:
        mode = self._position.currentData()
        return (
            0
            if mode == "start"
            else self._after_page.value()
            if mode == "after"
            else (self._page_count or 0)
        )

    def _build_job(self) -> JobRequest:
        output_path = self._output.path()
        if self._input_path is None or self._page_count is None or output_path is None:
            raise ValueError(tr("blank.error.incomplete", self._locale))
        width, height = self._dimensions()
        return JobRequest(
            OperationType.INSERT_BLANK_PAGE,
            (self._input_path,),
            output_path.parent,
            {
                "width_mm": width,
                "height_mm": height,
                "insert_after_page": self._insert_after_page(),
                "output_path": output_path,
            },
            job_id=str(uuid.uuid4()),
        )

    def _start(self) -> None:
        if self._job_runner.is_running() or self._blocker():
            return
        try:
            job = self._build_job()
        except ValueError as exc:
            self._action_bar.show_error(str(exc))
            return
        self._action_bar.set_running(
            tr("blank.progress", self._locale),
            expected_pages=expected_output_pages(job, self._page_count),
        )
        self._job_runner.start(job)
        self._update_state()

    def _operation_finished(self, result: JobResult) -> None:
        if result.success:
            # Next free name first: a destination change clears the displayed result.
            self._output.refresh()
        self._action_bar.finish(result, job_result_message(result, self._locale, "blank"))
        self._update_state()
        if result.success:
            open_output_folder_if_requested(self._settings, result)
        self.job_completed.emit(result)

    def _blocker(self) -> str:
        if self._input_path is None:
            return tr("tool.required.source", self._locale)
        problem = self._source_check.blocker_text()
        if problem:
            return problem
        if self._page_count is None:
            if self._count_runner.is_running():
                return tr("page_count.loading", self._locale)
            return tr("tool.required.valid_source", self._locale)
        if self._output.path() is None:
            return tr("tool.required.output", self._locale)
        return ""

    def _update_state(self) -> None:
        running = self._job_runner.is_running()
        self._output.setEnabled(not running)
        self._input.setEnabled(not running)
        self._action_bar.set_blocker(self._blocker())

    def set_workspace_document(self, document: WorkspaceDocument | None) -> None:
        if document is not None and (
            document.path != self._input_path or self._source_check.is_stale(document.path)
        ):
            self._set_input(document.path)

    def set_workspace_documents(self, _documents: tuple[WorkspaceDocument, ...]) -> None:
        pass

    def set_tool_launch_context(self, context: ToolLaunchContext | None) -> None:
        self._launch_context = context
        if context and context.input_files:
            self._set_input(
                context.active_document.source_path
                if context.active_document
                else context.input_files[0]
            )

    def busy_document_paths(self) -> tuple[Path, ...]:
        return (self._input_path,) if self._job_runner.is_running() and self._input_path else ()

    def set_locale(self, locale: Locale) -> None:
        self._locale = locale
        self._description.setText(tr("tool.blank_page.subtitle", locale))
        self._back.setText(tr("button.back", locale))
        self._format.setItemText(5, tr("blank.format.custom", locale))
        self._portrait.setText(tr("blank.orientation.portrait", locale))
        self._landscape.setText(tr("blank.orientation.landscape", locale))
        self._format_label.setText(tr("blank.label.format", locale))
        self._width_label.setText(tr("blank.label.width", locale))
        self._height_label.setText(tr("blank.label.height", locale))
        self._orientation_label.setText(tr("blank.label.orientation", locale))
        self._position_label.setText(tr("blank.label.position", locale))
        self._after_page_label.setText(tr("blank.label.after_page", locale))
        current = self._position.currentData()
        self._position.clear()
        for key in ("start", "after", "end"):
            self._position.addItem(tr(f"blank.position.{key}", locale), key)
        self._position.setCurrentIndex(max(0, self._position.findData(current or "end")))
        # The spin boxes format their value with QLocale: decimal comma in French.
        number_locale = QLocale(
            QLocale.Language.French if locale == "fr" else QLocale.Language.English
        )
        for dimension in (self._width, self._height):
            dimension.setLocale(number_locale)
            dimension.setSuffix(tr("blank.unit_mm", locale))
        self._output.set_locale(locale)
        self._action_bar.set_locale(locale)
        self._propose_output()
        self._input.set_locale(locale)
        self._source_check.set_locale(locale)
        self._apply_preset()
        self._update_state()
