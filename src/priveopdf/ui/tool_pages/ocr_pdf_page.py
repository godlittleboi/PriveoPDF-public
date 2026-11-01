"""OCR PDF tool: a searchable copy of a scanned PDF (docs/ux/UX_CONTRACT.md)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from priveopdf.app.settings import AppSettings
from priveopdf.domain.document_context import ToolLaunchContext
from priveopdf.domain.jobs import (
    OCR_CPU_SECONDS,
    OCR_MAX_DOCUMENT_PAGES,
    OCR_STATE_PREFIXES,
    OCR_TESSDATA,
    OCR_TIMEOUT_SECONDS,
    JobRequest,
    JobResult,
    OcrOptions,
    OperationType,
)
from priveopdf.domain.ocr_languages import (
    OCR_BASELINE_LANGUAGES,
    OCR_MAX_SELECTED_LANGUAGES,
    ocr_language_name,
)
from priveopdf.domain.ocr_languages import installed_ocr_languages as _installed_models
from priveopdf.domain.page_ranges import parse_page_ranges, validate_page_numbers
from priveopdf.ui.components import (
    ElidedLabel,
    GhostButton,
    OutputTargetField,
    PdfInputPanel,
    SecondaryButton,
    SourceCheck,
    SurfacePanel,
    ToolActionBar,
    job_result_message,
    open_output_folder_if_requested,
    output_suffix,
    proposed_output_directory,
)
from priveopdf.ui.i18n import Locale, tr
from priveopdf.ui.theme.tokens import SPACING
from priveopdf.ui.tool_pages.form_tool_page import FormToolPageMixin
from priveopdf.workers.job_runner import PageCountResult, QtJobRunner
from priveopdf.workers.process_supervisor import ResourceLimits

# Progress and Cancel stay available during the long OCR delay.
OCR_LIMITS = ResourceLimits(cpu_seconds=OCR_CPU_SECONDS)
_INTERFACE_LANGUAGE_MODEL: dict[str, str] = {"fr": "fra", "en": "eng"}


# Languages shown per row; the grid wraps when more models are installed.
_LANGUAGE_COLUMNS = 3


def installed_ocr_languages(tessdata: Path = OCR_TESSDATA) -> tuple[str, ...]:
    """Model codes installed by the system packages: baseline languages first."""

    return _installed_models(tessdata)


def ocr_page_counts(result: JobResult) -> tuple[int, int, int] | None:
    """(recognized, already with text, no text found) announced by a successful OCR job."""

    counts: list[int] = []
    for prefix in OCR_STATE_PREFIXES:
        value = next(
            (warning[len(prefix) :] for warning in result.warnings if warning.startswith(prefix)),
            "",
        )
        if not value.isdigit():
            return None
        counts.append(int(value))
    return counts[0], counts[1], counts[2]


class OcrPdfPage(FormToolPageMixin, QWidget):
    back_requested = Signal()
    workspace_files_added = Signal(list, bool)
    job_completed = Signal(object)
    output_pdf_requested = Signal(object)

    def __init__(
        self,
        locale: Locale = "en",
        settings: AppSettings | None = None,
        *,
        installed_languages: tuple[str, ...] | None = None,
    ) -> None:
        super().__init__()
        self._locale = locale
        self._settings = settings or AppSettings()
        # Models installed while the application runs are found when the page is shown again.
        self._detect_models = installed_languages is None
        self._installed = (
            installed_ocr_languages() if installed_languages is None else installed_languages
        )
        self._input_path: Path | None = None
        self._page_count: int | None = None
        # Counts already received, by file: the check is not run again for a
        # document shown a second time (review of OCR10).
        self._known_counts: dict[Path, int] = {}
        self._launch_context: ToolLaunchContext | None = None
        self._result: JobResult | None = None
        # Pages chosen for the running or finished job (OCR10), for its message.
        self._job_pages: tuple[int, ...] = ()
        self._job_runner = QtJobRunner(self, timeout_seconds=OCR_TIMEOUT_SECONDS, limits=OCR_LIMITS)
        self._job_runner.finished.connect(self._operation_finished)
        self._job_runner.progress.connect(self._progress)
        self._description = QLabel()
        self._description.setObjectName("HelpText")
        self._description.setWordWrap(True)
        self._back = GhostButton()
        self._back.clicked.connect(self.back_requested.emit)
        self._input = PdfInputPanel(multiple=False, locale=locale)
        self._input.paths_selected.connect(self._handle_files)
        self._document = ElidedLabel()
        # L4: the source is checked on load; a problem is shown under it.
        self._source_check = SourceCheck(locale, unsigned_copy=True)
        self._source_check.changed.connect(self._update_state)
        self._source_check.checked.connect(self._source_counted)
        self._languages_title = QLabel()
        self._languages_title.setObjectName("SectionTitle")
        self._languages_help = QLabel()
        self._languages_help.setObjectName("HelpText")
        self._languages_help.setWordWrap(True)
        self._language_boxes: dict[str, QCheckBox] = {}
        self._languages_grid = QGridLayout()
        self._languages_grid.setContentsMargins(0, 0, 0, 0)
        self._languages_grid.setHorizontalSpacing(SPACING["lg"])
        self._languages_grid.setVerticalSpacing(SPACING["sm"])
        # Issue 438: a language is added from a list; the system installer does the rest.
        self._add_language = SecondaryButton()
        self._add_language.setObjectName("OcrAddLanguageButton")
        self._add_language.clicked.connect(self._open_add_language)
        self._languages_add = QLabel()
        self._languages_add.setObjectName("HelpText")
        self._languages_add.setWordWrap(True)
        self._languages_add.setTextFormat(Qt.TextFormat.PlainText)
        self._build_language_boxes()
        self._help = QLabel()
        self._help.setObjectName("HelpText")
        self._help.setWordWrap(True)
        # OCR10: the pages to recognize, under the folded advanced options.
        self._advanced = SecondaryButton()
        self._advanced.setObjectName("OcrAdvancedButton")
        self._advanced.clicked.connect(self._toggle_advanced)
        self._pages_title = QLabel()
        self._pages_title.setObjectName("SectionTitle")
        self._pages_input = QLineEdit()
        self._pages_input.setObjectName("OcrPagesInput")
        self._pages_input.textChanged.connect(self._settings_changed)
        self._pages_help = QLabel()
        self._pages_help.setObjectName("HelpText")
        self._pages_help.setWordWrap(True)
        self._advanced_widgets = (self._pages_title, self._pages_input, self._pages_help)
        for widget in self._advanced_widgets:
            widget.setVisible(False)
        self._output = OutputTargetField("file", locale)
        self._output.changed.connect(self._settings_changed)
        self._action_bar = ToolActionBar(locale)
        self._action_bar.set_action_text_key("ocr.action")
        self._action_bar.action_requested.connect(self._start)
        self._action_bar.cancel_requested.connect(self._job_runner.cancel)
        self._action_bar.open_pdf_requested.connect(self.output_pdf_requested.emit)
        self._check_default_language()
        panel = SurfacePanel(role="primary")
        controls = QVBoxLayout(panel)
        controls.setContentsMargins(*(SPACING["lg"],) * 4)
        controls.setSpacing(SPACING["md"])
        controls.addWidget(self._languages_title)
        controls.addLayout(self._languages_grid)
        add_row = QHBoxLayout()
        add_row.setContentsMargins(0, 0, 0, 0)
        add_row.addWidget(self._add_language)
        add_row.addStretch(1)
        controls.addWidget(self._languages_help)
        controls.addLayout(add_row)
        for widget in (
            self._languages_add,
            self._help,
            self._advanced,
            *self._advanced_widgets,
        ):
            controls.addWidget(widget)
        controls.addWidget(self._output)
        controls.addWidget(self._action_bar)
        self._install_form_layout(panel)
        self.set_locale(locale)

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802 - Qt override
        self._detect_installed_models()
        super().showEvent(event)

    def _open_add_language(self) -> None:
        from priveopdf.ui.ocr_language_dialog import OcrLanguageDialog

        dialog = OcrLanguageDialog(self._locale, self._installed, parent=self)
        dialog.installed.connect(self._model_installed)
        dialog.exec()
        self._detect_installed_models()

    def _model_installed(self, code: str) -> None:
        """A model installed from the dialog is offered and ticked at once."""

        self._detect_installed_models()
        box = self._language_boxes.get(code)
        if box is not None and box.isEnabled() and not box.isChecked():
            box.setChecked(True)

    def _detect_installed_models(self) -> None:
        if not self._detect_models or self._job_runner.is_running():
            return
        installed = installed_ocr_languages()
        if installed != self._installed:
            self._installed = installed
            self._build_language_boxes()
            if not self.selected_languages():
                self._check_default_language()
            self._update_state()

    def _check_default_language(self) -> None:
        """The interface language's model when installed, else the first installed one."""

        preferred = _INTERFACE_LANGUAGE_MODEL.get(self._locale, "eng")
        choice = preferred if preferred in self._installed else next(iter(self._installed), None)
        if choice is not None:
            self._language_boxes[choice].setChecked(True)

    def selected_languages(self) -> tuple[str, ...]:
        return tuple(
            code
            for code, box in self._language_boxes.items()
            if box.isChecked() and code in self._installed
        )

    def _toggle_advanced(self) -> None:
        visible = not self._pages_input.isVisible()
        for widget in self._advanced_widgets:
            widget.setVisible(visible)

    def _source_counted(self, result: object) -> None:
        if not isinstance(result, PageCountResult):
            return
        if result.success:
            self._known_counts[result.pdf_path] = result.page_count
        else:
            self._known_counts.pop(result.pdf_path, None)
        if result.pdf_path == self._input_path:
            self._page_count = self._known_counts.get(result.pdf_path)
            self._update_state()

    def page_numbers(self) -> tuple[int, ...]:
        """Chosen pages, unique and ascending; empty for every scanned page (OCR10)."""

        text = self._pages_input.text().strip()
        if not text:
            return ()
        return tuple(sorted(set(parse_page_ranges(text))))

    def _pages_blocker(self) -> str:
        if not self._pages_input.text().strip():
            return ""
        try:
            numbers = self.page_numbers()
        except ValueError:
            return tr("ocr.required.pages", self._locale)
        if len(numbers) > OCR_MAX_DOCUMENT_PAGES:
            return tr("ocr.required.pages_many", self._locale, count=OCR_MAX_DOCUMENT_PAGES)
        if self._page_count is not None:
            try:
                validate_page_numbers(numbers, self._page_count)
            except ValueError:
                return tr("ocr.required.pages_bounds", self._locale, count=self._page_count)
        return ""

    def _set_input(self, path: Path) -> None:
        if self._job_runner.is_running():
            return
        if path == self._input_path:
            # L4: the same file may have changed (unlocked in place): check it again.
            self._source_check.check([path])
            return
        self._input_path = path
        self._page_count = self._known_counts.get(path)
        self._result = None
        # The chosen pages belong to the previous document.
        self._pages_input.clear()
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
            self._output.propose(directory, source.stem, output_suffix("ocr_pdf", self._locale))

    def _settings_changed(self, *_args: object) -> None:
        self._result = None
        self._action_bar.clear_result()
        self._update_state()

    def _build_job(self) -> JobRequest:
        output_path = self._output.path()
        if self._input_path is None or output_path is None:
            raise ValueError("OCR input or destination missing")
        return JobRequest(
            OperationType.OCR_PDF,
            (self._input_path,),
            output_path.parent,
            OcrOptions(
                output_path,
                self.selected_languages(),
                self.page_numbers(),
                allow_unsigned_copy=self._source_check.unsigned_copy_allowed(),
            ),
        )

    def _start(self) -> None:
        if self._job_runner.is_running() or self._blocker():
            return
        self._result = None
        job = self._build_job()
        self._job_pages = self.page_numbers()
        self._job_runner.start(job)
        self._action_bar.set_running(tr("ocr.progress", self._locale))
        self._update_state()

    def _progress(self, done: int, total: int) -> None:
        self._action_bar.set_progress(done, total, tr("ocr.progress", self._locale))

    def _operation_finished(self, result: JobResult) -> None:
        if result.success:
            # Next free name first: a destination change clears the displayed result.
            self._output.refresh()
        self._result = result
        self._action_bar.finish(result, self._result_message(result))
        if result.success:
            open_output_folder_if_requested(self._settings, result)
        self._update_state()
        # Like Compress, the summary stays readable even when launched from a PDF.
        self.job_completed.emit(result)

    def _result_message(self, result: JobResult) -> str:
        selected = bool(self._job_pages)
        if selected and not result.success and result.technical_detail == "ocr_already_searchable":
            return tr("ocr.error.ocr_already_searchable_selected", self._locale)
        message = job_result_message(result, self._locale, "ocr")
        counts = ocr_page_counts(result) if result.success else None
        if counts is not None:
            recognized, present, empty = counts
            message += "\n" + tr(
                "ocr.result.selected" if selected else "ocr.result",
                self._locale,
                recognized=recognized,
                present=present,
                empty=empty,
            )
        return message

    def _blocker(self) -> str:
        if self._input_path is None:
            return tr("tool.required.source", self._locale)
        problem = self._source_check.blocker_text()
        if problem:
            return problem
        if not self._installed:
            return tr("ocr.required.models", self._locale)
        if not self.selected_languages():
            return tr("ocr.required.language", self._locale)
        pages_problem = self._pages_blocker()
        if pages_problem:
            return pages_problem
        if self._output.path() is None:
            return tr("tool.required.output", self._locale)
        return ""

    def _update_state(self, *_args: object) -> None:
        busy = self._job_runner.is_running()
        self._input.setEnabled(not busy)
        self._output.setEnabled(not busy)
        self._refresh_language_boxes(busy=busy)
        self._pages_input.setEnabled(not busy)
        self._action_bar.set_blocker(self._blocker())

    def _build_language_boxes(self) -> None:
        """One box per baseline language (greyed when absent) and per other installed model."""

        checked = {code for code, box in self._language_boxes.items() if box.isChecked()}
        while self._languages_grid.count():
            item = self._languages_grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._language_boxes = {}
        codes = (
            *OCR_BASELINE_LANGUAGES,
            *(c for c in self._installed if c not in OCR_BASELINE_LANGUAGES),
        )
        for index, code in enumerate(codes):
            box = QCheckBox()
            box.setObjectName(f"OcrLanguage_{code}")
            box.setChecked(code in checked and code in self._installed)
            box.toggled.connect(self._settings_changed)
            self._language_boxes[code] = box
            self._languages_grid.addWidget(
                box, index // _LANGUAGE_COLUMNS, index % _LANGUAGE_COLUMNS
            )
        self._languages_grid.setColumnStretch(_LANGUAGE_COLUMNS, 1)
        self._refresh_language_boxes()

    def _refresh_language_boxes(self, *, busy: bool = False) -> None:
        # At most three models per job: a fourth choice is not offered.
        full = len(self.selected_languages()) >= OCR_MAX_SELECTED_LANGUAGES
        for code, box in self._language_boxes.items():
            box.setText(ocr_language_name(code, self._locale))
            installed = code in self._installed
            box.setEnabled(not busy and installed and (box.isChecked() or not full))
            if not installed:
                box.setToolTip(tr("ocr.language_missing", self._locale, code=code))
            elif full and not box.isChecked():
                box.setToolTip(tr("ocr.language_limit", self._locale))
            else:
                box.setToolTip("")
        self._languages_add.setText(tr("ocr.languages_add", self._locale))

    def set_locale(self, locale: Locale) -> None:
        self._locale = locale
        for widget, key in (
            (self._description, "tool.ocr_pdf.description"),
            (self._back, "button.back"),
            (self._languages_title, "ocr.languages"),
            (self._languages_help, "ocr.languages_help"),
            (self._add_language, "ocr.add.button"),
            (self._help, "ocr.help"),
            (self._advanced, "ocr.advanced"),
            (self._pages_title, "ocr.pages"),
            (self._pages_help, "ocr.pages_help"),
        ):
            widget.setText(tr(key, locale))
        self._pages_input.setPlaceholderText(tr("ocr.pages_placeholder", locale))
        self._refresh_language_boxes()
        self._input.set_locale(locale)
        self._source_check.set_locale(locale)
        self._output.set_locale(locale)
        self._action_bar.set_locale(locale)
        self._propose_output()
        if self._result is not None:
            self._action_bar.finish(self._result, self._result_message(self._result))
        self._update_state()
