from __future__ import annotations

from contextlib import suppress
from pathlib import Path

from PySide6.QtCore import QEvent, QPoint, QRect, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from pdfmod.ui.components.page_thumbnails import (
    THUMBNAIL_GRID_SIZE,
    THUMBNAIL_ICON_BOUNDS,
    PdfPageThumbnailGrid,
    thumbnail_placeholder_icon,
)
from pdfmod.ui.i18n import Locale, tr
from pdfmod.ui.theme.tokens import SPACING

DOCUMENT_PAGE_ROW_HEIGHT = THUMBNAIL_GRID_SIZE.height()
DOCUMENT_PAGES_FIRST_PAGE_PANEL_HEIGHT = DOCUMENT_PAGE_ROW_HEIGHT + 80
DOCUMENT_PAGES_MULTI_PAGE_PANEL_HEIGHT = DOCUMENT_PAGE_ROW_HEIGHT + 152


class DocumentPagesPanel(QWidget):
    page_clicked = Signal(int)

    def __init__(
        self,
        *,
        locale: Locale = "en",
        max_cached_thumbnails: int = 24,
        batch_size: int = 8,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("DocumentPagesPanel")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._locale = locale
        self._active_page: int | None = None
        self._scroll_area: QScrollArea | None = None
        self._rows: dict[int, QWidget] = {}
        self._buttons: dict[int, QToolButton] = {}

        self._thumbnail_grid = PdfPageThumbnailGrid(
            mode="preview_only",
            layout_mode="horizontal_strip",
            locale=locale,
            max_cached_thumbnails=max_cached_thumbnails,
            batch_size=batch_size,
            parent=self,
        )
        self._thumbnail_grid.thumbnail_ready.connect(self._thumbnail_ready)
        self._thumbnail_grid.hide()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING["sm"])
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._layout = layout

    def thumbnail_grid(self) -> PdfPageThumbnailGrid:
        return self._thumbnail_grid

    def source_page_count(self) -> int:
        return self._thumbnail_grid.source_page_count()

    def set_scroll_area(self, scroll_area: QScrollArea) -> None:
        if self._scroll_area is not None:
            self._scroll_area.viewport().removeEventFilter(self)
            with suppress(RuntimeError, TypeError):
                self._scroll_area.verticalScrollBar().valueChanged.disconnect(
                    self._schedule_visible_thumbnail_requests
                )
        self._scroll_area = scroll_area
        scroll_area.viewport().installEventFilter(self)
        scroll_area.verticalScrollBar().valueChanged.connect(
            self._schedule_visible_thumbnail_requests
        )

    def set_locale(self, locale: Locale) -> None:
        self._locale = locale
        self._thumbnail_grid.set_locale(locale)
        for page_number, button in self._buttons.items():
            label = tr("thumbnails.page_label", locale, page=page_number)
            button.setText(label)
            button.setToolTip(tr("thumbnails.page_tooltip", locale, page=page_number))
            button.setAccessibleName(label)

    def set_document(self, path: Path, page_count: int) -> None:
        self.clear_document(close_document=False)
        self._thumbnail_grid.set_document(path, page_count)
        for page_number in range(1, max(0, page_count) + 1):
            self._add_page_row(page_number)
        self._schedule_visible_thumbnail_requests()

    def clear_document(self, *, close_document: bool = True) -> None:
        self._active_page = None
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self._rows.clear()
        self._buttons.clear()
        self._thumbnail_grid.clear_document(close_document=close_document)

    def set_active_page(self, page_number: int) -> None:
        self._active_page = int(page_number)
        for candidate, button in self._buttons.items():
            active = candidate == self._active_page
            button.setChecked(active)
            button.setProperty("active", active)
            _refresh_style(button)
        if self._active_page in self._buttons:
            self._thumbnail_grid.set_active_page(self._active_page)
            self._thumbnail_grid.ensure_thumbnail(self._active_page)
            self._ensure_active_visible()

    def eventFilter(self, watched, event) -> bool:  # noqa: ANN001, N802
        if (
            self._scroll_area is not None
            and watched is self._scroll_area.viewport()
            and event.type() in {QEvent.Type.Resize, QEvent.Type.Show}
        ):
            self._schedule_visible_thumbnail_requests()
        return super().eventFilter(watched, event)

    def _add_page_row(self, page_number: int) -> None:
        row = QWidget()
        row.setObjectName("DocumentPageRow")
        row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        row.setMinimumHeight(DOCUMENT_PAGE_ROW_HEIGHT)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(0)

        button = QToolButton()
        button.setObjectName("DocumentPageItem")
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        button.setIcon(thumbnail_placeholder_icon("loading"))
        button.setIconSize(THUMBNAIL_ICON_BOUNDS)
        button.setCheckable(True)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        button.setMinimumSize(THUMBNAIL_GRID_SIZE)
        button.setMaximumWidth(THUMBNAIL_GRID_SIZE.width() + SPACING["xl"])
        button.clicked.connect(
            lambda _checked=False, selected_page=page_number: self.page_clicked.emit(selected_page)
        )
        row_layout.addStretch(1)
        row_layout.addWidget(button, 0, Qt.AlignmentFlag.AlignCenter)
        row_layout.addStretch(1)
        self._layout.addWidget(row, 0)
        self._rows[page_number] = row
        self._buttons[page_number] = button
        self.set_locale(self._locale)

    def _thumbnail_ready(self, page_number: int) -> None:
        self._refresh_thumbnail_icon(page_number)

    def _refresh_thumbnail_icon(self, page_number: int) -> None:
        button = self._buttons.get(page_number)
        if button is None:
            return
        icon = self._thumbnail_grid.thumbnail_icon(page_number)
        if icon is not None:
            button.setIcon(icon)

    def _schedule_visible_thumbnail_requests(self) -> None:
        QTimer.singleShot(0, self._request_visible_thumbnails)

    def _request_visible_thumbnails(self) -> None:
        if not self._buttons:
            return
        pages = self._visible_pages()
        if not pages:
            pages = tuple(self._buttons)[:8]
        if self._active_page is not None:
            pages = tuple(dict.fromkeys((*pages, self._active_page)))
        for page_number in pages:
            self._thumbnail_grid.ensure_thumbnail(page_number)
            self._refresh_thumbnail_icon(page_number)

    def _visible_pages(self) -> tuple[int, ...]:
        if self._scroll_area is None:
            return ()
        viewport = self._scroll_area.viewport()
        viewport_rect = viewport.rect().adjusted(
            0,
            -THUMBNAIL_GRID_SIZE.height(),
            0,
            THUMBNAIL_GRID_SIZE.height(),
        )
        visible_pages: list[int] = []
        for page_number, row in self._rows.items():
            top_left = row.mapTo(viewport, QPoint(0, 0))
            row_rect = QRect(top_left, row.size())
            if viewport_rect.intersects(row_rect):
                visible_pages.append(page_number)
        return tuple(visible_pages)

    def _ensure_active_visible(self) -> None:
        if self._scroll_area is None or self._active_page is None:
            return
        button = self._buttons.get(self._active_page)
        if button is not None:
            self._scroll_area.ensureWidgetVisible(button, SPACING["sm"], SPACING["sm"])


def _refresh_style(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()
