"""Shared Output and Action/Result zones of the tool contract (docs/ux/UX_CONTRACT.md)."""

from __future__ import annotations

import contextlib
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Literal

from PySide6.QtCore import QStandardPaths, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QDesktopServices, QResizeEvent
from PySide6.QtWidgets import (
    QBoxLayout,
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMenu,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from priveopdf.app.app_info import is_beta_runtime, is_dev_runtime
from priveopdf.app.settings import AppSettings
from priveopdf.domain.jobs import JobRequest, JobResult, OperationType
from priveopdf.ui.components.buttons import PrimaryButton, SecondaryButton
from priveopdf.ui.components.cards import ElidedLabel
from priveopdf.ui.components.feedback import ProgressOverlay
from priveopdf.ui.components.guided_action_cue import GuidedActionCue, _app_reduce_motion
from priveopdf.ui.i18n import DEFAULT_LOCALE, TRANSLATIONS, Locale, tr
from priveopdf.ui.theme.tokens import SIZES, SPACING
from priveopdf.utils.secure_paths import portable_filename_stem

OutputTargetMode = Literal["file", "directory"]
MAX_OUTPUT_NAME_ATTEMPTS = 999


def suggest_output_path(
    directory: Path,
    stem: str,
    suffix: str,
    *,
    exists: Callable[[Path], bool] = Path.exists,
) -> Path:
    """Return `<directory>/<stem><suffix>.pdf`, numbered `-2`, `-3`… when taken."""

    # The engine refuses some names Linux allows (":", "?", length): propose a valid one.
    base = f"{portable_filename_stem(stem)}{suffix}"
    candidate = directory / f"{base}.pdf"
    attempt = 2
    while exists(candidate) and attempt <= MAX_OUTPUT_NAME_ATTEMPTS:
        candidate = directory / f"{base}-{attempt}.pdf"
        attempt += 1
    return candidate


def proposed_output_directory(source: Path, settings: AppSettings) -> Path:
    """Default output folder: the setting, else the source folder (UX contract, rule 4).

    In dev and Beta, a source under `dev_corpus` never gets its output proposed
    there (issue 311): Documents, else the home folder, is proposed instead.
    """

    configured = settings.default_output_dir()
    if configured is not None:
        return configured
    directory = source.parent
    if (is_dev_runtime() or is_beta_runtime()) and "dev_corpus" in directory.parts:
        documents = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.DocumentsLocation
        )
        return Path(documents) if documents and Path(documents).is_dir() else Path.home()
    return directory


def output_suffix(tool_key: str, locale: Locale) -> str:
    return tr(f"output.suffix.{tool_key}", locale)


# L7 / E8: for these failures the main text names no system component; the code
# stays on its own copyable line for support.
TECHNICAL_DETAIL_CODES = frozenset(
    {
        "ocr_renderer_unavailable",
        "photocopy_renderer_unavailable",
        "render_memory_or_worker_failed",
        "render_memory_unavailable",
    }
)


def error_detail(code: str, locale: Locale) -> str:
    """`Technical detail: <code>` for the codes that need one, else ""."""

    return tr("job.error.detail", locale, code=code) if code in TECHNICAL_DETAIL_CODES else ""


def job_result_message(result: JobResult, locale: Locale, tool_key: str = "") -> str:
    """Localized one-line message for a job result, never the engine's own sentence."""

    if result.success:
        if len(result.output_files) == 1:
            return tr("job.success.file_created", locale, name=result.output_files[0].name)
        return tr("job.success.files_created", locale, count=len(result.output_files))
    code = result.technical_detail
    catalogue = TRANSLATIONS[DEFAULT_LOCALE]
    candidates = (f"{tool_key}.error.{code}", f"job.error.{code}") if code else ()
    message = tr("job.error.generic", locale)
    for key in (*candidates, f"{tool_key}.error.generic"):
        if key in catalogue:
            message = tr(key, locale)
            break
    detail = error_detail(code, locale)
    return f"{message}\n{detail}" if detail else message


def expected_output_pages(job: JobRequest, source_pages: int | None) -> int | None:
    """Pages of the single PDF a job will produce, when its request states them (L1)."""

    options = job.options
    operation = job.operation
    if operation is OperationType.EXTRACT_PAGES:
        return len(tuple(options.get("page_numbers") or ())) or None
    if operation is OperationType.REORDER_PAGES:
        return len(tuple(options.get("page_order") or ())) or None
    if source_pages is None or source_pages <= 0:
        return None
    if operation is OperationType.REMOVE_PAGES:
        return source_pages - len(set(options.get("page_numbers") or ())) or None
    if operation is OperationType.ROTATE_PAGES:
        return source_pages
    if operation is OperationType.INSERT_BLANK_PAGE:
        return source_pages + 1
    if operation is OperationType.INSERT_PDF_PAGES:
        return source_pages + len(tuple(options.get("page_numbers") or ()))
    return None


