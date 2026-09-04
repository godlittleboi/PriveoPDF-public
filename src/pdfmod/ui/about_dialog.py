from __future__ import annotations

from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QVBoxLayout

from pdfmod.app.app_info import get_display_version
from pdfmod.ui.components.buttons import GhostButton
from pdfmod.ui.components.cards import SurfacePanel
from pdfmod.ui.i18n import Locale, tr


class AboutDialog(QDialog):
    def __init__(
        self,
        locale: Locale,
        update_status_text: str = "",
        parent=None,  # noqa: ANN001
    ) -> None:
        super().__init__(parent)
        self._locale = locale
        self.setWindowTitle(tr("about.title", locale))
        self.setModal(True)
        self.resize(460, 300)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        title = QLabel(tr("app.name", locale))
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        panel = SurfacePanel(role="info")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(18, 18, 18, 18)
        panel_layout.setSpacing(8)

        version = QLabel(get_display_version(locale))
        version.setObjectName("SectionTitle")
        update_status = QLabel(update_status_text)
        update_status.setObjectName("HelpText")
        update_status.setWordWrap(True)
        promise = QLabel(tr("about.product_promise", locale))
        promise.setObjectName("HelpText")
        promise.setWordWrap(True)
        no_account = QLabel(tr("about.no_account", locale))
        no_account.setObjectName("HelpText")
        documents_stay = QLabel(tr("about.documents_stay", locale))
        documents_stay.setObjectName("HelpText")
        documents_stay.setWordWrap(True)
        license_label = QLabel(tr("about.license", locale))
        license_label.setObjectName("HelpText")
        license_label.setWordWrap(True)
        third_party_label = QLabel(tr("about.third_party", locale))
        third_party_label.setObjectName("HelpText")
        third_party_label.setWordWrap(True)
        copyright_label = QLabel(tr("about.copyright", locale))
        copyright_label.setObjectName("HelpText")
        panel_layout.addWidget(version)
        if update_status_text:
            panel_layout.addWidget(update_status)
        panel_layout.addWidget(promise)
        panel_layout.addWidget(no_account)
        panel_layout.addWidget(documents_stay)
        panel_layout.addWidget(license_label)
        panel_layout.addWidget(third_party_label)
        panel_layout.addWidget(copyright_label)

        layout.addWidget(panel)
        layout.addStretch(1)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        close_button = GhostButton(tr("options.close", locale))
        close_button.clicked.connect(self.reject)
        button_row.addWidget(close_button)
        layout.addLayout(button_row)
