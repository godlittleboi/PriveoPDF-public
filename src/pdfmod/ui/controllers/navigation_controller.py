from __future__ import annotations

from collections.abc import Callable, Mapping

from PySide6.QtWidgets import QStackedWidget, QWidget

from pdfmod.domain.document_context import ToolLaunchContext
from pdfmod.ui.app_store import AppStore
from pdfmod.ui.components import Sidebar, TopBar
from pdfmod.ui.page_contracts import ToolLaunchPage
from pdfmod.ui.theme.animations import fade_in


class NavigationController:
    """Apply shell navigation state without knowing page implementation details."""

    def __init__(
        self,
        *,
        stack: QStackedWidget,
        sidebar: Sidebar,
        top_bar: TopBar,
        pages: Mapping[str, QWidget],
        tool_launch_pages: Mapping[str, ToolLaunchPage],
        store: AppStore,
        sync_page: Callable[[QWidget], None],
        page_title: Callable[[str], str],
        reduce_motion: Callable[[], bool],
    ) -> None:
        self._stack = stack
        self._sidebar = sidebar
        self._top_bar = top_bar
        self._pages = dict(pages)
        self._tool_launch_pages = dict(tool_launch_pages)
        self._store = store
        self._sync_page = sync_page
        self._page_title = page_title
        self._reduce_motion = reduce_motion
        self._active_tool_launch_context: ToolLaunchContext | None = None

    @property
    def active_tool_launch_context(self) -> ToolLaunchContext | None:
        return self._active_tool_launch_context

    @active_tool_launch_context.setter
    def active_tool_launch_context(self, context: ToolLaunchContext | None) -> None:
        self._active_tool_launch_context = context

    def show(self, key: str, launch_context: ToolLaunchContext | None = None) -> bool:
        page = self._pages.get(key)
        if page is None:
            return False
        shell_page = key in {"dashboard", "community", "document"}
        self._active_tool_launch_context = None if shell_page else launch_context
        self._store.set_active_tool_key(None if shell_page else key)
        self._sync_page(page)
        tool_page = self._tool_launch_pages.get(key)
        if tool_page is not None:
            tool_page.set_tool_launch_context(self._active_tool_launch_context)
        self._stack.setCurrentWidget(page)
        self._sidebar.set_active(key)
        self._top_bar.set_title(self._page_title(key))
        fade_in(page, reduce_motion=self._reduce_motion())
        return True

    def current_key(self) -> str:
        current = self._stack.currentWidget()
        for key, page in self._pages.items():
            if page is current:
                return key
        return "dashboard"

    def refresh_title(self) -> None:
        self._top_bar.set_title(self._page_title(self.current_key()))