def page_count_text(count: int, locale: Locale) -> str:
    """ "1 page" / "12 pages" in the interface language, never "page(s)"."""

    key = "dashboard.ready.page_count_one" if count == 1 else "dashboard.ready.page_count_many"
    return tr(key, locale, count=count)


def format_bytes(count: int, locale: Locale) -> str:
    """Human size in the interface language: `512 octets`, `1,4 Mo`, `1.4 MB`."""

    units = ("size.bytes", "size.kib", "size.mib", "size.gib")
    value = float(count)
    index = 0
    while value >= 1024 and index < len(units) - 1:
        value /= 1024
        index += 1
    return tr(units[index], locale, value=format_decimal(value, locale, 0 if index == 0 else 1))


def format_decimal(value: float, locale: Locale, digits: int = 1) -> str:
    text = f"{value:.{digits}f}"
    return text.replace(".", ",") if locale == "fr" else text


class OutputTargetField(QWidget):
    """Output zone: a destination proposed as soon as a source exists, never overwritten.

    With `allow_replace`, a "Replace this PDF" box (unchecked for every new source)
    turns the destination into the source itself; the page confirms before running.
    """

    changed = Signal()

    def __init__(
        self,
        mode: OutputTargetMode = "file",
        locale: Locale = DEFAULT_LOCALE,
        parent: QWidget | None = None,
        *,
        allow_replace: bool = False,
    ) -> None:
        super().__init__(parent)
        self._mode: OutputTargetMode = mode
        self._locale = locale
        self._path: Path | None = None
        self._base: tuple[Path, str, str] | None = None
        self._manual = False
        self._source: Path | None = None
        self._caption = QLabel()
        self._caption.setObjectName("HelpText")
        self._value = ElidedLabel()
        self._value.setObjectName("OutputFileName")
        self._change = SecondaryButton()
        self._change.clicked.connect(self._choose)
        self._replace = QCheckBox()
        self._replace.setVisible(allow_replace)
        self._replace.toggled.connect(self._replace_toggled)
        self._replace_help = QLabel()
        self._replace_help.setObjectName("HelpText")
        self._replace_help.setWordWrap(True)
        self._replace_help.setVisible(allow_replace)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(SPACING["sm"])
        row.addWidget(self._value, 1)
        row.addWidget(self._change)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING["xs"])
        layout.addWidget(self._caption)
        layout.addLayout(row)
        layout.addWidget(self._replace)
        layout.addWidget(self._replace_help)
        self.set_locale(locale)

    def path(self) -> Path | None:
        if self.replacing():
            return self._source
        return self._path

    def replacing(self) -> bool:
        return self._replace.isChecked() and self._source is not None

    def propose(
        self, directory: Path, stem: str, suffix: str, *, source: Path | None = None
    ) -> None:
        """Propose `<directory>/<stem><suffix>.pdf` (or `directory` in folder mode).

        A destination chosen by the user is kept until `clear()`. A new `source`
        always unchecks "Replace this PDF".
        """

        if source != self._source:
            self._source = source
            self.reset_replace()
        if self._manual:
            return
        self._base = (directory, stem, suffix)
        self._apply_base()

    def clear(self) -> None:
        self._manual = False
        self._base = None
        self._source = None
        self.reset_replace()
        self._set_path(None)

    def reset_replace(self) -> None:
        """Rule 5: replacing the original is never pre-selected."""

        self._replace.setChecked(False)

    def refresh(self) -> None:
        """Move to the next free name when the current destination was taken meanwhile."""

        if self._mode == "file" and self._path is not None and self._path.exists():
            self._apply_base()

    def set_locale(self, locale: Locale) -> None:
        self._locale = locale
        caption = (
            "output.panel.destination_dir"
            if self._mode == "directory"
            else ("output.panel.destination")
        )
        self._caption.setText(tr(caption, locale))
        self._change.setText(tr("output.change", locale))
        self._change.setToolTip(tr(f"output.dialog.{self._mode}", locale))
        self._replace.setText(tr("output.replace_input", locale))
        self._render()

    def _apply_base(self) -> None:
        if self._base is None:
            return
        directory, stem, suffix = self._base
        if self._mode == "directory":
            self._set_path(directory)
            return
        self._set_path(suggest_output_path(directory, stem, suffix))

    def _choose(self) -> None:
        start = str(self._path) if self._path is not None else ""
        title = tr(f"output.dialog.{self._mode}", self._locale)
        if self._mode == "directory":
            selected = QFileDialog.getExistingDirectory(self, title, start)
            if selected:
                self._manual = True
                self._base = (Path(selected), "", "")
                self._apply_base()
            return
        selected, _ = QFileDialog.getSaveFileName(
            self,
            title,
            start,
            "PDF (*.pdf)",
            options=QFileDialog.Option.DontConfirmOverwrite,
        )
        if selected:
            chosen = Path(selected)
            stem = chosen.stem if chosen.suffix.lower() == ".pdf" else chosen.name
            self._manual = True
            self._base = (chosen.parent, stem, "")
            self._apply_base()

    def _replace_toggled(self) -> None:
        self._render()
        self.changed.emit()

    def _set_path(self, path: Path | None) -> None:
        if path == self._path:
            return
        self._path = path
        self._render()
        self.changed.emit()

    def _render(self) -> None:
        shown = self.path()
        if shown is None:
            empty = "output.none_dir" if self._mode == "directory" else "output.none_file"
            self._value.setText(tr(empty, self._locale))
        else:
            self._value.setText(str(shown))
        replacing = self.replacing()
        self._change.setVisible(not replacing)
        self._change.setEnabled(self._base is not None)
        help_key = "output.replace_help" if replacing else "output.copy_help"
        self._replace_help.setText(tr(help_key, self._locale))


