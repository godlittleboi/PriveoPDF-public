from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QMimeData, Qt, QTimer, Signal
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from pdfmod.ui.components.buttons import PrimaryButton
from pdfmod.ui.components.cards import PixelFrame
from pdfmod.ui.i18n import Locale, tr
from pdfmod.ui.theme.animations import set_transient_property
from pdfmod.ui.theme.tokens import SIZES


def _refresh_style(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


class PdfDropZone(PixelFrame):
    files_dropped = Signal(list)
    browse_requested = Signal()

    def __init__(
        self,
        multiple: bool = True,
        title: str | None = None,
        subtitle: str | None = None,
        locale: Locale = "en",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__("primary", parent)
        self._multiple = multiple
        self._locale = locale
        self.setObjectName("DropZone")
        self.setAcceptDrops(True)
        self.setMinimumHeight(SIZES["dropzone_min"])
        self.setProperty("dragOver", False)
        self.setProperty("accepted", False)
        self.setProperty("rejected", False)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(8)

        self._title_label = QLabel()
        self._title_label.setObjectName("SectionTitle")
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._subtitle_label = QLabel()
        self._subtitle_label.setObjectName("HelpText")
        self._subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._browse_button = PrimaryButton()
        self._browse_button.clicked.connect(self.browse_requested.emit)
        self._state_label = QLabel("")
        self._state_label.setObjectName("DropZoneState")
        self._state_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.set_text(
            title or tr("dropzone.title" if multiple else "dropzone.single_title", locale),
            subtitle or tr("dropzone.subtitle" if multiple else "dropzone.single_subtitle", locale),
        )
        self.set_locale(locale)

        layout.addWidget(self._title_label)
        layout.addWidget(self._subtitle_label)
        layout.addSpacing(6)
        layout.addWidget(self._browse_button, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._state_label)

    def dragEnterEvent(self, event) -> None:  # noqa: ANN001
        if self._has_pdf_urls(event.mimeData()):
            self._set_drag_over(True)
            event.acceptProposedAction()
            return
        event.ignore()

    def dragMoveEvent(self, event) -> None:  # noqa: ANN001
        if self._has_pdf_urls(event.mimeData()):
            event.acceptProposedAction()
            return
        event.ignore()

    def dragLeaveEvent(self, event) -> None:  # noqa: ANN001
        self._set_drag_over(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event) -> None:  # noqa: ANN001
        self._set_drag_over(False)
        paths = [Path(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile()]
        pdfs = [path for path in paths if path.suffix.lower() == ".pdf"]
        if not self._multiple:
            pdfs = pdfs[:1]
        if pdfs:
            self.files_dropped.emit(pdfs)
            set_transient_property(self, "accepted", True, False)
            self._show_state(
                tr("dropzone.accepted", self._locale, count=len(pdfs)),
                "success",
            )
            event.acceptProposedAction()
            return
        set_transient_property(self, "rejected", True, False)
        self._show_state(tr("dropzone.rejected", self._locale), "danger")
        event.ignore()

    def _set_drag_over(self, drag_over: bool) -> None:
        self.setProperty("dragOver", drag_over)
        self.set_pixel_raised(drag_over)
        _refresh_style(self)

    def _has_pdf_urls(self, mime_data: QMimeData) -> bool:
        return any(
            url.isLocalFile() and Path(url.toLocalFile()).suffix.lower() == ".pdf"
            for url in mime_data.urls()
        )

    def _show_state(self, message: str, status: str) -> None:
        self._state_label.setProperty("status", status)
        self._state_label.setText(message)
        _refresh_style(self._state_label)

        def clear_state() -> None:
            self._state_label.setText("")
            self._state_label.setProperty("status", "info")
            _refresh_style(self._state_label)

        QTimer.singleShot(2200, clear_state)

    def set_text(self, title: str, subtitle: str) -> None:
        self._title_label.setText(title.upper())
        self._subtitle_label.setText(subtitle)
        self._subtitle_label.setVisible(bool(subtitle))

    def set_locale(self, locale: Locale) -> None:
        self._locale = locale
        self.set_text(
            tr("dropzone.title" if self._multiple else "dropzone.single_title", locale),
            tr("dropzone.subtitle" if self._multiple else "dropzone.single_subtitle", locale),
        )
        self._browse_button.setText(tr("dropzone.browse", locale))
