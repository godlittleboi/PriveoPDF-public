"""Source check on load (UX contract, logic L4).

Each tool checks its source as soon as it is loaded, with the existing isolated
worker (page count). An unusable PDF is reported under the source, before any
click: protected by a password, or unreadable and damaged. The tool keeps its
action disabled with the same reason.

A digitally signed PDF is reported the same way by the tools that can produce
a copy without its signatures (`unsigned_copy=True`): the action stays
disabled until the user ticks the choice, never pre-selected.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from priveopdf.domain.errors import EncryptedPdfError, InvalidPdfError
from priveopdf.ui.components.buttons import SecondaryButton
from priveopdf.ui.i18n import Locale, tr
from priveopdf.ui.theme.tokens import SPACING
from priveopdf.workers.job_runner import PageCountResult, QtPageCountRunner

SourceProblem = Literal["", "protected", "invalid", "not_protected"]

# A missing or inaccessible file (`input_path_error`) is not a damaged PDF: the
# job reports it with its own message.
_INVALID_CODES = frozenset({InvalidPdfError.technical_code})
_Signature = tuple[int, int] | None


def source_problem(result: PageCountResult, *, unlock_tool: bool = False) -> SourceProblem:
    """Problem shown for a page-count result.

    The count opens the PDF without password: success means "not encrypted",
    `encrypted_pdf` means a password is needed (an empty user password, with
    usage restrictions only, opens and is processed).
    Other failures (sandbox, timeout) are not the PDF's fault: no problem is
    shown and the job reports its own error.
    """

    if result.success:
        return "not_protected" if unlock_tool else ""
    code = result.technical_detail
    if code == EncryptedPdfError.technical_code:
        return "" if unlock_tool else "protected"
    if code in _INVALID_CODES:
        return "invalid"
    return ""


def source_problem_text(problem: SourceProblem, locale: Locale, name: str = "") -> str:
    """Message of a problem; `name` names the file when the tool has several sources."""

    if not problem:
        return ""
    if name and problem in {"protected", "invalid"}:
        return tr(f"source.{problem}_named", locale, name=name)
    return tr(f"source.{problem}", locale)


def _signature(path: Path) -> _Signature:
    try:
        status = path.stat()
    except OSError:
        return None
    return (status.st_mtime_ns, status.st_size)


class SourceCheck(QWidget):
    """Message under the source, with `Déverrouiller PDF` for a protected PDF.

    `check()` counts the pages of the listed sources in the isolated worker, one
    at a time. Pages that already count their pages call `record()` instead.
    `changed` is emitted whenever the shown problem changes.
    """

    changed = Signal()
    unlock_requested = Signal(object)
    checked = Signal(object)

    def __init__(
        self,
        locale: Locale = "en",
        *,
        unlock_tool: bool = False,
        name_files: bool = False,
        unsigned_copy: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("SourceCheck")
        self._locale = locale
        self._unlock_tool = unlock_tool
        self._name_files = name_files
        self._unsigned_copy = unsigned_copy
        self._sources: tuple[Path, ...] = ()
        self._problems: dict[Path, tuple[_Signature, SourceProblem]] = {}
        self._signed: dict[Path, bool] = {}
        self._queue: list[Path] = []
        self._runner: QtPageCountRunner | None = None
        self._running_path: Path | None = None
        self._running_signature: _Signature = None
        self._closing = False
        self._message = QLabel()
        self._message.setObjectName("ErrorText")
        self._message.setWordWrap(True)
        self._unlock = SecondaryButton()
        self._unlock.clicked.connect(self._request_unlock)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self._unlock)
        row.addStretch(1)
        self._signed_message = QLabel()
        self._signed_message.setObjectName("WarningText")
        self._signed_message.setWordWrap(True)
        self._unsigned_choice = QCheckBox()
        self._unsigned_choice.setObjectName("UnsignedCopyChoice")
        self._unsigned_choice.toggled.connect(lambda _checked: self.changed.emit())
        self._unsigned_help = QLabel()
        self._unsigned_help.setObjectName("HelpText")
        self._unsigned_help.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING["sm"])
        layout.addWidget(self._message)
        layout.addLayout(row)
        layout.addWidget(self._signed_message)
        layout.addWidget(self._unsigned_choice)
        layout.addWidget(self._unsigned_help)
        self.set_locale(locale)

    def check(self, sources: Sequence[Path]) -> None:
        """Show the problems of `sources` and count those not known yet.

        A source already checked is counted again when its file changed (a PDF
        unlocked in place keeps its path).
        """

        self._sources = tuple(Path(path) for path in sources)
        self._queue = [path for path in self._queue if path in self._sources]
        for path in self._sources:
            if path in self._problems and not self.is_stale(path):
                continue
            if path not in self._queue and path != self._running_path:
                self._queue.append(path)
        self._start_next()
        self._render()

    def is_stale(self, path: Path) -> bool:
        """True when `path` was checked and its file has changed since."""

        known = self._problems.get(Path(path))
        return known is not None and known[0] != _signature(Path(path))

    def blocker_text(self) -> str:
        """Reason that keeps the action disabled: the problem, the signed PDF
        without the user's choice, or the check in progress."""

        problem = self.problem_text()
        if problem:
            return problem
        if self.is_checking():
            return tr("source.checking", self._locale)
        if self.signed() and not self._unsigned_choice.isChecked():
            return tr("source.signed_blocker", self._locale)
        return ""

    def signed(self) -> bool:
        """True when a current source carries a digital signature (tools with
        `unsigned_copy` only; the others let the job report it)."""

        return self._unsigned_copy and any(self._signed.get(path, False) for path in self._sources)

    def unsigned_copy_allowed(self) -> bool:
        """The user's choice to produce the copy without its signatures."""

        return self.signed() and self._unsigned_choice.isChecked()

    def set_sources(self, sources: Sequence[Path]) -> None:
        """Sources currently used by the tool; results for others are ignored."""

        self._sources = tuple(Path(path) for path in sources)
        self._queue = [path for path in self._queue if path in self._sources]
        self._render()

    def record(self, result: PageCountResult) -> None:
        """Page-count result obtained by the tool itself."""

        self._store(result, _signature(result.pdf_path))
        self._render()

    def record_problem(self, path: Path, problem: SourceProblem) -> None:
        self._problems[Path(path)] = (_signature(Path(path)), problem)
        self._render()

    def sources(self) -> tuple[Path, ...]:
        return self._sources

    def clear(self) -> None:
        self.set_sources(())

    def problem(self) -> SourceProblem:
        """Problem of the first unusable source, in the tool's order."""

        found = self._found_problems()
        return found[0][1] if found else ""

    def problem_of(self, path: Path) -> SourceProblem:
        """Known problem of one source, "" when none or not checked yet."""

        known = self._problems.get(Path(path))
        return known[1] if known is not None else ""

    def protected_path(self) -> Path | None:
        """First protected source: the one `Unlock PDF` opens."""

        return next((path for path, kind in self._found_problems() if kind == "protected"), None)

    def problem_text(self) -> str:
        """One line per unusable source, so a list shows every file in question."""

        return "\n".join(
            source_problem_text(kind, self._locale, path.name if self._name_files else "")
            for path, kind in self._found_problems()
        )

    def is_checking(self) -> bool:
        return self._running_path is not None or bool(self._queue)

    def set_locale(self, locale: Locale) -> None:
        self._locale = locale
        self._unlock.setText(tr("source.unlock", locale))
        self._signed_message.setText(tr("source.signed", locale))
        self._unsigned_choice.setText(tr("source.signed_choice", locale))
        self._unsigned_help.setText(tr("source.signed_help", locale))
        self._render()

    def shutdown(self) -> bool:
        """Window closing: no further check starts, the running one is cancelled."""

        self._closing = True
        self._queue.clear()
        runner = self._runner
        return runner.shutdown() if runner is not None else True

    def _found_problems(self) -> list[tuple[Path, SourceProblem]]:
        found: list[tuple[Path, SourceProblem]] = []
        for path in self._sources:
            known = self._problems.get(path)
            if known is not None and known[1]:
                found.append((path, known[1]))
        return found

    def _start_next(self) -> None:
        if self._closing or self._running_path is not None or not self._queue:
            return
        path = self._queue.pop(0)
        if self._runner is None:
            runner = QtPageCountRunner(self)
            runner.finished.connect(self._count_finished)
            # B22: a page deleted during a check must not destroy a running QThread.
            # `destroyed` is emitted before the children are deleted.
            self.destroyed.connect(lambda *_args: runner.shutdown())
            self._runner = runner
        self._running_path = path
        # Taken before counting: a file rewritten meanwhile is counted again later.
        self._running_signature = _signature(path)
        self._runner.start(path)

    def _count_finished(self, result: PageCountResult) -> None:
        self._running_path = None
        self._store(result, self._running_signature)
        self.checked.emit(result)
        self._start_next()
        self._render()

    def _store(self, result: PageCountResult, signature: _Signature) -> None:
        # Every answer is kept for this file version, a sandbox or timeout failure
        # included (no problem shown, the job reports it): forgetting it made
        # each workspace refresh count the file again, endlessly.
        self._problems[result.pdf_path] = (
            signature,
            source_problem(result, unlock_tool=self._unlock_tool),
        )
        previous = self._signed.get(result.pdf_path, False)
        self._signed[result.pdf_path] = result.success and result.signed
        if previous != self._signed[result.pdf_path]:
            # Rule 5 spirit: the choice is never carried over to another file.
            self._unsigned_choice.setChecked(False)

    def _render(self) -> None:
        text = self.problem_text()
        self._message.setText(text)
        # An empty error label would still draw its danger border.
        self._message.setVisible(bool(text))
        self._unlock.setVisible(self.protected_path() is not None)
        signed = not text and self.signed()
        for widget in (self._signed_message, self._unsigned_choice, self._unsigned_help):
            widget.setVisible(signed)
        shown = bool(text) or signed
        # A parentless widget shown would become a window: show only once placed.
        if not shown or self.parentWidget() is not None:
            self.setVisible(shown)
        self.changed.emit()

    def _request_unlock(self) -> None:
        path = self.protected_path()
        if path is not None:
            self.unlock_requested.emit(path)
