"""« Ajouter une langue » for Recognize text: pick a language by name, install its
system model with the desktop installer, see it appear.

The dialog lists every Tesseract language package known to PriveoPDF
(`priveopdf.domain.ocr_languages`), greys the installed ones, and hands the
chosen package to the system installer, which asks the user's password and
downloads it. PriveoPDF itself connects to nothing. While the dialog is open,
the model folder is watched: the language is reported as installed as soon as
its file exists. Without a desktop opener, the terminal command is shown with a
copy button.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from priveopdf.app.package_install import (
    install_command,
    open_system_installer,
    system_installer_available,
)
from priveopdf.domain.jobs import OCR_TESSDATA
from priveopdf.domain.ocr_languages import OCR_LANGUAGE_NAMES, ocr_language_name
from priveopdf.ui.components.buttons import GhostButton, PrimaryButton, SecondaryButton
from priveopdf.ui.i18n import Locale, tr
from priveopdf.ui.theme.tokens import SPACING

_WATCH_INTERVAL_MS = 2000


class OcrLanguageDialog(QDialog):
    """Emits `installed` with the model code each time a chosen model appears."""

    installed = Signal(str)

    def __init__(
        self,
        locale: Locale,
        installed_codes: tuple[str, ...],
        *,
        tessdata: Path = OCR_TESSDATA,
        installer_available: bool | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._locale = locale
        self._tessdata = tessdata
        self._installed = set(installed_codes)
        self._installer = (
            system_installer_available() if installer_available is None else installer_available
        )
        self._pending: str | None = None
        self.setWindowTitle(tr("ocr.add.title", locale))
        self.setModal(True)
        self.resize(520, 560)

        self._search = QLineEdit()
        self._search.setObjectName("OcrLanguageSearch")
        self._search.setPlaceholderText(tr("ocr.add.search", locale))
        self._search.textChanged.connect(self._filter)
        self._list = QListWidget()
        self._list.setObjectName("OcrLanguageList")
        self._list.currentItemChanged.connect(lambda *_: self._update_state())
        self._list.itemDoubleClicked.connect(lambda _item: self._install())
        for code in sorted(OCR_LANGUAGE_NAMES, key=lambda c: ocr_language_name(c, locale)):
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, code)
            self._list.addItem(item)
        self._status = QLabel()
        self._status.setObjectName("HelpText")
        self._status.setWordWrap(True)
        self._status.setTextFormat(Qt.TextFormat.PlainText)
        self._status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._install_button = PrimaryButton(tr("ocr.add.install", locale))
        self._install_button.setObjectName("OcrLanguageInstall")
        self._install_button.clicked.connect(self._install)
        self._copy_button = SecondaryButton(tr("ocr.add.copy", locale))
        self._copy_button.setObjectName("OcrLanguageCopy")
        self._copy_button.clicked.connect(self._copy_command)
        close_button = GhostButton(tr("options.close", locale))
        close_button.clicked.connect(self.accept)

        intro = QLabel(tr("ocr.add.intro", locale))
        intro.setObjectName("HelpText")
        intro.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*(SPACING["lg"],) * 4)
        layout.setSpacing(SPACING["md"])
        layout.addWidget(intro)
        layout.addWidget(self._search)
        layout.addWidget(self._list, 1)
        layout.addWidget(self._status)
        buttons = QHBoxLayout()
        buttons.addWidget(self._install_button)
        buttons.addWidget(self._copy_button)
        buttons.addStretch(1)
        buttons.addWidget(close_button)
        layout.addLayout(buttons)

        self._watch = QTimer(self)
        self._watch.setInterval(_WATCH_INTERVAL_MS)
        self._watch.timeout.connect(self._check_pending)
        self._refresh_items()
        self._update_state()

    def done(self, result: int) -> None:  # noqa: N802 - Qt override
        self._watch.stop()
        self._pending = None
        super().done(result)

    # Selection -------------------------------------------------------------

    def selected_code(self) -> str | None:
        item = self._list.currentItem()
        return None if item is None else str(item.data(Qt.ItemDataRole.UserRole))

    def _refresh_items(self) -> None:
        for index in range(self._list.count()):
            item = self._list.item(index)
            code = str(item.data(Qt.ItemDataRole.UserRole))
            name = ocr_language_name(code, self._locale)
            if code in self._installed:
                item.setText(tr("ocr.add.item_installed", self._locale, name=name, code=code))
            else:
                item.setText(tr("ocr.add.item", self._locale, name=name, code=code))

    def _filter(self, text: str) -> None:
        needle = text.strip().casefold()
        for index in range(self._list.count()):
            item = self._list.item(index)
            item.setHidden(bool(needle) and needle not in item.text().casefold())

    def _update_state(self) -> None:
        code = self.selected_code()
        chosen = code is not None and code not in self._installed
        self._install_button.setEnabled(chosen and self._installer)
        self._install_button.setVisible(self._installer)
        self._copy_button.setEnabled(chosen)
        if code is None:
            self._status.setText(tr("ocr.add.choose", self._locale))
        elif code in self._installed:
            self._status.setText(
                tr("ocr.add.already", self._locale, name=ocr_language_name(code, self._locale))
            )
        elif self._pending == code:
            self._status.setText(tr("ocr.add.waiting", self._locale, command=install_command(code)))
        elif self._installer:
            self._status.setText(tr("ocr.add.ready", self._locale, command=install_command(code)))
        else:
            self._status.setText(tr("ocr.add.manual", self._locale, command=install_command(code)))

    # Install ---------------------------------------------------------------

    def _install(self) -> None:
        code = self.selected_code()
        if code is None or code in self._installed or not self._installer:
            return
        if not open_system_installer(code):
            self._installer = False
            self._update_state()
            return
        self._pending = code
        self._watch.start()
        self._update_state()

    def _copy_command(self) -> None:
        code = self.selected_code()
        if code is not None:
            QApplication.clipboard().setText(install_command(code))
            self._status.setText(tr("ocr.add.copied", self._locale, command=install_command(code)))

    def _check_pending(self) -> None:
        code = self._pending
        if code is None:
            self._watch.stop()
            return
        if (self._tessdata / f"{code}.traineddata").is_file():
            self._pending = None
            self._watch.stop()
            self._installed.add(code)
            self._refresh_items()
            self._status.setText(
                tr("ocr.add.done", self._locale, name=ocr_language_name(code, self._locale))
            )
            self._install_button.setEnabled(False)
            self.installed.emit(code)
