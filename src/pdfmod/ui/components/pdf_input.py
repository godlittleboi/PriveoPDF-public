from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QDialog, QFileDialog, QHBoxLayout, QVBoxLayout, QWidget

from pdfmod.ui.components.buttons import SecondaryButton
from pdfmod.ui.components.dropzone import PdfDropZone
from pdfmod.ui.i18n import Locale, tr


class PdfOpenDialog(QDialog):
    def __init__(
        self,
        multiple: bool = False,
        locale: Locale = "en",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._multiple = multiple
        self._locale = locale
        self._paths: list[Path] = []
        self.setModal(True)
        self.setWindowTitle(self._dialog_title())

        self._dropzone = PdfDropZone(multiple=multiple, locale=locale)
        self._dropzone.files_dropped.connect(self._accept_paths)
        self._dropzone.browse_requested.connect(self._browse)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        layout.addWidget(self._dropzone)
        self.set_locale(locale)

    def selected_paths(self) -> list[Path]:
        return list(self._paths)

    def set_locale(self, locale: Locale) -> None:
        self._locale = locale
        self.setWindowTitle(self._dialog_title())
        self._dropzone.set_locale(locale)
        self._dropzone.set_text(self._empty_title(), "")

    def _dialog_title(self) -> str:
        key = "pdf_input.dialog_multi" if self._multiple else "pdf_input.dialog_single"
        return tr(key, self._locale)

    def _empty_title(self) -> str:
        key = "pdf_input.empty_multi" if self._multiple else "pdf_input.empty_single"
        return tr(key, self._locale)

    def _browse(self) -> None:
        if self._multiple:
            files, _ = QFileDialog.getOpenFileNames(
                self,
                self._dialog_title(),
                "",
                "PDF (*.pdf)",
            )
            self._accept_paths([Path(file) for file in files])
            return

        file_name, _ = QFileDialog.getOpenFileName(
            self,
            self._dialog_title(),
            "",
            "PDF (*.pdf)",
        )
        if file_name:
            self._accept_paths([Path(file_name)])

    def _accept_paths(self, paths: list[Path]) -> None:
        pdfs = [Path(path) for path in paths if Path(path).suffix.lower() == ".pdf"]
        if not self._multiple:
            pdfs = pdfs[:1]
        if not pdfs:
            return
        self._paths = pdfs
        self.accept()


class PdfInputPanel(QWidget):
    paths_selected = Signal(list)

    def __init__(
        self,
        multiple: bool = False,
        locale: Locale = "en",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._multiple = multiple
        self._locale = locale
        self._loaded = False

        self._dropzone = PdfDropZone(multiple=multiple, locale=locale)
        self._dropzone.files_dropped.connect(self._emit_paths)
        self._dropzone.browse_requested.connect(self._browse_directly)

        self._compact_button = SecondaryButton()
        self._compact_button.clicked.connect(self._open_dialog)

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

    def _empty_title(self) -> str:
        key = "pdf_input.empty_multi" if self._multiple else "pdf_input.empty_single"
        return tr(key, self._locale)

    def _browse_directly(self) -> None:
        if self._multiple:
            files, _ = QFileDialog.getOpenFileNames(
                self,
                tr("pdf_input.dialog_multi", self._locale),
                "",
                "PDF (*.pdf)",
            )
            self._emit_paths([Path(file) for file in files])
            return
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            tr("pdf_input.dialog_single", self._locale),
            "",
            "PDF (*.pdf)",
        )
        if file_name:
            self._emit_paths([Path(file_name)])

    def _open_dialog(self) -> None:
        dialog = PdfOpenDialog(self._multiple, self._locale, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._emit_paths(dialog.selected_paths())

    def _emit_paths(self, paths: list[Path]) -> None:
        pdfs = [Path(path) for path in paths if Path(path).suffix.lower() == ".pdf"]
        if not self._multiple:
            pdfs = pdfs[:1]
        if pdfs:
            self.paths_selected.emit(pdfs)
