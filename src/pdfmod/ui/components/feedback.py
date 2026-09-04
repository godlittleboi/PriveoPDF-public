from __future__ import annotations

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QLabel, QMainWindow, QMessageBox, QProgressBar, QVBoxLayout, QWidget

from pdfmod.ui.components.cards import SurfacePanel


def show_info(parent: QWidget, title: str, message: str) -> None:
    dialog = QMessageBox(parent)
    dialog.setIcon(QMessageBox.Icon.Information)
    dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
    dialog.setWindowTitle(title)
    dialog.setText(message)
    _strip_standard_button_icons(dialog)
    dialog.exec()


def show_error(parent: QWidget, title: str, message: str, detail: str = "") -> None:
    dialog = QMessageBox(parent)
    dialog.setIcon(QMessageBox.Icon.Warning)
    dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
    dialog.setWindowTitle(title)
    dialog.setText(message)
    if detail:
        dialog.setInformativeText("Un detail technique est disponible ci-dessous.")
        dialog.setDetailedText(detail)
    _strip_standard_button_icons(dialog)
    dialog.exec()


def show_status_message(parent: QWidget, message: str, timeout_ms: int = 5000) -> None:
    window = parent.window()
    if isinstance(window, QMainWindow):
        window.statusBar().showMessage(message, timeout_ms)
        return
    show_info(parent, "Information", message)


def _strip_standard_button_icons(dialog: QMessageBox) -> None:
    empty_icon = QIcon()
    for button in dialog.buttons():
        button.setIcon(empty_icon)


class ProgressOverlay(SurfacePanel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(role="info", parent=parent)
        self.setObjectName("ProgressOverlay")
        self.setVisible(False)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)
        self._label = QLabel("Traitement local en cours...")
        self._label.setObjectName("SectionTitle")
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        layout.addWidget(self._label)
        layout.addWidget(self._progress)

    def show_message(self, message: str = "Traitement local en cours...") -> None:
        self._label.setText(message)
        self.setVisible(True)

    def hide_overlay(self) -> None:
        self.setVisible(False)
