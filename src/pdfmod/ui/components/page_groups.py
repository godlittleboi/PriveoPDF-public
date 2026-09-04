from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QLabel,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from pdfmod.ui.components.cards import SurfacePanel
from pdfmod.ui.components.page_thumbnails import (
    PAGE_NUMBER_ROLE,
    target_row_for_insertion,
    thumbnail_placeholder_icon,
)

PAGE_GROUP_ROLE = Qt.ItemDataRole.UserRole + 30
PAGE_MIME_PREFIX = "application/x-priveopdf-pages:"
PAGE_OUTPUT_ICON_SIZE = QSize(128, 180)
PAGE_OUTPUT_GRID_SIZE = QSize(156, 228)
PAGE_OUTPUT_LIST_HEIGHT = 260
PAGE_OUTPUT_LIST_COMPACT_HEIGHT = 232
PAGE_OUTPUT_LIST_LARGE_HEIGHT = 340
ThumbnailProvider = Callable[[int], QIcon | None]


class PageGroupListWidget(QListWidget):
    pages_dropped = Signal(tuple)
    order_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._thumbnail_provider: ThumbnailProvider | None = None
        self.setObjectName("PageOutputList")
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setViewMode(QListWidget.ViewMode.IconMode)
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.setFlow(QListView.Flow.LeftToRight)
        self.setWrapping(True)
        self.setUniformItemSizes(True)
        self.setIconSize(PAGE_OUTPUT_ICON_SIZE)
        self.setGridSize(PAGE_OUTPUT_GRID_SIZE)
        self.setMinimumHeight(PAGE_OUTPUT_LIST_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def pages(self) -> tuple[int, ...]:
        return tuple(
            int(self.item(index).data(PAGE_NUMBER_ROLE))
            for index in range(self.count())
            if self.item(index).data(PAGE_NUMBER_ROLE) is not None
        )

    def set_pages(self, pages: tuple[int, ...] | list[int]) -> None:
        self.clear()
        for page in pages:
            self._add_page_item(int(page))
        self._refresh_item_labels_and_icons()
        self.order_changed.emit()

    def set_thumbnail_provider(self, provider: ThumbnailProvider | None) -> None:
        self._thumbnail_provider = provider
        self._refresh_item_labels_and_icons()

    def refresh_page_thumbnail(self, page: int) -> None:
        for index in range(self.count()):
            item = self.item(index)
            if int(item.data(PAGE_NUMBER_ROLE)) == page:
                item.setIcon(self._icon_for_page(page))

    def set_minimum_view_height(self, height: int) -> None:
        self.setMinimumHeight(max(PAGE_OUTPUT_LIST_COMPACT_HEIGHT, height))

    def dragEnterEvent(self, event) -> None:  # noqa: ANN001, N802
        if event.source() is self or _pages_from_mime(event.mimeData()):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:  # noqa: ANN001, N802
        if event.source() is self or _pages_from_mime(event.mimeData()):
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:  # noqa: ANN001, N802
        insertion_index = self._insertion_index(event.position().toPoint())
        if event.source() is self:
            self._move_selected_to(insertion_index)
            event.acceptProposedAction()
            return

        pages = _pages_from_mime(event.mimeData())
        if pages:
            self._insert_unique_pages(pages, insertion_index)
            self.pages_dropped.emit(pages)
            event.acceptProposedAction()
            return

        super().dropEvent(event)

    def _move_selected_to(self, insertion_index: int) -> None:
        selected = self.selectedItems()
        if not selected:
            return
        item = selected[0]
        source_row = self.row(item)
        target_row = target_row_for_insertion(source_row, insertion_index, self.count())
        if target_row is None:
            return
        if target_row == source_row:
            return
        moved = self.takeItem(source_row)
        self.insertItem(target_row, moved)
        self.setCurrentItem(moved)
        self._refresh_item_labels_and_icons()
        self.order_changed.emit()

    def _insertion_index(self, pos) -> int:  # noqa: ANN001
        item = self.itemAt(pos)
        if item is None:
            return self.count()
        rect = self.visualItemRect(item)
        index = self.row(item)
        return index if pos.x() < rect.center().x() else index + 1

    def _add_page_item(self, page: int) -> None:
        self.addItem(_page_item(page, self.count() + 1, self._icon_for_page(page)))

    def _insert_unique_pages(self, pages: tuple[int, ...], insertion_index: int) -> None:
        incoming = _unique_pages(pages)
        if not incoming:
            return
        current = list(self.pages())
        adjusted_index = max(0, min(insertion_index, len(current)))
        incoming_set = set(incoming)
        retained: list[int] = []
        for index, page in enumerate(current):
            if page in incoming_set:
                if index < adjusted_index:
                    adjusted_index -= 1
                continue
            retained.append(page)
        adjusted_index = max(0, min(adjusted_index, len(retained)))
        new_pages = (
            *retained[:adjusted_index],
            *incoming,
            *retained[adjusted_index:],
        )
        self.set_pages(new_pages)

    def _icon_for_page(self, page: int) -> QIcon:
        if self._thumbnail_provider is None:
            return thumbnail_placeholder_icon("loading")
        icon = self._thumbnail_provider(page)
        return icon if icon is not None else thumbnail_placeholder_icon("loading")

    def _refresh_item_labels_and_icons(self) -> None:
        for index in range(self.count()):
            item = self.item(index)
            page = int(item.data(PAGE_NUMBER_ROLE))
            item.setText(_page_item_text(page, index + 1))
            item.setIcon(self._icon_for_page(page))


class PageOutputGroupWidget(SurfacePanel):
    pages_changed = Signal(str, tuple)
    pages_dropped = Signal(str, tuple)

    def __init__(
        self,
        group_id: str,
        title: str,
        empty_text: str,
        remove_on_click: bool = False,
        remove_text: str = "Remove from this output",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(role="primary", parent=parent)
        self._group_id = group_id
        self._empty_text = empty_text
        self._remove_on_click = remove_on_click
        self._remove_text = remove_text
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._title = QLabel(title)
        self._title.setObjectName("SectionTitle")
        self._empty_label = QLabel(empty_text)
        self._empty_label.setObjectName("HelpText")
        self._empty_label.setWordWrap(True)
        self._list = PageGroupListWidget()
        self._list.pages_dropped.connect(self._pages_dropped)
        self._list.order_changed.connect(self._emit_pages_changed)
        self._list.itemClicked.connect(self._item_clicked)
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._open_item_context_menu)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)
        layout.addWidget(self._title)
        layout.addWidget(self._empty_label)
        layout.addWidget(self._list, 1)
        self._refresh_empty_state()

    def group_id(self) -> str:
        return self._group_id

    def pages(self) -> tuple[int, ...]:
        return self._list.pages()

    def set_title(self, title: str) -> None:
        self._title.setText(title)

    def set_remove_text(self, text: str) -> None:
        self._remove_text = text

    def set_pages(self, pages: tuple[int, ...] | list[int]) -> None:
        self._list.set_pages(pages)
        self._refresh_empty_state()

    def set_thumbnail_provider(self, provider: ThumbnailProvider | None) -> None:
        self._list.set_thumbnail_provider(provider)

    def refresh_page_thumbnail(self, page: int) -> None:
        self._list.refresh_page_thumbnail(page)

    def set_minimum_list_height(self, height: int) -> None:
        self._list.set_minimum_view_height(height)

    def add_pages(self, pages: tuple[int, ...] | list[int]) -> None:
        existing = list(self.pages())
        for page in pages:
            if int(page) not in existing:
                existing.append(int(page))
        self.set_pages(tuple(existing))

    def remove_page(self, page: int) -> None:
        self.set_pages(tuple(candidate for candidate in self.pages() if candidate != page))

    def _pages_dropped(self, pages: tuple[int, ...]) -> None:
        self._refresh_empty_state()
        self.pages_dropped.emit(self._group_id, pages)
        self._emit_pages_changed()

    def _emit_pages_changed(self) -> None:
        self._refresh_empty_state()
        self.pages_changed.emit(self._group_id, self.pages())

    def _item_clicked(self, item: QListWidgetItem) -> None:
        if not self._remove_on_click or item.data(PAGE_NUMBER_ROLE) is None:
            return
        self.remove_page(int(item.data(PAGE_NUMBER_ROLE)))

    def _open_item_context_menu(self, pos) -> None:  # noqa: ANN001
        item = self._list.itemAt(pos)
        if item is None or item.data(PAGE_NUMBER_ROLE) is None:
            return
        menu = QMenu(self)
        remove_action = menu.addAction(self._remove_text)
        selected_action = menu.exec(self._list.mapToGlobal(pos))
        if selected_action is remove_action:
            self.remove_page(int(item.data(PAGE_NUMBER_ROLE)))

    def _refresh_empty_state(self) -> None:
        self._empty_label.setVisible(self._list.count() == 0)


def _page_item(page: int, order: int, icon: QIcon) -> QListWidgetItem:
    item = QListWidgetItem(icon, _page_item_text(page, order))
    item.setData(PAGE_NUMBER_ROLE, page)
    item.setData(PAGE_GROUP_ROLE, page)
    item.setFlags(
        Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsDragEnabled
    )
    return item


def _page_item_text(page: int, order: int) -> str:
    return f"#{order}\nPage {page}"


def _unique_pages(pages: tuple[int, ...] | list[int]) -> tuple[int, ...]:
    seen: set[int] = set()
    unique: list[int] = []
    for page in pages:
        if page in seen:
            continue
        seen.add(page)
        unique.append(page)
    return tuple(unique)


def _pages_from_mime(mime_data) -> tuple[int, ...]:  # noqa: ANN001
    text = mime_data.text() if mime_data.hasText() else ""
    if not text.startswith(PAGE_MIME_PREFIX):
        return ()
    return tuple(
        int(value) for value in text.removeprefix(PAGE_MIME_PREFIX).split(",") if value.isdecimal()
    )
