from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from pdfmod.ui.components import GhostButton, SurfacePanel
from pdfmod.ui.i18n import Locale, tr
from pdfmod.ui.tool_specs import ToolSpec


class PendingToolPage(QWidget):
    back_requested = Signal()

    def __init__(self, spec: ToolSpec, locale: Locale = "en") -> None:
        super().__init__()
        self._spec = spec
        self._locale = locale

        self._description_label = QLabel()
        self._description_label.setObjectName("HelpText")
        self._description_label.setWordWrap(True)

        self._back_button = GhostButton()
        self._back_button.clicked.connect(self.back_requested.emit)

        toolbar = QHBoxLayout()
        toolbar.addWidget(self._back_button)
        toolbar.addStretch(1)

        panel = SurfacePanel(role="warning")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(18, 18, 18, 18)
        panel_layout.setSpacing(12)
        self._badge_label = QLabel()
        self._badge_label.setObjectName("PendingBadge")
        self._message_label = QLabel()
        self._message_label.setObjectName("HelpText")
        self._message_label.setWordWrap(True)
        panel_layout.addWidget(self._badge_label)
        panel_layout.addWidget(self._message_label)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 30, 32, 30)
        layout.setSpacing(16)
        layout.addWidget(self._description_label)
        layout.addLayout(toolbar)
        layout.addWidget(panel)
        layout.addStretch(1)
        self.set_locale(locale)

    def set_locale(self, locale: Locale) -> None:
        self._locale = locale
        self._description_label.setText(tr(self._spec.description_key, locale))
        self._back_button.setText(tr("button.back", locale))
        self._badge_label.setText(tr("pending.badge", locale))
        self._message_label.setText(tr("pending.local_message", locale))
