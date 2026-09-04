from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QDialog, QLabel, QVBoxLayout, QWidget

from pdfmod.app.settings import AppSettings
from pdfmod.ui.components.buttons import PrimaryButton
from pdfmod.ui.components.cards import SurfacePanel
from pdfmod.ui.i18n import SUPPORTED_LANGUAGE_OPTIONS, Locale, tr


class FirstRunDialog(QDialog):
    preferences_applied = Signal(str)

    def __init__(self, settings: AppSettings, parent=None) -> None:  # noqa: ANN001
        super().__init__(parent)
        self._settings = settings
        self._locale: Locale = settings.language()
        self.setModal(True)
        self.resize(560, 320)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        self._title = QLabel()
        self._title.setObjectName("PageTitle")
        layout.addWidget(self._title)

        self._subtitle = QLabel()
        self._subtitle.setObjectName("HelpText")
        self._subtitle.setWordWrap(True)
        layout.addWidget(self._subtitle)

        panel = SurfacePanel(role="primary")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(18, 18, 18, 18)
        panel_layout.setSpacing(12)

        self._language_combo = QComboBox()
        for option in SUPPORTED_LANGUAGE_OPTIONS:
            self._language_combo.addItem(tr(option.label_key, self._locale), option.locale)
        self._set_combo_value(self._language_combo, self._settings.language())
        self._language_combo.currentIndexChanged.connect(self._preview_locale)
        self._language_row = _labeled_row("", self._language_combo)
        panel_layout.addWidget(self._language_row)

        layout.addWidget(panel)
        layout.addStretch(1)

        self._start_button = PrimaryButton()
        self._start_button.clicked.connect(self._apply)
        layout.addWidget(self._start_button)

        self._set_locale(self._locale)

    def _preview_locale(self) -> None:
        self._set_locale(self._language_combo.currentData())

    def _set_locale(self, locale: Locale) -> None:
        self._locale = locale
        self.setWindowTitle(tr("first_run.title", locale))
        self._title.setText(tr("first_run.title", locale))
        self._subtitle.setText(tr("first_run.subtitle", locale))
        _set_row_label(self._language_row, tr("first_run.language", locale))
        self._start_button.setText(tr("first_run.start", locale))

    def _apply(self) -> None:
        locale = self._language_combo.currentData()
        self._settings.set_language(locale)
        self._settings.set_initial_setup_completed(True)
        self._settings.sync()
        self.preferences_applied.emit(locale)
        self.accept()

    def _set_combo_value(self, combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)


def _labeled_row(label_text: str, widget: QWidget) -> QWidget:
    row = QWidget()
    layout = QVBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    label = QLabel(label_text)
    label.setObjectName("SectionTitle")
    layout.addWidget(label)
    layout.addWidget(widget)
    return row


def _set_row_label(row: QWidget, label_text: str) -> None:
    labels = row.findChildren(QLabel)
    if labels:
        labels[0].setText(label_text)
