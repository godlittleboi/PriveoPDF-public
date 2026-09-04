from __future__ import annotations

import heapq
import itertools
import logging
from collections import OrderedDict
from collections.abc import Iterator, MutableMapping
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from PySide6.QtCore import (
    QAbstractListModel,
    QEvent,
    QItemSelectionModel,
    QMimeData,
    QModelIndex,
    QPoint,
    QRect,
    QSize,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QColor, QDrag, QIcon, QImage, QPainter, QPen, QPixmap
from PySide6.QtPdf import QPdfDocument, QPdfDocumentRenderOptions, QPdfPageRenderer
from PySide6.QtWidgets import (
    QApplication,
    QListView,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QStyledItemDelegate,
    QVBoxLayout,
    QWidget,
)

from pdfmod.domain.page_ranges import PageRange
from pdfmod.ui.components.buttons import set_button_role
from pdfmod.ui.i18n import Locale, tr
from pdfmod.ui.theme.tokens import PALETTES, ThemeTokens

ThumbnailMode = Literal["preview_only", "selection", "ordered", "split"]
ThumbnailLayoutMode = Literal[
    "horizontal_strip",
    "grid_reorder",
    "selection_grid",
    "vertical_strip",
]
ThumbnailRenderState = Literal["loading", "ready", "error"]

LOGGER = logging.getLogger(__name__)

PAGE_NUMBER_ROLE = Qt.ItemDataRole.UserRole + 1
THUMBNAIL_STATE_ROLE = Qt.ItemDataRole.UserRole + 2
THUMBNAIL_MARK_ROLE = Qt.ItemDataRole.UserRole + 3

THUMBNAIL_ICON_BOUNDS = QSize(104, 148)
THUMBNAIL_RENDER_BOUNDS = QSize(156, 222)
THUMBNAIL_GRID_SIZE = QSize(132, 196)
THUMBNAIL_LIST_HEIGHT = 224
THUMBNAIL_GRID_VISIBLE_ROWS = 3
THUMBNAIL_GRID_MAX_COLUMNS = 10
THUMBNAIL_GRID_HEIGHT = THUMBNAIL_GRID_SIZE.height() * THUMBNAIL_GRID_VISIBLE_ROWS + 28
DELETED_MARK_LINE_WIDTH = 2
DELETED_MARK_BORDER_WIDTH = 2
PAGE_REORDER_MIME = "application/x-priveopdf-page-reorder"
DEFAULT_THUMBNAIL_CACHE_BYTES = 64 * 1024 * 1024
MAX_THUMBNAIL_RENDERS_IN_FLIGHT = 4
THUMBNAIL_SCROLL_DEBOUNCE_MS = 45


class ThumbnailListWidget(QListWidget):
    manual_order_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ordered_mode = False
        self._external_drag_enabled = False
        self._insertion_index: int | None = None
        self._layout_mode: ThumbnailLayoutMode = "horizontal_strip"

    def set_ordered_mode(self, ordered: bool) -> None:
        self._ordered_mode = ordered
        self._clear_insertion()

    def set_layout_mode(self, layout_mode: ThumbnailLayoutMode) -> None:
        self._layout_mode = layout_mode
        self._clear_insertion()

    def set_external_drag_enabled(self, enabled: bool) -> None:
        self._external_drag_enabled = enabled

    def mimeData(self, items: list[QListWidgetItem]) -> QMimeData:  # noqa: N802
        mime_data = super().mimeData(items)
        pages = [
            str(int(item.data(PAGE_NUMBER_ROLE)))
            for item in items
            if item.data(PAGE_NUMBER_ROLE) is not None
        ]
        if pages:
            mime_data.setText(f"application/x-priveopdf-pages:{','.join(pages)}")
        if self._ordered_mode and len(items) == 1:
            reorder_mime = self._reorder_mime_data_for_item(items[0])
            if reorder_mime is not None:
                mime_data.setData(PAGE_REORDER_MIME, reorder_mime.data(PAGE_REORDER_MIME))
        return mime_data

    def insertion_index_for_position(self, pos: QPoint) -> int | None:
        return self._insertion_index_for_pos(pos)

    def move_page_to_insertion(self, page_number: int, insertion_index: int) -> bool:
        current_order = self._page_order()
        try:
            source_row = current_order.index(int(page_number))
        except ValueError:
            return False
        next_order = reordered_pages_for_insertion(current_order, source_row, insertion_index)
        if next_order is None:
            return False
        if next_order != current_order:
            self._rebuild_from_order(next_order)
            self._set_current_page(int(page_number))
            self.manual_order_changed.emit()
        return True

    def startDrag(self, supported_actions: Qt.DropAction) -> None:  # noqa: N802
        if not self._ordered_mode:
            super().startDrag(supported_actions)
            return

        item = self.currentItem()
        if item is None or item.data(PAGE_NUMBER_ROLE) is None:
            super().startDrag(supported_actions)
            return

        mime_data = self._reorder_mime_data_for_item(item)
        if mime_data is None:
            return

        drag = QDrag(self)
        drag.setMimeData(mime_data)
        pixmap = item.icon().pixmap(self.iconSize())
        if not pixmap.isNull():
            drag.setPixmap(pixmap)
            drag.setHotSpot(QPoint(pixmap.width() // 2, pixmap.height() // 2))
        drag.exec(Qt.DropAction.MoveAction, Qt.DropAction.MoveAction)

    def viewportEvent(self, event) -> bool:  # noqa: ANN001, N802
        if event.type() == QEvent.Type.DragEnter:
            self.dragEnterEvent(event)
            return event.isAccepted()
        if event.type() == QEvent.Type.DragMove:
            self.dragMoveEvent(event)
            return event.isAccepted()
        if event.type() == QEvent.Type.Drop:
            self.dropEvent(event)
            return event.isAccepted()
        if event.type() == QEvent.Type.DragLeave:
            self.dragLeaveEvent(event)
            return event.isAccepted()
        return super().viewportEvent(event)

    def dragEnterEvent(self, event) -> None:  # noqa: ANN001
        if self._ordered_mode and self._is_internal_reorder_drag(event):
            self._accept_reorder_event(event)
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:  # noqa: ANN001
        if not self._ordered_mode or not self._is_internal_reorder_drag(event):
            super().dragMoveEvent(event)
            return
        insertion_index = self._insertion_index_for_pos(_event_position(event))
        if insertion_index is None:
            self._clear_insertion()
            event.ignore()
            return
        self._set_insertion_index(insertion_index)
        self._accept_reorder_event(event)

    def dragLeaveEvent(self, event) -> None:  # noqa: ANN001
        self._clear_insertion()
        super().dragLeaveEvent(event)

    def dropEvent(self, event) -> None:  # noqa: ANN001
        if not self._ordered_mode or not self._is_internal_reorder_drag(event):
            super().dropEvent(event)
            return
        payload = _reorder_payload_from_mime(event.mimeData())
        insertion_index = self._insertion_index_for_pos(_event_position(event))
        if payload is None or insertion_index is None:
            self._clear_insertion()
            event.ignore()
            return

        _source_row, moved_page = payload
        if not self.move_page_to_insertion(moved_page, insertion_index):
            self._clear_insertion()
            event.ignore()
            return
        self._clear_insertion()
        self._accept_reorder_event(event)

    def paintEvent(self, event) -> None:  # noqa: ANN001
        super().paintEvent(event)
        self._paint_deleted_marks()
        if self._insertion_index is None:
            return
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        if self._layout_mode == "grid_reorder":
            rect = self._indicator_rect(self._insertion_index)
            if rect is None:
                return
            pen = QPen(_indicator_color(), 2, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawLine(rect.topLeft(), rect.bottomLeft())
            return

        x = self._indicator_x(self._insertion_index)
        if x is None:
            return
        painter.fillRect(x - 2, 12, 4, max(0, self.viewport().height() - 24), _indicator_color())

    def _paint_deleted_marks(self) -> None:
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        color = _mark_foreground("deleted")
        overlay = QColor(_mark_background("deleted"))
        overlay.setAlpha(80)
        for index in range(self.count()):
            item = self.item(index)
            if item.data(THUMBNAIL_MARK_ROLE) != "deleted":
                continue
            rect = self.visualItemRect(item).adjusted(6, 6, -6, -6)
            if rect.isNull() or not self.viewport().rect().intersects(rect):
                continue
            painter.fillRect(rect, overlay)
            painter.setPen(QPen(color, DELETED_MARK_LINE_WIDTH, Qt.PenStyle.SolidLine))
            painter.drawLine(rect.topLeft(), rect.bottomRight())
            painter.drawLine(rect.topRight(), rect.bottomLeft())
            painter.setPen(QPen(color, DELETED_MARK_BORDER_WIDTH, Qt.PenStyle.SolidLine))
            painter.drawRect(rect)
        painter.end()

    def _insertion_index_for_pos(self, pos: QPoint) -> int | None:
        if self.count() == 0:
            return 0
        item = self.itemAt(pos)
        if item is not None:
            rect = self.visualItemRect(item)
            index = self.row(item)
            return index if pos.x() < rect.center().x() else index + 1

        if self._layout_mode == "grid_reorder":
            return self._grid_insertion_index_for_empty_pos(pos)

        last = self.item(self.count() - 1)
        if last is None:
            return None
        last_rect = self.visualItemRect(last)
        if pos.x() > last_rect.right() and last_rect.top() <= pos.y() <= last_rect.bottom():
            return self.count()
        return None

    def _grid_insertion_index_for_empty_pos(self, pos: QPoint) -> int | None:
        row_items: list[tuple[int, QRect]] = []
        for index in range(self.count()):
            item = self.item(index)
            rect = self.visualItemRect(item)
            if rect.isNull():
                continue
            if rect.top() <= pos.y() <= rect.bottom():
                row_items.append((index, rect))
        if not row_items:
            return None

        row_items.sort(key=lambda item: item[1].left())
        first_index, first_rect = row_items[0]
        last_index, last_rect = row_items[-1]
        if pos.x() < first_rect.left():
            return first_index
        if pos.x() > last_rect.right():
            return last_index + 1
        for left, right in itertools.pairwise(row_items):
            _left_index, left_rect = left
            right_index, right_rect = right
            if left_rect.right() < pos.x() < right_rect.left():
                return right_index
        return None

    def _indicator_x(self, insertion_index: int) -> int | None:
        if self.count() == 0:
            return 12
        if insertion_index >= self.count():
            last = self.item(self.count() - 1)
            if last is None:
                return None
            return self.visualItemRect(last).right() + 8
        item = self.item(insertion_index)
        if item is None:
            return None
        return self.visualItemRect(item).left() - 4

    def _indicator_rect(self, insertion_index: int) -> QRect | None:
        if self.count() == 0:
            return QRect(12, 12, 1, max(0, self.viewport().height() - 24))
        if insertion_index >= self.count():
            last = self.item(self.count() - 1)
            if last is None:
                return None
            rect = self.visualItemRect(last)
            return QRect(rect.right() + 6, rect.top() + 8, 1, max(1, rect.height() - 16))
        item = self.item(insertion_index)
        if item is None:
            return None
        rect = self.visualItemRect(item)
        return QRect(rect.left() - 6, rect.top() + 8, 1, max(1, rect.height() - 16))

    def _set_insertion_index(self, insertion_index: int) -> None:
        if self._insertion_index == insertion_index:
            return
        self._insertion_index = insertion_index
        self.viewport().update()

    def _clear_insertion(self) -> None:
        if self._insertion_index is None:
            return
        self._insertion_index = None
        self.viewport().update()

    def _reorder_mime_data_for_item(self, item: QListWidgetItem) -> QMimeData | None:
        page_number = item.data(PAGE_NUMBER_ROLE)
        if page_number is None:
            return None
        row = self.row(item)
        if row < 0:
            return None
        mime_data = QMimeData()
        mime_data.setData(PAGE_REORDER_MIME, f"{row},{int(page_number)}".encode("ascii"))
        mime_data.setText(f"application/x-priveopdf-pages:{int(page_number)}")
        return mime_data

    def _is_internal_reorder_drag(self, event) -> bool:  # noqa: ANN001
        source = event.source()
        if source not in {self, self.viewport()}:
            return False
        return _reorder_payload_from_mime(event.mimeData()) is not None

    def _accept_reorder_event(self, event) -> None:  # noqa: ANN001
        event.setDropAction(Qt.DropAction.MoveAction)
        event.accept()

    def _page_order(self) -> tuple[int, ...]:
        return tuple(
            int(self.item(index).data(PAGE_NUMBER_ROLE))
            for index in range(self.count())
            if self.item(index).data(PAGE_NUMBER_ROLE) is not None
        )

    def _rebuild_from_order(self, page_order: tuple[int, ...]) -> None:
        items_by_page: dict[int, QListWidgetItem] = {}
        while self.count():
            item = self.takeItem(0)
            page_number = item.data(PAGE_NUMBER_ROLE)
            if page_number is not None:
                items_by_page[int(page_number)] = item
        for page_number in page_order:
            item = items_by_page.get(int(page_number))
            if item is not None:
                self.addItem(item)

    def _set_current_page(self, page_number: int) -> None:
        for index in range(self.count()):
            item = self.item(index)
            if int(item.data(PAGE_NUMBER_ROLE)) == page_number:
                self.setCurrentItem(item)
                self.scrollToItem(item, QListWidget.ScrollHint.PositionAtCenter)
                return


class ThumbnailListModel(QAbstractListModel):
    """Compact page-occurrence model with sparse render state per source page."""

    def __init__(self, *, locale: Locale = "en", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._locale = locale
        self._mode: ThumbnailMode = "selection"
        self._external_drag_enabled = False
        self._pages: list[int] = []
        self._rows_by_page: dict[int, tuple[int, ...]] = {}
        self._states: dict[int, ThumbnailRenderState] = {}
        self._marks: dict[int, str] = {}
        self._icons: dict[int, QIcon] = {}

    def rowCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802
        return 0 if parent is not None and parent.isValid() else len(self._pages)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or not 0 <= index.row() < len(self._pages):
            return None
        page = self._pages[index.row()]
        state = self._states.get(page, "loading")
        mark = self._marks.get(page, "")
        if role == Qt.ItemDataRole.DisplayRole:
            return _thumbnail_item_text(page, state, mark, self._locale)
        if role == Qt.ItemDataRole.DecorationRole:
            return self._icons.get(page, _placeholder_icon(state))
        if role == Qt.ItemDataRole.ToolTipRole:
            return tr("thumbnails.page_tooltip", self._locale, page=page)
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return int(Qt.AlignmentFlag.AlignCenter)
        if role == Qt.ItemDataRole.AccessibleTextRole:
            return tr("thumbnails.page_label", self._locale, page=page)
        if role == PAGE_NUMBER_ROLE:
            return page
        if role == THUMBNAIL_STATE_ROLE:
            return state
        if role == THUMBNAIL_MARK_ROLE:
            return mark
        return None

    def setData(self, index: QModelIndex, value: Any, role: int) -> bool:  # noqa: N802
        if not index.isValid() or not 0 <= index.row() < len(self._pages):
            return False
        page = self._pages[index.row()]
        if role == THUMBNAIL_STATE_ROLE:
            self._states[page] = value
        elif role == THUMBNAIL_MARK_ROLE:
            if value:
                self._marks[page] = str(value)
            else:
                self._marks.pop(page, None)
        elif role == Qt.ItemDataRole.DecorationRole:
            if isinstance(value, QIcon) and not value.isNull():
                self._icons[page] = value
            else:
                self._icons.pop(page, None)
        else:
            return False
        changed_roles = [role, Qt.ItemDataRole.DisplayRole]
        for row in self.rows_for_page(page):
            changed = self.index(row, 0)
            self.dataChanged.emit(changed, changed, changed_roles)
        return True

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return (
                Qt.ItemFlag.ItemIsDropEnabled
                if self._mode == "ordered"
                else Qt.ItemFlag.NoItemFlags
            )
        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if self._mode == "ordered":
            flags |= Qt.ItemFlag.ItemIsDragEnabled | Qt.ItemFlag.ItemIsDropEnabled
        if self._external_drag_enabled:
            flags |= Qt.ItemFlag.ItemIsDragEnabled
        return flags

    def set_locale(self, locale: Locale) -> None:
        if self._locale == locale:
            return
        self._locale = locale
        if self._pages:
            self.dataChanged.emit(
                self.index(0, 0),
                self.index(len(self._pages) - 1, 0),
                [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole],
            )

    def set_mode(self, mode: ThumbnailMode, *, external_drag_enabled: bool = False) -> None:
        self._mode = mode
        self._external_drag_enabled = external_drag_enabled
        if self._pages:
            self.dataChanged.emit(self.index(0, 0), self.index(len(self._pages) - 1, 0), [])

    def reset_pages(self, count: int) -> None:
        self.beginResetModel()
        self._pages = list(range(1, max(0, count) + 1))
        self._reindex()
        self._states.clear()
        self._marks.clear()
        self._icons.clear()
        self.endResetModel()

    def clear(self) -> None:
        self.reset_pages(0)

    def append_item(self, item: QListWidgetItem | _ThumbnailItemAdapter) -> None:
        page_value = item.data(PAGE_NUMBER_ROLE)
        page = int(page_value) if page_value is not None else len(self._pages) + 1
        row = len(self._pages)
        self.beginInsertRows(QModelIndex(), row, row)
        self._pages.append(page)
        state = item.data(THUMBNAIL_STATE_ROLE)
        if state:
            self._states[page] = state
        mark = item.data(THUMBNAIL_MARK_ROLE)
        if mark:
            self._marks[page] = str(mark)
        icon = item.icon()
        if not icon.isNull():
            self._icons[page] = icon
        self._reindex()
        self.endInsertRows()

    def insert_detached(self, row: int, item: QListWidgetItem) -> None:
        page = int(item.data(PAGE_NUMBER_ROLE))
        row = max(0, min(row, len(self._pages)))
        self.beginInsertRows(QModelIndex(), row, row)
        self._pages.insert(row, page)
        self._states[page] = item.data(THUMBNAIL_STATE_ROLE) or "loading"
        mark = item.data(THUMBNAIL_MARK_ROLE)
        if mark:
            self._marks[page] = str(mark)
        icon = item.icon()
        if not icon.isNull():
            self._icons[page] = icon
        self._reindex()
        self.endInsertRows()

    def take_item(self, row: int) -> QListWidgetItem | None:
        if not 0 <= row < len(self._pages):
            return None
        self.beginRemoveRows(QModelIndex(), row, row)
        page = self._pages.pop(row)
        item = QListWidgetItem()
        item.setData(PAGE_NUMBER_ROLE, page)
        item.setData(THUMBNAIL_STATE_ROLE, self._states.get(page, "loading"))
        item.setData(THUMBNAIL_MARK_ROLE, self._marks.get(page, ""))
        item.setIcon(self._icons.get(page, QIcon()))
        if page not in self._pages:
            self._states.pop(page, None)
            self._marks.pop(page, None)
            self._icons.pop(page, None)
        self._reindex()
        self.endRemoveRows()
        return item

    def move_row_to_insertion(self, source_row: int, insertion_index: int) -> bool:
        target_row = target_row_for_insertion(source_row, insertion_index, len(self._pages))
        if source_row < 0 or target_row is None or target_row == source_row:
            return False
        destination = target_row + 1 if target_row > source_row else target_row
        self.beginMoveRows(QModelIndex(), source_row, source_row, QModelIndex(), destination)
        page = self._pages.pop(source_row)
        self._pages.insert(target_row, page)
        self._reindex()
        self.endMoveRows()
        return True

    def move_page_to_insertion(self, page_number: int, insertion_index: int) -> bool:
        return self.move_row_to_insertion(self.row_for_page(page_number), insertion_index)

    def duplicate_rows(self, rows: tuple[int, ...] | list[int]) -> tuple[int, ...]:
        selected = {int(row) for row in rows if 0 <= int(row) < len(self._pages)}
        if not selected:
            return ()
        next_pages: list[int] = []
        duplicate_rows: list[int] = []
        for row, page in enumerate(self._pages):
            next_pages.append(page)
            if row in selected:
                next_pages.append(page)
                duplicate_rows.append(len(next_pages) - 1)
        self.beginResetModel()
        self._pages = next_pages
        self._reindex()
        self.endResetModel()
        return tuple(duplicate_rows)

    def page_at(self, row: int) -> int | None:
        return self._pages[row] if 0 <= row < len(self._pages) else None

    def rows_for_page(self, page_number: int) -> tuple[int, ...]:
        return self._rows_by_page.get(int(page_number), ())

    def row_for_page(self, page_number: int) -> int:
        rows = self.rows_for_page(page_number)
        return rows[0] if rows else -1

    def page_order(self) -> tuple[int, ...]:
        return tuple(self._pages)

    def set_page_state(self, page: int, state: ThumbnailRenderState) -> None:
        row = self.row_for_page(page)
        if row >= 0:
            self.setData(self.index(row, 0), state, THUMBNAIL_STATE_ROLE)

    def set_page_mark(self, page: int, mark: str) -> None:
        row = self.row_for_page(page)
        if row >= 0:
            self.setData(self.index(row, 0), mark, THUMBNAIL_MARK_ROLE)

    def set_page_icon(self, page: int, icon: QIcon | None) -> None:
        row = self.row_for_page(page)
        if row >= 0:
            self.setData(self.index(row, 0), icon or QIcon(), Qt.ItemDataRole.DecorationRole)

    def _reindex(self) -> None:
        rows: dict[int, list[int]] = {}
        for row, page in enumerate(self._pages):
            rows.setdefault(page, []).append(row)
        self._rows_by_page = {page: tuple(page_rows) for page, page_rows in rows.items()}


class _ThumbnailItemAdapter:
    """Compatibility facade retaining the identity of one visible occurrence."""

    def __init__(self, model: ThumbnailListModel, row: int) -> None:
        self._model = model
        self._row = int(row)

    def _index(self) -> QModelIndex:
        return (
            self._model.index(self._row, 0)
            if 0 <= self._row < self._model.rowCount()
            else QModelIndex()
        )

    def row(self) -> int:
        return self._row

    def data(self, role: int) -> Any:
        return self._model.data(self._index(), role)

    def setData(self, role: int, value: Any) -> None:  # noqa: N802
        self._model.setData(self._index(), value, role)

    def setText(self, _text: str) -> None:  # noqa: N802
        return

    def setIcon(self, icon: QIcon) -> None:  # noqa: N802
        self._model.setData(self._index(), icon, Qt.ItemDataRole.DecorationRole)

    def setToolTip(self, _tooltip: str) -> None:  # noqa: N802
        return

    def setTextAlignment(self, _alignment: Qt.AlignmentFlag) -> None:  # noqa: N802
        return

    def setFlags(self, _flags: Qt.ItemFlag) -> None:  # noqa: N802
        return

    def icon(self) -> QIcon:
        value = self._model.data(self._index(), Qt.ItemDataRole.DecorationRole)
        return value if isinstance(value, QIcon) else QIcon()

    def flags(self) -> Qt.ItemFlag:
        return self._model.flags(self._index())


class ThumbnailDelegate(QStyledItemDelegate):
    def paint(self, painter: QPainter, option, index: QModelIndex) -> None:  # noqa: ANN001
        super().paint(painter, option, index)
        mark = index.data(THUMBNAIL_MARK_ROLE)
        if not mark:
            return
        rect = option.rect.adjusted(6, 6, -6, -6)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        if mark == "deleted":
            overlay = QColor(_mark_background("deleted"))
            overlay.setAlpha(80)
            painter.fillRect(rect, overlay)
            painter.setPen(QPen(_mark_foreground("deleted"), DELETED_MARK_LINE_WIDTH))
            painter.drawLine(rect.topLeft(), rect.bottomRight())
            painter.drawLine(rect.topRight(), rect.bottomLeft())
            painter.setPen(QPen(_mark_foreground("deleted"), DELETED_MARK_BORDER_WIDTH))
            painter.drawRect(rect)
        elif mark == "assigned":
            painter.setPen(QPen(_mark_foreground("assigned"), 3))
            painter.drawRect(rect)
        painter.restore()


class ThumbnailMemoryCache(MutableMapping[int, QIcon]):
    def __init__(self, max_bytes: int = DEFAULT_THUMBNAIL_CACHE_BYTES) -> None:
        if max_bytes < 1:
            raise ValueError("thumbnail cache size must be positive")
        self.max_bytes = int(max_bytes)
        self._entries: OrderedDict[int, tuple[QIcon, int]] = OrderedDict()
        self._bytes = 0

    @property
    def byte_size(self) -> int:
        return self._bytes

    def __getitem__(self, key: int) -> QIcon:
        icon, _size = self._entries[int(key)]
        self._entries.move_to_end(int(key))
        return icon

    def __setitem__(self, key: int, value: QIcon) -> None:
        pixmap = value.pixmap(THUMBNAIL_RENDER_BOUNDS)
        estimate = max(1, pixmap.width() * pixmap.height() * 4)
        self.put(int(key), value, estimate)

    def __delitem__(self, key: int) -> None:
        _icon, size = self._entries.pop(int(key))
        self._bytes -= size

    def __iter__(self) -> Iterator[int]:
        return iter(self._entries)

    def __len__(self) -> int:
        return len(self._entries)

    def get(self, key: int, default: QIcon | None = None) -> QIcon | None:
        try:
            return self[int(key)]
        except KeyError:
            return default

    def put(self, page: int, icon: QIcon, size_bytes: int) -> tuple[int, ...]:
        page = int(page)
        if page in self._entries:
            _old_icon, old_size = self._entries.pop(page)
            self._bytes -= old_size
        bounded_size = max(1, int(size_bytes))
        evicted: list[int] = []
        if bounded_size <= self.max_bytes:
            self._entries[page] = (icon, bounded_size)
            self._bytes += bounded_size
        while self._bytes > self.max_bytes and self._entries:
            evicted_page, (_evicted_icon, evicted_size) = self._entries.popitem(last=False)
            self._bytes -= evicted_size
            evicted.append(evicted_page)
        return tuple(evicted)

    def clear(self) -> None:
        self._entries.clear()
        self._bytes = 0


class ThumbnailRenderScheduler:
    def __init__(self, max_in_flight: int = MAX_THUMBNAIL_RENDERS_IN_FLIGHT) -> None:
        if not 1 <= max_in_flight <= MAX_THUMBNAIL_RENDERS_IN_FLIGHT:
            raise ValueError("thumbnail render concurrency must be between one and four")
        self.max_in_flight = int(max_in_flight)
        self._generation = 0
        self._sequence = itertools.count()
        self._queue: list[tuple[int, int, int, int]] = []
        self._queued: set[tuple[int, int]] = set()
        self._in_flight: dict[int, tuple[int, int]] = {}

    @property
    def in_flight_count(self) -> int:
        return len(self._in_flight)

    @property
    def pending_pages(self) -> set[int]:
        return {page for generation, page in self._queued if generation == self._generation} | {
            page for generation, page in self._in_flight.values() if generation == self._generation
        }

    def reset(self, generation: int) -> None:
        self._generation = int(generation)
        self._queue.clear()
        self._queued.clear()
        self._in_flight.clear()

    def enqueue(self, pages: tuple[int, ...] | list[int], *, priority: int) -> None:
        for page in pages:
            key = (self._generation, int(page))
            if key in self._queued or key in self._in_flight.values():
                continue
            heapq.heappush(
                self._queue,
                (int(priority), next(self._sequence), self._generation, int(page)),
            )
            self._queued.add(key)

    def start_available(self, request: Any) -> None:
        while len(self._in_flight) < self.max_in_flight and self._queue:
            _priority, _sequence, generation, page = heapq.heappop(self._queue)
            self._queued.discard((generation, page))
            if generation != self._generation:
                continue
            request_id = request(page)
            if request_id is not None:
                self._in_flight[int(request_id)] = (generation, page)

    def complete(self, request_id: int) -> tuple[int, int] | None:
        return self._in_flight.pop(int(request_id), None)

    def queued_pages_by_priority(self) -> tuple[int, ...]:
        return tuple(
            page
            for _priority, _sequence, generation, page in sorted(self._queue)
            if generation == self._generation
        )


class PdfPageThumbnailView(QListView):
    manual_order_changed = Signal()
    itemSelectionChanged = Signal()
    itemClicked = Signal(object)
    currentItemChanged = Signal(object, object)

    def __init__(self, model: ThumbnailListModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._thumbnail_model = model
        self._ordered_mode = False
        self._insertion_index: int | None = None
        self._layout_mode: ThumbnailLayoutMode = "horizontal_strip"
        self.setModel(model)
        self.setItemDelegate(ThumbnailDelegate(self))
        self.clicked.connect(lambda index: self.itemClicked.emit(self.item(index.row())))
        self.selectionModel().selectionChanged.connect(
            lambda *_args: self.itemSelectionChanged.emit()
        )
        self.selectionModel().currentChanged.connect(self._current_index_changed)

    def count(self) -> int:
        return self._thumbnail_model.rowCount()

    def item(self, row: int) -> _ThumbnailItemAdapter | None:
        return (
            _ThumbnailItemAdapter(self._thumbnail_model, row)
            if self._thumbnail_model.page_at(row) is not None
            else None
        )

    def addItem(self, item: QListWidgetItem | _ThumbnailItemAdapter) -> None:  # noqa: N802
        self._thumbnail_model.append_item(item)

    def insertItem(self, row: int, item: QListWidgetItem) -> None:  # noqa: N802
        self._thumbnail_model.insert_detached(row, item)

    def takeItem(self, row: int) -> QListWidgetItem | None:  # noqa: N802
        return self._thumbnail_model.take_item(row)

    def clear(self) -> None:
        self._thumbnail_model.clear()

    def row(self, item: _ThumbnailItemAdapter | QListWidgetItem) -> int:
        if isinstance(item, _ThumbnailItemAdapter):
            return item.row()
        page = item.data(PAGE_NUMBER_ROLE)
        return self._thumbnail_model.row_for_page(int(page)) if page is not None else -1

    def selectedItems(self) -> list[_ThumbnailItemAdapter]:  # noqa: N802
        selected: list[_ThumbnailItemAdapter] = []
        for index in self.selectionModel().selectedRows():
            item = self.item(index.row())
            if item is not None:
                selected.append(item)
        return selected

    def currentItem(self) -> _ThumbnailItemAdapter | None:  # noqa: N802
        return self.item(self.currentIndex().row()) if self.currentIndex().isValid() else None

    def currentRow(self) -> int:  # noqa: N802
        return self.currentIndex().row()

    def setCurrentRow(self, row: int) -> None:  # noqa: N802
        self.setCurrentIndex(self._thumbnail_model.index(row, 0))

    def setCurrentItem(self, item: _ThumbnailItemAdapter) -> None:  # noqa: N802
        row = self.row(item)
        if row >= 0:
            self.setCurrentIndex(self._thumbnail_model.index(row, 0))

    def visualItemRect(self, item: _ThumbnailItemAdapter) -> QRect:  # noqa: N802
        row = self.row(item)
        return self.visualRect(self._thumbnail_model.index(row, 0)) if row >= 0 else QRect()

    def itemAt(self, pos: QPoint) -> _ThumbnailItemAdapter | None:  # noqa: N802
        index = self.indexAt(pos)
        return self.item(index.row()) if index.isValid() else None

    def scrollToItem(
        self,
        item: _ThumbnailItemAdapter,
        hint: QListWidget.ScrollHint = QListWidget.ScrollHint.EnsureVisible,
    ) -> None:  # noqa: N802
        row = self.row(item)
        if row >= 0:
            self.scrollTo(self._thumbnail_model.index(row, 0), hint)

    def set_ordered_mode(self, ordered: bool) -> None:
        self._ordered_mode = ordered
        self._clear_insertion()

    def set_layout_mode(self, layout_mode: ThumbnailLayoutMode) -> None:
        self._layout_mode = layout_mode
        self._clear_insertion()

    def set_external_drag_enabled(self, _enabled: bool) -> None:
        return

    def mimeData(self, items: list[_ThumbnailItemAdapter]) -> QMimeData:  # noqa: N802
        mime_data = QMimeData()
        pages = [str(int(item.data(PAGE_NUMBER_ROLE))) for item in items if item is not None]
        if pages:
            mime_data.setText(f"application/x-priveopdf-pages:{','.join(pages)}")
        if self._ordered_mode and len(items) == 1:
            row = self.row(items[0])
            page = items[0].data(PAGE_NUMBER_ROLE)
            mime_data.setData(PAGE_REORDER_MIME, f"{row},{int(page)}".encode("ascii"))
        return mime_data

    def insertion_index_for_position(self, pos: QPoint) -> int | None:
        item = self.itemAt(pos)
        if item is not None:
            rect = self.visualItemRect(item)
            row = self.row(item)
            return row if pos.x() < rect.center().x() else row + 1
        rows = self.visible_rows()
        if not rows:
            return 0 if self.count() == 0 else None
        first, last = rows[0], rows[-1]
        first_rect = self.visualRect(self._thumbnail_model.index(first, 0))
        last_rect = self.visualRect(self._thumbnail_model.index(last, 0))
        row_rects = [self.visualRect(self._thumbnail_model.index(row, 0)) for row in rows]
        if pos.y() < min(rect.top() for rect in row_rects) or pos.y() > max(
            rect.bottom() for rect in row_rects
        ):
            return None
        if pos.y() < first_rect.top() or pos.x() < first_rect.left():
            return first
        if pos.y() <= last_rect.bottom() and pos.x() > last_rect.right():
            return last + 1
        for row in rows:
            rect = self.visualRect(self._thumbnail_model.index(row, 0))
            if rect.top() <= pos.y() <= rect.bottom() and pos.x() < rect.left():
                return row
        return None

    def move_row_to_insertion(self, source_row: int, insertion_index: int) -> bool:
        target_row = target_row_for_insertion(
            source_row, insertion_index, self._thumbnail_model.rowCount()
        )
        changed = self._thumbnail_model.move_row_to_insertion(source_row, insertion_index)
        if changed and target_row is not None:
            self.setCurrentRow(target_row)
            self.scrollTo(
                self._thumbnail_model.index(target_row, 0),
                QListView.ScrollHint.PositionAtCenter,
            )
            self.manual_order_changed.emit()
        return changed

    def move_page_to_insertion(self, page_number: int, insertion_index: int) -> bool:
        return self.move_row_to_insertion(
            self._thumbnail_model.row_for_page(page_number), insertion_index
        )

    def visible_rows(self) -> tuple[int, ...]:
        if self.count() == 0:
            return ()
        viewport = self.viewport().rect()
        grid = self.gridSize()
        step_x = max(1, grid.width() // 2)
        step_y = max(1, grid.height() // 2)
        rows: set[int] = set()
        for y in range(1, max(2, viewport.height()), step_y):
            for x in range(1, max(2, viewport.width()), step_x):
                index = self.indexAt(QPoint(x, y))
                if index.isValid():
                    rows.add(index.row())
        current = self.currentIndex()
        if not rows and current.isValid():
            rows.add(current.row())
        if not rows:
            rows.update(range(min(self.count(), THUMBNAIL_GRID_VISIBLE_ROWS * 2)))
        return tuple(sorted(rows))

    def startDrag(self, _supported_actions: Qt.DropAction) -> None:  # noqa: N802
        item = self.currentItem()
        if item is None:
            return
        drag_items = [item] if self._ordered_mode else self.selectedItems()
        if not drag_items:
            drag_items = [item]
        mime_data = self.mimeData(drag_items)
        drag = QDrag(self)
        drag.setMimeData(mime_data)
        pixmap = item.icon().pixmap(self.iconSize())
        if not pixmap.isNull():
            drag.setPixmap(pixmap)
        drag.exec(Qt.DropAction.MoveAction, Qt.DropAction.MoveAction)

    def dragEnterEvent(self, event) -> None:  # noqa: ANN001
        if self._ordered_mode and _reorder_payload_from_mime(event.mimeData()) is not None:
            event.setDropAction(Qt.DropAction.MoveAction)
            event.accept()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:  # noqa: ANN001
        if not self._ordered_mode or _reorder_payload_from_mime(event.mimeData()) is None:
            super().dragMoveEvent(event)
            return
        insertion = self.insertion_index_for_position(_event_position(event))
        if insertion is None:
            event.ignore()
            return
        self._insertion_index = insertion
        self.viewport().update()
        event.setDropAction(Qt.DropAction.MoveAction)
        event.accept()

    def dropEvent(self, event) -> None:  # noqa: ANN001
        payload = _reorder_payload_from_mime(event.mimeData())
        insertion = self.insertion_index_for_position(_event_position(event))
        if not self._ordered_mode or payload is None or insertion is None:
            event.ignore()
            return
        source_row, _page = payload
        if self.move_row_to_insertion(source_row, insertion):
            event.setDropAction(Qt.DropAction.MoveAction)
            event.accept()
        else:
            event.ignore()
        self._clear_insertion()

    def dragLeaveEvent(self, event) -> None:  # noqa: ANN001
        self._clear_insertion()
        super().dragLeaveEvent(event)

    def paintEvent(self, event) -> None:  # noqa: ANN001
        super().paintEvent(event)
        if self._insertion_index is None:
            return
        painter = QPainter(self.viewport())
        painter.setPen(QPen(_indicator_color(), 2, Qt.PenStyle.DashLine))
        row = min(self._insertion_index, max(0, self.count() - 1))
        rect = self.visualRect(self._thumbnail_model.index(row, 0))
        x = rect.right() + 6 if self._insertion_index >= self.count() else rect.left() - 6
        painter.drawLine(x, rect.top() + 6, x, rect.bottom() - 6)
        painter.end()

    def _current_index_changed(self, current: QModelIndex, previous: QModelIndex) -> None:
        current_item = self.item(current.row()) if current.isValid() else None
        previous_item = self.item(previous.row()) if previous.isValid() else None
        self.currentItemChanged.emit(current_item, previous_item)

    def _set_current_page(self, page_number: int) -> None:
        row = self._thumbnail_model.row_for_page(page_number)
        if row >= 0:
            self.setCurrentRow(row)
            self.scrollTo(
                self._thumbnail_model.index(row, 0),
                QListView.ScrollHint.PositionAtCenter,
            )

    def _clear_insertion(self) -> None:
        if self._insertion_index is not None:
            self._insertion_index = None
            self.viewport().update()


class PdfPageThumbnailGrid(QWidget):
    active_page_changed = Signal(int)
    page_clicked = Signal(int)
    selection_changed = Signal(tuple)
    order_changed = Signal(tuple)
    split_ranges_changed = Signal(tuple)
    thumbnail_ready = Signal(int)

    def __init__(
        self,
        mode: ThumbnailMode = "selection",
        layout_mode: ThumbnailLayoutMode = "horizontal_strip",
        locale: Locale = "en",
        max_cached_thumbnails: int = 20,
        batch_size: int = 12,
        cache_bytes: int = DEFAULT_THUMBNAIL_CACHE_BYTES,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._mode = mode
        self._layout_mode = layout_mode
        self._locale = locale
        self._batch_size = batch_size
        self._external_drag_enabled = False
        self._page_marks: dict[int, str] = {}
        self._requested_max_cached_thumbnails = max_cached_thumbnails
        self._max_cached_thumbnails = max_cached_thumbnails
        self._document_generation = 0
        self._rendered_pages = ThumbnailMemoryCache(cache_bytes)
        self._scheduler = ThumbnailRenderScheduler()
        self._pending_requests = self._scheduler._in_flight
        self._pending_pages = self._scheduler.pending_pages
        self._next_render_page = 0
        self._pending_page_count: int | None = None
        self._document_debug_id = ""
        self._source_page_count = 0

        self._document = QPdfDocument(self)
        self._document.statusChanged.connect(self._document_status_changed)
        self._renderer = QPdfPageRenderer(self)
        self._renderer.setDocument(self._document)
        self._renderer.pageRendered.connect(self._page_rendered)

        self._model = ThumbnailListModel(locale=locale, parent=self)
        self._list = PdfPageThumbnailView(self._model)
        self._list.setObjectName("ThumbnailList")
        self._list.setViewMode(QListWidget.ViewMode.IconMode)
        self._list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self._list.setFlow(QListView.Flow.LeftToRight)
        self._list.setMovement(QListWidget.Movement.Static)
        self._list.setWrapping(False)
        self._list.setUniformItemSizes(True)
        self._list.setIconSize(THUMBNAIL_ICON_BOUNDS)
        self._list.setGridSize(THUMBNAIL_GRID_SIZE)
        self._list.setMinimumHeight(THUMBNAIL_LIST_HEIGHT)
        self._list.setMaximumHeight(THUMBNAIL_LIST_HEIGHT)
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list.itemSelectionChanged.connect(self._emit_selection_state)
        self._list.itemClicked.connect(self._emit_clicked_page)
        self._list.currentItemChanged.connect(self._emit_active_page)
        self._list.manual_order_changed.connect(self._emit_order_state)
        self._viewport_debounce = QTimer(self)
        self._viewport_debounce.setSingleShot(True)
        self._viewport_debounce.setInterval(THUMBNAIL_SCROLL_DEBOUNCE_MS)
        self._viewport_debounce.timeout.connect(self._request_visible_thumbnails)
        self._list.horizontalScrollBar().valueChanged.connect(self._schedule_visible_thumbnails)
        self._list.verticalScrollBar().valueChanged.connect(self._schedule_visible_thumbnails)
        self._configure_mode()
        self._configure_layout()

        self._load_more_button = QPushButton()
        set_button_role(self._load_more_button, "secondary")
        self._load_more_button.clicked.connect(self.render_next_batch)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self._list)
        layout.addWidget(self._load_more_button)
        self.set_locale(locale)
        self._update_load_more_state()

    def set_locale(self, locale: Locale) -> None:
        self._locale = locale
        self._load_more_button.setText(tr("thumbnails.load_more", locale))
        self._model.set_locale(locale)

    def set_mode(self, mode: ThumbnailMode) -> None:
        self._mode = mode
        self._configure_mode()

    def set_layout_mode(self, layout_mode: ThumbnailLayoutMode) -> None:
        self._layout_mode = layout_mode
        self._configure_layout()
        self._update_load_more_state()
        self._request_initial_thumbnails()

    def set_external_drag_enabled(self, enabled: bool) -> None:
        self._external_drag_enabled = enabled
        self._list.set_external_drag_enabled(enabled)
        self._configure_mode()
        for index in range(self._list.count()):
            self._list.item(index).setFlags(self._item_flags())

    def thumbnail_icon(self, page_number: int) -> QIcon | None:
        return self._rendered_pages.get(int(page_number))

    def ensure_thumbnail(self, page_number: int) -> None:
        item = self._item_for_page(int(page_number))
        if item is None:
            return
        self._request_thumbnail(self._list.row(item))

    def has_duplicate_page_items(self) -> bool:
        pages = self.page_order()
        return len(pages) != len(set(pages))

    def source_page_count(self) -> int:
        return self._source_page_count

    def source_pages_are_exactly(self, page_count: int) -> bool:
        expected = tuple(range(1, page_count + 1))
        return self.source_page_count() == page_count and self.page_order() == expected

    def set_page_marks(self, pages: tuple[int, ...] | list[int], mark: str = "") -> None:
        marked_pages = {int(page) for page in pages}
        if mark:
            for page in marked_pages:
                self._page_marks[page] = mark
        else:
            for page in marked_pages:
                self._page_marks.pop(page, None)
        for page_number in marked_pages:
            self._model.set_page_mark(page_number, mark)
        self._list.viewport().update()

    def clear_page_marks(self) -> None:
        marked_pages = tuple(self._page_marks)
        self._page_marks.clear()
        for page_number in marked_pages:
            self._model.set_page_mark(page_number, "")
        self._list.viewport().update()

    def resizeEvent(self, event) -> None:  # noqa: ANN001
        super().resizeEvent(event)
        self._sync_vertical_grid_width()
        self._schedule_visible_thumbnails()

    def set_document(self, path: Path, page_count: int | None = None) -> None:
        self.clear_document(close_document=False)
        self._document_debug_id = _new_document_debug_id()
        self._pending_page_count = page_count
        self._document.close()
        error = self._document.load(str(path))
        if error != QPdfDocument.Error.None_:
            self._update_load_more_state()
            return

        if page_count is not None:
            self._populate_items(page_count)
        if self._document.status() == QPdfDocument.Status.Ready:
            self._document_ready()

    def clear_document(self, close_document: bool = True) -> None:
        self._document_generation += 1
        self._scheduler.reset(self._document_generation)
        self._pending_requests = self._scheduler._in_flight
        self._pending_pages = self._scheduler.pending_pages
        self._rendered_pages.clear()
        self._page_marks.clear()
        self._next_render_page = 0
        self._pending_page_count = None
        self._document_debug_id = ""
        self._source_page_count = 0
        self._model.clear()
        if close_document:
            self._document.close()
        self._update_load_more_state()

    def _document_ready(self) -> None:
        count = (
            self._pending_page_count
            if self._pending_page_count is not None
            else self._document.pageCount()
        )
        if self._list.count() == 0:
            self._populate_items(count)
        if self._list.count() > 0 and self._list.currentItem() is None:
            self._list.setCurrentRow(0)
        self._request_initial_thumbnails()
        self._emit_order_state()

    def _populate_items(self, count: int) -> None:
        self._source_page_count = max(0, int(count))
        self._model.reset_pages(count)
        self._model.set_mode(self._mode, external_drag_enabled=self._external_drag_enabled)
        self._sync_vertical_grid_width()

    def selected_pages(self) -> tuple[int, ...]:
        return tuple(
            sorted(
                int(item.data(PAGE_NUMBER_ROLE))
                for item in self._list.selectedItems()
                if item.data(PAGE_NUMBER_ROLE) is not None
            )
        )

    def active_page(self) -> int | None:
        item = self._list.currentItem()
        if item is None or item.data(PAGE_NUMBER_ROLE) is None:
            return None
        return int(item.data(PAGE_NUMBER_ROLE))

    def set_active_page(self, page_number: int) -> None:
        row = self._model.row_for_page(page_number)
        if row >= 0:
            self._list.setCurrentRow(row)
            item = self._list.item(row)
            if item is not None:
                self._list.scrollToItem(item, QListWidget.ScrollHint.PositionAtCenter)

    def page_order(self) -> tuple[int, ...]:
        return self._model.page_order()

    def range_expression(self) -> str:
        return pages_to_range_expression(self.selected_pages())

    def order_permutation(self) -> tuple[int, ...]:
        return ordered_pages_to_permutation(self.page_order(), self._source_page_count)

    def order_sequence(self) -> tuple[int, ...]:
        return ordered_pages_to_sequence(self.page_order(), self._source_page_count)

    def duplicate_selected(self) -> tuple[int, ...]:
        rows = tuple(index.row() for index in self._list.selectionModel().selectedRows())
        if not rows and self._list.currentRow() >= 0:
            rows = (self._list.currentRow(),)
        duplicates = self._model.duplicate_rows(rows)
        if not duplicates:
            return ()
        selection_model = self._list.selectionModel()
        selection_model.clearSelection()
        for index, row in enumerate(duplicates):
            flags = QItemSelectionModel.SelectionFlag.Select
            if index == 0:
                flags |= QItemSelectionModel.SelectionFlag.Current
            selection_model.select(self._model.index(row, 0), flags)
        self._list.setCurrentIndex(self._model.index(duplicates[0], 0))
        self._emit_order_state()
        return duplicates

    def move_selected(self, offset: int) -> None:
        row = self._list.currentRow()
        target = row + offset
        if row < 0 or target < 0 or target >= self._list.count():
            return
        insertion = target + 1 if offset > 0 else target
        if self._list.move_row_to_insertion(row, insertion):
            self._emit_order_state()

    def render_next_batch(self) -> None:
        if self._document.status() != QPdfDocument.Status.Ready:
            return
        end = min(self._list.count(), self._next_render_page + self._batch_size)
        for index in range(self._next_render_page, end):
            self._request_thumbnail(index)
        self._next_render_page = end
        self._update_load_more_state()

    def _configure_mode(self) -> None:
        self._model.set_mode(self._mode, external_drag_enabled=self._external_drag_enabled)
        if self._mode == "preview_only":
            self._list.set_ordered_mode(False)
            self._list.setMovement(QListWidget.Movement.Static)
            self._list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
            self._list.setAcceptDrops(False)
            self._list.viewport().setAcceptDrops(False)
            self._list.setDragEnabled(False)
            self._list.setDragDropMode(QListWidget.DragDropMode.NoDragDrop)
        elif self._mode == "ordered":
            self._list.set_ordered_mode(True)
            self._list.setMovement(QListWidget.Movement.Static)
            self._list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
            self._list.setAcceptDrops(True)
            self._list.viewport().setAcceptDrops(True)
            self._list.setDragEnabled(True)
            self._list.setDropIndicatorShown(False)
            self._list.setDragDropMode(QListWidget.DragDropMode.DragDrop)
            self._list.setDefaultDropAction(Qt.DropAction.MoveAction)
        else:
            self._list.set_ordered_mode(False)
            self._list.setMovement(QListWidget.Movement.Static)
            self._list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
            self._list.setAcceptDrops(False)
            self._list.viewport().setAcceptDrops(False)
            self._list.setDragEnabled(self._external_drag_enabled)
            self._list.setDragDropMode(
                QListWidget.DragDropMode.DragOnly
                if self._external_drag_enabled
                else QListWidget.DragDropMode.NoDragDrop
            )

    def _configure_layout(self) -> None:
        self._list.set_layout_mode(self._layout_mode)
        self._list.setIconSize(THUMBNAIL_ICON_BOUNDS)
        self._list.setGridSize(THUMBNAIL_GRID_SIZE)
        self._list.setUniformItemSizes(True)
        if self._layout_mode == "horizontal_strip":
            self._max_cached_thumbnails = self._requested_max_cached_thumbnails
            self._list.setFlow(QListView.Flow.LeftToRight)
            self._list.setWrapping(False)
            self._list.setMinimumHeight(THUMBNAIL_LIST_HEIGHT)
            self._list.setMaximumHeight(THUMBNAIL_LIST_HEIGHT)
            self._list.setMaximumWidth(16777215)
            self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            self._list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            return

        if self._layout_mode == "vertical_strip":
            self._max_cached_thumbnails = max(self._requested_max_cached_thumbnails, 24)
            self._list.setFlow(QListView.Flow.TopToBottom)
            self._list.setWrapping(False)
            self._list.setMinimumHeight(THUMBNAIL_LIST_HEIGHT)
            self._list.setMaximumHeight(16777215)
            self._list.setMaximumWidth(16777215)
            self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self._list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            self._sync_vertical_grid_width()
            return

        self._max_cached_thumbnails = max(
            self._requested_max_cached_thumbnails,
            THUMBNAIL_GRID_VISIBLE_ROWS * THUMBNAIL_GRID_MAX_COLUMNS + 10,
        )
        self._list.setFlow(QListView.Flow.LeftToRight)
        self._list.setWrapping(True)
        self._list.setMinimumHeight(THUMBNAIL_LIST_HEIGHT)
        self._list.setMaximumHeight(THUMBNAIL_GRID_HEIGHT)
        self._list.setMaximumWidth(THUMBNAIL_GRID_SIZE.width() * THUMBNAIL_GRID_MAX_COLUMNS + 28)
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

    def _sync_vertical_grid_width(self) -> None:
        if self._layout_mode != "vertical_strip":
            return
        width = max(THUMBNAIL_GRID_SIZE.width(), self._list.viewport().width())
        self._list.setGridSize(QSize(width, THUMBNAIL_GRID_SIZE.height()))

    def _document_status_changed(self, status: QPdfDocument.Status) -> None:
        if status == QPdfDocument.Status.Ready:
            self._document_ready()
            return
        if status == QPdfDocument.Status.Error:
            self._mark_all_pages_error()

    def _request_initial_thumbnails(self) -> None:
        if self._layout_mode == "horizontal_strip":
            self.render_next_batch()
            return
        self._schedule_visible_thumbnails()

    def _schedule_visible_thumbnails(self) -> None:
        self._viewport_debounce.start()

    def _request_visible_thumbnails(self) -> None:
        if self._layout_mode == "horizontal_strip":
            return
        if self._document.status() != QPdfDocument.Status.Ready:
            return
        visible_rows = self._list.visible_rows()
        visible_pages = tuple(
            page for row in visible_rows if (page := self._model.page_at(row)) is not None
        )
        active = self.active_page()
        if active is not None:
            self._queue_pages((active,), priority=0)
        self._queue_pages(visible_pages, priority=1)
        neighbor_pages: set[int] = set()
        for page in visible_pages:
            if page > 1:
                neighbor_pages.add(page - 1)
            if page < self._source_page_count:
                neighbor_pages.add(page + 1)
        self._queue_pages(tuple(sorted(neighbor_pages)), priority=2)
        self._pump_thumbnail_requests()

    def _request_thumbnail(self, item_index: int, *, priority: int = 1) -> None:
        page_number = self._model.page_at(item_index)
        if page_number is None:
            return
        if self._document.status() != QPdfDocument.Status.Ready:
            return
        if page_number in self._rendered_pages:
            self._set_page_state(page_number, "ready")
            return
        if page_number in self._scheduler.pending_pages:
            return
        self._queue_pages((page_number,), priority=priority)
        self._pump_thumbnail_requests()

    def _queue_pages(self, pages: tuple[int, ...], *, priority: int) -> None:
        missing = tuple(
            page
            for page in pages
            if 1 <= page <= self._list.count() and page not in self._rendered_pages
        )
        self._scheduler.enqueue(missing, priority=priority)

    def _pump_thumbnail_requests(self) -> None:
        self._scheduler.start_available(self._issue_thumbnail_request)
        self._pending_pages = self._scheduler.pending_pages

    def _issue_thumbnail_request(self, page_number: int) -> int | None:
        if self._document.status() != QPdfDocument.Status.Ready:
            return None
        options = QPdfDocumentRenderOptions()
        render_size = self._render_size(page_number)
        options.setScaledSize(render_size)
        request_id = int(self._renderer.requestPage(page_number - 1, render_size, options))
        self._set_page_state(page_number, "loading")
        return request_id

    def _render_size(self, page_number: int) -> QSize:
        point_size = self._document.pagePointSize(page_number - 1)
        width = max(1.0, point_size.width())
        height = max(1.0, point_size.height())
        scale = min(
            THUMBNAIL_RENDER_BOUNDS.width() / width,
            THUMBNAIL_RENDER_BOUNDS.height() / height,
        )
        return QSize(max(1, int(width * scale)), max(1, int(height * scale)))

    def _page_rendered(
        self,
        page_number: int,
        size: QSize,
        image,
        options: QPdfDocumentRenderOptions,
        request_id: int,
    ) -> None:
        del page_number, size, options
        request = self._scheduler.complete(int(request_id))
        if request is None:
            return
        generation, one_based_page = request
        self._pending_pages = self._scheduler.pending_pages
        if generation != self._document_generation:
            self._pump_thumbnail_requests()
            return
        rendered_image = _compose_on_paper(image) if not image.isNull() else image
        if _image_is_invalid_thumbnail(rendered_image):
            LOGGER.debug(
                "thumbnail render unavailable file=%s page=%s reason=invalid-image",
                self._document_debug_id,
                one_based_page,
            )
            self._set_page_error(one_based_page)
            self._pump_thumbnail_requests()
            return

        if self._model.row_for_page(one_based_page) < 0:
            self._pump_thumbnail_requests()
            return

        icon = QIcon(QPixmap.fromImage(rendered_image))
        evicted = self._rendered_pages.put(
            one_based_page,
            icon,
            max(1, int(rendered_image.sizeInBytes())),
        )
        for evicted_page in evicted:
            self._model.set_page_icon(evicted_page, None)
            self._set_page_state(evicted_page, "loading")
        self._model.set_page_icon(one_based_page, icon)
        self._set_page_state(one_based_page, "ready")
        self.thumbnail_ready.emit(one_based_page)
        self._pump_thumbnail_requests()

    def _set_page_error(self, page_number: int) -> None:
        self._model.set_page_icon(page_number, None)
        self._set_page_state(page_number, "error")

    def _item_for_page(self, page_number: int) -> _ThumbnailItemAdapter | None:
        row = self._model.row_for_page(page_number)
        return self._list.item(row) if row >= 0 else None

    def _mark_all_pages_error(self) -> None:
        for page_number in self._model.page_order():
            self._set_page_state(page_number, "error")

    def _set_item_state(
        self,
        item: QListWidgetItem | _ThumbnailItemAdapter,
        page_number: int,
        state: ThumbnailRenderState,
    ) -> None:
        item.setData(THUMBNAIL_STATE_ROLE, state)
        if state == "ready" and page_number in self._rendered_pages:
            item.setIcon(self._rendered_pages[page_number])
        else:
            item.setIcon(_placeholder_icon(state))
        self._apply_item_mark(item, page_number)

    def _set_page_state(self, page_number: int, state: ThumbnailRenderState) -> None:
        self._model.set_page_state(page_number, state)

    def _item_text(self, page_number: int, state: ThumbnailRenderState) -> str:
        label = tr("thumbnails.page_label", self._locale, page=page_number)
        if state == "loading":
            return f"{label}\n{tr('thumbnails.loading', self._locale)}"
        if state == "error":
            return f"{label}\n{tr('thumbnails.unavailable', self._locale)}"
        mark = self._page_marks.get(page_number, "")
        if mark == "deleted":
            return f"{label}\n{tr('thumbnails.deleted', self._locale)}"
        if mark == "assigned":
            return f"{label}\n{tr('thumbnails.assigned', self._locale)}"
        return label

    def _evict_cache(self) -> None:
        return

    def _emit_selection_state(self) -> None:
        selected_pages = self.selected_pages()
        self.selection_changed.emit(selected_pages)
        if self._mode == "split":
            ranges = tuple(
                PageRange(group[0], group[-1], tuple(group))
                for group in _contiguous_groups(selected_pages)
            )
            self.split_ranges_changed.emit(ranges)

    def _emit_clicked_page(self, item: QListWidgetItem | _ThumbnailItemAdapter) -> None:
        if item.data(PAGE_NUMBER_ROLE) is None:
            return
        self.page_clicked.emit(int(item.data(PAGE_NUMBER_ROLE)))

    def _emit_active_page(
        self,
        item: QListWidgetItem | _ThumbnailItemAdapter | None,
        _previous: QListWidgetItem | _ThumbnailItemAdapter | None = None,
    ) -> None:
        if item is None or item.data(PAGE_NUMBER_ROLE) is None:
            return
        self.active_page_changed.emit(int(item.data(PAGE_NUMBER_ROLE)))

    def _emit_order_state(self) -> None:
        if self._mode == "ordered":
            self.order_changed.emit(self.page_order())

    def _item_flags(self) -> Qt.ItemFlag:
        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if self._mode == "ordered":
            flags |= Qt.ItemFlag.ItemIsDragEnabled | Qt.ItemFlag.ItemIsDropEnabled
        if self._external_drag_enabled:
            flags |= Qt.ItemFlag.ItemIsDragEnabled
        return flags

    def _apply_item_mark(
        self,
        item: QListWidgetItem | _ThumbnailItemAdapter,
        page_number: int,
    ) -> None:
        mark = self._page_marks.get(page_number, "")
        item.setData(THUMBNAIL_MARK_ROLE, mark)

    def _update_load_more_state(self) -> None:
        self._load_more_button.setVisible(
            self._layout_mode == "horizontal_strip" and self._next_render_page < self._list.count()
        )


def pages_to_range_expression(pages: tuple[int, ...] | list[int]) -> str:
    groups = _contiguous_groups(tuple(sorted(set(pages))))
    return ",".join(
        str(group[0]) if group[0] == group[-1] else f"{group[0]}-{group[-1]}" for group in groups
    )


def ordered_pages_to_permutation(
    order: tuple[int, ...] | list[int],
    page_count: int,
) -> tuple[int, ...]:
    pages = tuple(order)
    expected = tuple(range(1, page_count + 1))
    if sorted(pages) != list(expected):
        raise ValueError("page order must include every page exactly once")
    return pages


def ordered_pages_to_sequence(
    order: tuple[int, ...] | list[int],
    page_count: int,
) -> tuple[int, ...]:
    pages = tuple(order)
    expected = set(range(1, page_count + 1))
    if not pages or set(pages) != expected:
        raise ValueError("page order must include every source page at least once")
    return pages


def target_row_for_insertion(
    source_row: int,
    insertion_index: int,
    item_count: int,
) -> int | None:
    if source_row < 0 or source_row >= item_count:
        return None
    if insertion_index < 0 or insertion_index > item_count:
        return None
    target_row = insertion_index
    if target_row > source_row:
        target_row -= 1
    return max(0, min(target_row, item_count - 1))


def reordered_pages_for_insertion(
    order: tuple[int, ...] | list[int],
    source_row: int,
    insertion_index: int,
) -> tuple[int, ...] | None:
    pages = list(order)
    target_row = target_row_for_insertion(source_row, insertion_index, len(pages))
    if target_row is None:
        return None
    moved = pages.pop(source_row)
    pages.insert(target_row, moved)
    return tuple(pages)


def _event_position(event) -> QPoint:  # noqa: ANN001
    position = event.position() if hasattr(event, "position") else event.pos()
    return position.toPoint() if hasattr(position, "toPoint") else position


def _reorder_payload_from_mime(mime_data: QMimeData) -> tuple[int, int] | None:
    if not mime_data.hasFormat(PAGE_REORDER_MIME):
        return None
    try:
        payload = bytes(mime_data.data(PAGE_REORDER_MIME)).decode("ascii")
        source_row_text, page_number_text = payload.split(",", maxsplit=1)
        source_row = int(source_row_text)
        page_number = int(page_number_text)
    except (TypeError, ValueError, UnicodeDecodeError):
        return None
    if source_row < 0 or page_number < 1:
        return None
    return source_row, page_number


def _contiguous_groups(pages: tuple[int, ...]) -> tuple[tuple[int, ...], ...]:
    if not pages:
        return ()
    groups: list[list[int]] = [[pages[0]]]
    for page in pages[1:]:
        if page == groups[-1][-1] + 1:
            groups[-1].append(page)
        else:
            groups.append([page])
    return tuple(tuple(group) for group in groups)


def _placeholder_icon(state: ThumbnailRenderState = "loading") -> QIcon:
    pixmap = QPixmap(THUMBNAIL_ICON_BOUNDS)
    pixmap.fill(_placeholder_color(state))
    painter = QPainter(pixmap)
    painter.setPen(QPen(_placeholder_border_color(state), 2, Qt.PenStyle.DashLine))
    painter.drawRect(1, 1, pixmap.width() - 2, pixmap.height() - 2)
    if state == "error":
        painter.setPen(QPen(_indicator_color(), 2, Qt.PenStyle.SolidLine))
        painter.drawLine(12, 12, pixmap.width() - 13, 12)
    painter.end()
    return QIcon(pixmap)


def _thumbnail_item_text(
    page_number: int,
    state: ThumbnailRenderState,
    mark: str,
    locale: Locale,
) -> str:
    label = tr("thumbnails.page_label", locale, page=page_number)
    if state == "loading":
        return f"{label}\n{tr('thumbnails.loading', locale)}"
    if state == "error":
        return f"{label}\n{tr('thumbnails.unavailable', locale)}"
    if mark == "deleted":
        return f"{label}\n{tr('thumbnails.deleted', locale)}"
    if mark == "assigned":
        return f"{label}\n{tr('thumbnails.assigned', locale)}"
    return label


def thumbnail_placeholder_icon(state: ThumbnailRenderState = "loading") -> QIcon:
    return _placeholder_icon(state)


def _placeholder_color(state: ThumbnailRenderState) -> QColor:
    tokens = _current_tokens()
    if state == "error":
        return QColor(tokens.color_bg_surface)
    return QColor(tokens.color_bg_surface)


def _placeholder_border_color(state: ThumbnailRenderState) -> QColor:
    tokens = _current_tokens()
    if state == "error":
        return QColor(tokens.color_warning)
    return QColor(tokens.color_border_default)


def _indicator_color() -> QColor:
    return QColor(_current_tokens().color_warning)


def _mark_background(mark: str) -> QColor:
    tokens = _current_tokens()
    if mark == "deleted":
        return QColor(tokens.color_danger_bg)
    if mark == "assigned":
        return QColor(tokens.color_info_bg)
    return QColor(tokens.color_bg_surface)


def _mark_foreground(mark: str) -> QColor:
    tokens = _current_tokens()
    if mark == "deleted":
        return QColor(tokens.color_danger)
    if mark == "assigned":
        return QColor(tokens.color_info)
    return QColor(tokens.color_text_main)


def _current_tokens() -> ThemeTokens:
    app = QApplication.instance()
    preset = app.property("priveopdf_theme_preset") if app is not None else "dark_pro"
    if isinstance(preset, str):
        return PALETTES.get(preset, PALETTES["dark_pro"])
    mode = app.property("priveopdf_theme_mode") if app is not None else "dark"
    return PALETTES.get(mode, PALETTES["dark_pro"])


def _compose_on_paper(image: QImage) -> QImage:
    composed = QImage(image.size(), QImage.Format.Format_ARGB32_Premultiplied)
    composed.fill(Qt.GlobalColor.white)
    painter = QPainter(composed)
    painter.drawImage(0, 0, image)
    painter.end()
    return composed


def _image_is_invalid_thumbnail(image: QImage) -> bool:
    if image.isNull() or image.width() <= 1 or image.height() <= 1:
        return True
    sample_count = 0
    black_count = 0
    step_x = max(1, image.width() // 8)
    step_y = max(1, image.height() // 8)
    for y in range(0, image.height(), step_y):
        for x in range(0, image.width(), step_x):
            color = image.pixelColor(x, y)
            sample_count += 1
            if color.alpha() > 0 and color.red() < 4 and color.green() < 4 and color.blue() < 4:
                black_count += 1
    return sample_count > 0 and black_count == sample_count


def _new_document_debug_id() -> str:
    return uuid4().hex[:10]