def open_output_folder_if_requested(settings: AppSettings, result: JobResult) -> None:
    """Setting « Après traitement » = open the output folder, for every tool (E1, L1)."""

    if settings.after_job_behavior() != "open_output_folder" or not result.output_files:
        return
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(result.output_files[0].parent)))


class ToolActionBar(QWidget):
    """Action zone: one primary button, its blocker, progress with cancel, then the result."""

    action_requested = Signal()
    cancel_requested = Signal()
    open_pdf_requested = Signal(object)
    continue_requested = Signal(object, str)

    def __init__(self, locale: Locale = DEFAULT_LOCALE, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._locale = locale
        self._action_key = ""
        self._blocker = ""
        self._running = False
        self._result: JobResult | None = None
        self._result_text = ""
        self._action = PrimaryButton()
        self._action.clicked.connect(self.request_action)
        self._blocker_label = QLabel()
        self._blocker_label.setObjectName("HelpText")
        self._blocker_label.setWordWrap(True)
        self._progress = ProgressOverlay()
        self._cancel = SecondaryButton()
        self._cancel.clicked.connect(self.cancel_requested.emit)
        self._result_label = QLabel()
        self._result_label.setObjectName("ResultText")
        self._result_label.setWordWrap(True)
        self._error_label = QLabel()
        self._error_label.setObjectName("ErrorText")
        self._error_label.setWordWrap(True)
        # Rule 9: an error and its technical detail can be copied, also with the keyboard.
        self._error_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self._error_label.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._open_pdf = SecondaryButton()
        self._open_pdf.clicked.connect(self._request_open_pdf)
        self._open_folder = SecondaryButton()
        self._open_folder.clicked.connect(self._open_result_folder)
        # L2: "Continue with…" opens another tool on the produced PDF.
        self._continue = SecondaryButton()
        self._continue_menu = QMenu(self._continue)
        self._continue_menu.triggered.connect(self._continue_triggered)
        self._continue.setMenu(self._continue_menu)
        self._continue_entries: tuple[tuple[str, str], ...] = ()
        self._details = ""
        self._show_size = True
        self._page_count: int | None = None
        self._expected_pages: int | None = None
        # The one next logical step of every tool: its action button, as soon
        # as nothing blocks it and until a result is shown (every tool alike).
        self._cue = GuidedActionCue(self)

        cancel_row = QHBoxLayout()
        cancel_row.setContentsMargins(0, 0, 0, 0)
        cancel_row.addWidget(self._cancel)
        cancel_row.addStretch(1)
        self._result_actions = _ResultActions((self._open_pdf, self._open_folder, self._continue))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING["sm"])
        layout.addWidget(self._action)
        layout.addWidget(self._blocker_label)
        layout.addWidget(self._progress)
        layout.addLayout(cancel_row)
        layout.addWidget(self._result_label)
        layout.addWidget(self._error_label)
        layout.addWidget(self._result_actions)
        self.set_locale(locale)

    def action_button(self) -> PrimaryButton:
        return self._action

    def guided_cue(self) -> GuidedActionCue:
        """The highlight of the next step; the bar aims it at its own button."""
        return self._cue

    def set_action_text_key(self, key: str) -> None:
        self._action_key = key
        self._action.setText(tr(key, self._locale).upper())

    def set_blocker(self, text: str) -> None:
        """Empty text means ready; otherwise the action stays disabled with this reason."""

        self._blocker = text
        self._refresh()

    def set_running(self, message: str = "", *, expected_pages: int | None = None) -> None:
        """`expected_pages`: pages of the produced PDF, shown in the result (L1)."""

        self._running = True
        self._expected_pages = expected_pages
        self.clear_result()
        self._progress.show_message(message or tr("job.running", self._locale))
        self._refresh()

    def set_progress(self, done: int, total: int, message: str = "") -> None:
        if self._running and total > 0:
            self._progress.show_progress(message or tr("job.running", self._locale), done, total)

    def finish(
        self,
        result: JobResult,
        message: str,
        *,
        page_count: int | None = None,
        show_size: bool = True,
    ) -> None:
        """Show the result in the page (L1): message, then size, pages and folder.

        `page_count` is the produced PDF's page count when the tool knows it;
        `show_size=False` when `message` already states the size (Compress).
        """

        self._running = False
        self._progress.hide_overlay()
        self._result = result
        self._result_text = message
        self._page_count = page_count if page_count is not None else self._expected_pages
        self._show_size = show_size
        self._details = self._result_details()
        self._refresh()
        # The result replaces the button area: bring it into view on short windows.
        QTimer.singleShot(0, self._reveal)

    def show_error(self, message: str) -> None:
        """Error raised before any job (invalid input): shown at the same place."""

        self._result = None
        self._result_text = message
        self._details = ""
        self._refresh()

    def clear_result(self) -> None:
        self._result = None
        self._result_text = ""
        self._details = ""
        self._refresh()

    def set_continue_tools(self, entries: Sequence[tuple[str, str]]) -> None:
        """Tools offered by `Continue with…`, as (key, visible title), in home order."""

        self._continue_entries = tuple(entries)
        self._continue_menu.clear()
        for key, title in self._continue_entries:
            action = self._continue_menu.addAction(title)
            action.setData(key)
        self._refresh()

    def is_running(self) -> bool:
        return self._running

    def result_pdf(self) -> Path | None:
        result = self._result
        if result is None or not result.success or len(result.output_files) != 1:
            return None
        path = result.output_files[0]
        return path if path.suffix.lower() == ".pdf" and path.is_file() else None

    def set_locale(self, locale: Locale) -> None:
        self._locale = locale
        if self._action_key:
            self._action.setText(tr(self._action_key, locale).upper())
        self._action.setToolTip(tr("tool.action.shortcut", locale))
        self._cancel.setText(tr("button.cancel", locale))
        self._open_pdf.setText(tr("result.open_pdf", locale))
        self._open_folder.setText(tr("result.open_folder", locale))
        self._continue.setText(tr("result.continue_with", locale))
        self._details = self._result_details()
        self._refresh()

    def _refresh(self) -> None:
        busy = self._running
        self._action.setEnabled(not busy and not self._blocker)
        self._blocker_label.setText(self._blocker)
        self._blocker_label.setVisible(bool(self._blocker) and not busy)
        self._cancel.setVisible(busy)
        succeeded = self._result is not None and self._result.success
        shown = "\n".join(part for part in (self._result_text, self._details) if part)
        self._result_label.setText(shown if succeeded else "")
        self._result_label.setVisible(succeeded and bool(self._result_text) and not busy)
        failed = not succeeded and bool(self._result_text)
        self._error_label.setText(self._result_text if failed else "")
        self._error_label.setVisible(failed and not busy)
        has_pdf = not busy and self.result_pdf() is not None
        has_files = not busy and succeeded and bool(self._result and self._result.output_files)
        self._open_pdf.setVisible(has_pdf)
        self._open_folder.setVisible(has_files)
        self._continue.setVisible(has_pdf and bool(self._continue_entries))
        self._result_actions.setVisible(has_files)
        self._result_actions.update_direction()
        ready = not busy and not self._blocker and not succeeded
        # "Reduce animations" can change without a theme change: read it at
        # every state update, as the pages did (Codex review).
        self._cue.set_reduce_motion(_app_reduce_motion())
        self._cue.set_target(self._action if ready else None)

    def _result_details(self) -> str:
        result = self._result
        if result is None or not result.success or not result.output_files:
            return ""
        folder = result.output_files[0].parent
        folder_text = tr(
            "job.success.details_folder", self._locale, folder=folder.name or str(folder)
        )
        if len(result.output_files) != 1:
            return folder_text
        parts: list[str] = []
        if self._show_size:
            with contextlib.suppress(OSError):
                parts.append(format_bytes(result.output_files[0].stat().st_size, self._locale))
        if self._page_count is not None and self._page_count > 0:
            parts.append(page_count_text(self._page_count, self._locale))
        parts.append(folder_text)
        return " · ".join(parts)

    def _continue_triggered(self, action: QAction) -> None:
        path = self.result_pdf()
        key = action.data()
        if path is not None and isinstance(key, str) and key:
            self.continue_requested.emit(path, key)

    def _reveal(self) -> None:
        parent = self.parentWidget()
        while parent is not None and not isinstance(parent, QScrollArea):
            parent = parent.parentWidget()
        if isinstance(parent, QScrollArea):
            parent.ensureWidgetVisible(self, 0, SPACING["lg"])

    def request_action(self) -> None:
        """Click or Ctrl+Enter: emits only while the action is allowed."""

        if self._action.isEnabled():
            self.action_requested.emit()

    def _request_open_pdf(self) -> None:
        path = self.result_pdf()
        if path is not None:
            self.open_pdf_requested.emit(path)

    def _open_result_folder(self) -> None:
        result = self._result
        if result is None or not result.success or not result.output_files:
            return
        folder = result.output_files[0].parent
        if folder.is_dir():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))


