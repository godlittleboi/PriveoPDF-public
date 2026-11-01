from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QStandardPaths, Signal
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QVBoxLayout, QWidget

from priveopdf.app.app_info import PROJECT_ROOT, is_beta_runtime, is_dev_runtime
from priveopdf.app.settings import AppSettings
from priveopdf.ui.components.buttons import SecondaryButton
from priveopdf.ui.components.dropzone import PdfDropZone
from priveopdf.ui.i18n import Locale, tr

OPEN_DIR_ENV = "PRIVEOPDF_OPEN_DIR"


def open_dialog_directory(settings: AppSettings) -> str:
    """Start folder of the PDF open dialogs (issue 311).

    Dev and Beta start from `PRIVEOPDF_OPEN_DIR` (absolute, set outside the
    repository) or the clone's `dev_corpus`. Otherwise: last folder used, then
    Documents. An unusable value silently falls back to the next one.
    """

    candidates: list[Path] = []
    if is_dev_runtime() or is_beta_runtime():
        configured = os.environ.get(OPEN_DIR_ENV, "").strip()
        if configured:
            candidates.append(Path(configured))
        candidates.append(PROJECT_ROOT / "dev_corpus")
    last = settings.last_open_dir()
    if last is not None:
        candidates.append(last)
    documents = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
    if documents:
        candidates.append(Path(documents))
    for candidate in candidates:
        if candidate.is_absolute() and candidate.is_dir():
            return str(candidate)
    return ""


def choose_pdf_files(
    parent: QWidget, *, multiple: bool, locale: Locale, settings: AppSettings
) -> list[Path]:
    """Open the system file dialog directly and remember the folder used."""

    title = tr("pdf_input.dialog_multi" if multiple else "pdf_input.dialog_single", locale)
    start = open_dialog_directory(settings)
    if multiple:
        files, _ = QFileDialog.getOpenFileNames(parent, title, start, "PDF (*.pdf)")
        chosen = [Path(file) for file in files]
    else:
        file_name, _ = QFileDialog.getOpenFileName(parent, title, start, "PDF (*.pdf)")
        chosen = [Path(file_name)] if file_name else []
    pdfs = [path for path in chosen if path.suffix.lower() == ".pdf"]
    if pdfs:
        settings.set_last_open_dir(pdfs[0].parent)
    return pdfs


class PdfInputPanel(QWidget):
    paths_selected = Signal(list)

    def __init__(
        self,
        multiple: bool = False,
        locale: Locale = "en",
        parent: QWidget | None = None,
        settings: AppSettings | None = None,
    ) -> None:
        super().__init__(parent)
        self._multiple = multiple
        self._locale = locale
        self._loaded = False
        self._settings = settings

        self._dropzone = PdfDropZone(multiple=multiple, locale=locale)
        self._dropzone.files_dropped.connect(self._emit_paths)
        self._dropzone.browse_requested.connect(self._browse_directly)

        self._compact_button = SecondaryButton()
        self._compact_button.clicked.connect(self._browse_directly)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.addWidget(self._compact_button)
        button_row.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self._dropzone)
        layout.addLayout(button_row)

        self.set_locale(locale)
        self.set_loaded(False)

    def set_loaded(self, loaded: bool) -> None:
        self._loaded = loaded
        self._dropzone.setVisible(not loaded)
        self._compact_button.setVisible(loaded)

    def set_locale(self, locale: Locale) -> None:
        self._locale = locale
        self._dropzone.set_locale(locale)
        self._dropzone.set_text(self._empty_title(), "")
        self._compact_button.setText(
            tr("pdf_input.add_pdf" if self._multiple else "pdf_input.change_pdf", locale)
        )

    def accept_paths(self, paths: list[Path]) -> None:
        """PDFs dropped anywhere on the window are routed here (UX contract, rule 2)."""

        if self.isEnabled():
            self._emit_paths(paths)

    def _empty_title(self) -> str:
        key = "pdf_input.empty_multi" if self._multiple else "pdf_input.empty_single"
        return tr(key, self._locale)

    def _browse_directly(self) -> None:
        settings = self._settings or AppSettings()
        self._emit_paths(
            choose_pdf_files(self, multiple=self._multiple, locale=self._locale, settings=settings)
        )

    def _emit_paths(self, paths: list[Path]) -> None:
        pdfs = [Path(path) for path in paths if Path(path).suffix.lower() == ".pdf"]
        if not self._multiple:
            pdfs = pdfs[:1]
        if pdfs:
            self.paths_selected.emit(pdfs)
