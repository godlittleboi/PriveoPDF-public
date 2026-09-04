from __future__ import annotations

import uuid
from pathlib import Path

from PySide6.QtCore import QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from pdfmod.app.settings import AppSettings
from pdfmod.domain.document_context import ToolLaunchContext
from pdfmod.domain.jobs import JobRequest, JobResult, OperationType
from pdfmod.domain.paper_sizes import (
    MAX_PDF_PAGE_MM,
    MIN_PDF_PAGE_MM,
    PAPER_SIZES_MM,
    orient_page_dimensions,
)
from pdfmod.ui.components import (
    GhostButton,
    PdfInputPanel,
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


class InsertBlankPage(QWidget):
    back_requested = Signal()
    workspace_files_added = Signal(list, bool)
    page_count_ready = Signal(object, int)
    page_count_failed = Signal(object)
    job_completed = Signal(object)

    def __init__(self, locale: Locale = "en", settings: AppSettings | None = None) -> None:
        super().__init__()
        self._locale = locale
        self._settings = settings or AppSettings()
        self._input_path: Path | None = None
        self._page_count: int | None = None
        self._queued_page_count_path: Path | None = None
        self._output_path: Path | None = None
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
        self._output_label = QLabel()
        self._output_label.setObjectName("HelpText")
        self._output = SecondaryButton()
        self._output.clicked.connect(self._choose_output)
        self._action = PrimaryButton()
        self._action.clicked.connect(self._start)
        self._action.setEnabled(False)
        self._status = QLabel()
        self._status.setObjectName("StatusText")
        self._progress = ProgressOverlay()

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
        output_row = QHBoxLayout()
        output_row.addWidget(self._output_label, 1)
        output_row.addWidget(self._output)
        panel = SurfacePanel(role="primary")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(*(SPACING["lg"],) * 4)
        panel_layout.addLayout(form)
        panel_layout.addLayout(output_row)
        panel_layout.addWidget(self._action)
        panel_layout.addWidget(self._progress)
        panel_layout.addWidget(self._status)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(*(SPACING["xxl"],) * 4)
        layout.setSpacing(SPACING["md"])
        toolbar = QHBoxLayout()
        toolbar.addWidget(self._back)
        toolbar.addStretch(1)
        layout.addWidget(self._description)
        layout.addLayout(toolbar)
        layout.addWidget(self._input)
        layout.addWidget(self._input_status)
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
        value.setSuffix(" mm")
        return value

    def _handle_files(self, paths: list[Path]) -> None:
        if paths:
            self._set_input(paths[0])
            self.workspace_files_added.emit(paths, True)

    def _set_input(self, path: Path) -> None:
        self._input_path = path
        self._page_count = None
        self._input.set_loaded(True)
        self._input_status.setText(tr("blank.loading", self._locale, name=path.name))
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
            self.page_count_failed.emit(result.pdf_path)

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
                        count=result.page_count,
                    )
                )
            else:
                self._page_count = None
                self._input.set_loaded(False)
                self._input_status.setText(result.user_message)
        if queued_path is not None and queued_path != result.pdf_path:
            self._count_runner.start(queued_path)
            self._update_state()
            return
        self._update_state()

    def _options_changed(self, *_args: object) -> None:
        self._apply_preset()
        self._after_page.setEnabled(
            self._position.currentData() == "after" and self._page_count is not None
        )
        self._update_state()

    def _apply_preset(self) -> None:
        preset = self._format.currentData()
        custom = preset == "custom"
        self._width.setEnabled(custom)
        self._height.setEnabled(custom)
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
            tr("blank.effective", self._locale, width=f"{width:.2f}", height=f"{height:.2f}")
        )

    def _dimensions(self) -> tuple[float, float]:
        return orient_page_dimensions(
            self._width.value(), self._height.value(), landscape=self._landscape.isChecked()
        )

    def _choose_output(self) -> None:
        name, _ = QFileDialog.getSaveFileName(
            self,
            tr("blank.output.dialog", self._locale),
            self._default_output_path(),
            "PDF (*.pdf)",
        )
        if name:
            self._output_path = Path(name)
            self._output_path = (
                self._output_path
                if self._output_path.suffix.lower() == ".pdf"
                else self._output_path.with_suffix(".pdf")
            )
            self._output_label.setText(str(self._output_path))
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
        if self._input_path is None or self._page_count is None or self._output_path is None:
            raise ValueError(tr("blank.error.incomplete", self._locale))
        width, height = self._dimensions()
        return JobRequest(
            OperationType.INSERT_BLANK_PAGE,
            (self._input_path,),
            self._output_path.parent,
            {
                "width_mm": width,
                "height_mm": height,
                "insert_after_page": self._insert_after_page(),
                "output_path": self._output_path,
            },
            job_id=str(uuid.uuid4()),
        )

    def _start(self) -> None:
        try:
            job = self._build_job()
        except ValueError as exc:
            show_error(self, tr("error.operation.title", self._locale), str(exc))
            return
        progress = tr("blank.progress", self._locale)
        self._progress.show_message(progress)
        self._status.setText(progress)
        self._job_runner.start(job)
        self._update_state()

    def _operation_finished(self, result: JobResult) -> None:
        self._progress.hide_overlay()
        self.job_completed.emit(result)
        self._update_state()
        if not result.success:
            show_error(
                self,
                tr("error.operation.title", self._locale),
                result.user_message,
                result.technical_detail,
            )
            return
        message = tr("blank.success.message", self._locale, name=result.output_files[0].name)
        self._status.setText(message)
        if self._settings.after_job_behavior() == "open_output_folder":
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(result.output_files[0].parent)))
        show_info(self, tr("blank.success.title", self._locale), message)

    def _update_state(self) -> None:
        safe_output = (
            self._output_path is not None
            and not self._output_path.exists()
            and (
                self._input_path is None
                or self._output_path.resolve(strict=False) != self._input_path.resolve(strict=False)
            )
        )
        self._action.setEnabled(
            self._page_count is not None
            and safe_output
            and not self._job_runner.is_running()
            and not self._count_runner.is_running()
        )

    def _default_output_path(self) -> str:
        name = f"{self._input_path.stem if self._input_path else 'document'}_avec-page-blanche.pdf"
        directory = (
            self._launch_context.suggested_output_dir
            if self._launch_context and self._launch_context.suggested_output_dir
            else self._settings.default_output_dir()
        )
        return str(directory / name) if directory else name

    def set_workspace_document(self, document: WorkspaceDocument | None) -> None:
        if document is not None and document.path != self._input_path:
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
        self._output.setText(tr("button.choose_output", locale))
        self._action.setText(tr("button.blank_page", locale))
        self._output_label.setText(
            str(self._output_path) if self._output_path else tr("output.none_file", locale)
        )
        self._input.set_locale(locale)
        self._apply_preset()
        self._update_state()