class _ResultActions(QWidget):
    """Result buttons in one row, stacked when the column is too narrow (side column)."""

    def __init__(self, buttons: Sequence[QWidget], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._buttons = tuple(buttons)
        self._layout = QBoxLayout(QBoxLayout.Direction.LeftToRight, self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(SPACING["sm"])
        for button in self._buttons:
            self._layout.addWidget(button)
        self._layout.addStretch(1)

    def update_direction(self) -> None:
        visible = [button for button in self._buttons if not button.isHidden()]
        needed = sum(button.sizeHint().width() for button in visible)
        needed += self._layout.spacing() * max(0, len(visible) - 1)
        width = self.width() if self.width() > 0 else needed
        direction = (
            QBoxLayout.Direction.TopToBottom if needed > width else QBoxLayout.Direction.LeftToRight
        )
        if self._layout.direction() != direction:
            self._layout.setDirection(direction)

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self.update_direction()


def install_page_tool_layout(
    page: QWidget,
    *,
    back: QWidget,
    header: Sequence[QWidget],
    pages: QWidget,
    side_panels: Sequence[QWidget],
) -> QScrollArea:
    """Lay out a page-editing tool (UX contract, rule 1 "page editing" adaptation).

    Back sits alone on the first row, then `header` (description, source input).
    Below, the source `pages` fill the left; `side_panels` (settings, output,
    action and result) are stacked in that order in a fixed right column. The
    whole content scrolls only when the window is too small for it.
    """

    side = QWidget()
    side.setObjectName("PageToolSideColumn")
    side.setFixedWidth(SIZES["tool_side_column"])
    side_layout = QVBoxLayout(side)
    side_layout.setContentsMargins(0, 0, 0, 0)
    side_layout.setSpacing(SPACING["lg"])
    for panel in side_panels:
        side_layout.addWidget(panel)
    side_layout.addStretch(1)

    body = QHBoxLayout()
    body.setSpacing(SPACING["lg"])
    body.addWidget(pages, 1)
    body.addWidget(side)

    navigation = QHBoxLayout()
    navigation.addWidget(back)
    navigation.addStretch(1)

    content = QWidget()
    layout = QVBoxLayout(content)
    layout.setContentsMargins(SPACING["xxl"], SPACING["xl"], SPACING["xxl"], SPACING["xl"])
    layout.setSpacing(SPACING["md"])
    layout.addLayout(navigation)
    for widget in header:
        layout.addWidget(widget)
    layout.addLayout(body, 1)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QScrollArea.Shape.NoFrame)
    scroll.setWidget(content)
    root = QVBoxLayout(page)
    root.setContentsMargins(0, 0, 0, 0)
    root.addWidget(scroll)
    return scroll
