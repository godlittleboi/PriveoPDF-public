"""PDF reader viewport which consumes validated pixels, never PDF bytes."""

from __future__ import annotations

from bisect import bisect_right
from collections import OrderedDict
from enum import IntEnum
from math import trunc

from PySide6.QtCore import QObject, QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QGuiApplication, QKeySequence, QPainter
from PySide6.QtWidgets import QAbstractScrollArea, QApplication

from priveopdf.ui.components.cards import _current_tokens
from priveopdf.ui.components.text_selection import TextLayout
from priveopdf.ui.components.viewer_tools import PageOverlay, ViewerTool
from priveopdf.ui.i18n import tr
from priveopdf.ui.theme.tokens import SPACING
from priveopdf.workers.render_client import (
    RemotePageRenderer,
    RemoteRenderOptions,
    bounded_render_size,
)

# Pages whose text boxes stay in memory (5 000 boxes at most per page, under
# 2 MB each), and visible pages whose boxes are fetched before the pointer comes.
_MAX_TEXT_LAYOUTS = 8
_PREFETCH_PAGES = 3


class _Navigator(QObject):
    currentPageChanged = Signal(int)

    def __init__(self, view):
        super().__init__(view)
        self.view = view
        self._page = 0

    def currentPage(self):
        return self._page

    def jump(self, page, location=None, zoom=0):
        if self.view._document is None or not 0 <= page < self.view._document.pageCount():
            return
        self.view.verticalScrollBar().setValue(round(self.view._offsets[page]))
        self._set(page)
        self.view.viewport().update()

    def _set(self, page):
        if page != self._page:
            self._page = page
            self.currentPageChanged.emit(page)


class IsolatedPdfView(QAbstractScrollArea):
    class PageMode(IntEnum):
        SinglePage = 0
        MultiPage = 1

    class ZoomMode(IntEnum):
        Custom = 0
        FitToWidth = 1
        FitInView = 2

    zoomFactorChanged = Signal(float)
    # Zoom factor asked by Ctrl+wheel, and the viewport point to keep in place.
    zoom_requested = Signal(float, QPointF)
    page_step_requested = Signal(int)
    # Current match (0-based, -1 when none), match count, and state: "idle",
    # "running", "done" or "failed".
    search_changed = Signal(int, int, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._locale = "en"
        self._document = None
        self._navigator = _Navigator(self)
        self._zoom_mode = self.ZoomMode.FitInView
        self._zoom = 1.0
        self._fit_zoom_ceiling = 4.0
        self._page_mode = self.PageMode.MultiPage
        self._offsets = [0.0]
        self._sizes = []
        self._cache = OrderedDict()
        self._cache_bytes = 0
        self._requests = {}
        self._failed = set()
        # Text boxes per page, fetched once from the render worker for selection.
        self._layouts: OrderedDict[int, TextLayout] = OrderedDict()
        self._layout_requests: dict[int, int] = {}
        self._selection_page: int | None = None
        self._anchor = QPointF()
        self._focus = QPointF()
        self._selection_rects: list[tuple[float, float, float, float]] = []
        self._selection_id = None
        self._selection_text = ""
        self._copy_pending = False
        self._search_id = None
        self._query = ""
        self._prefetch_text = False
        self._matches: list[tuple[int, list[tuple[float, float, float, float]]]] = []
        self._match_index = -1
        self._renderer = RemotePageRenderer(self)
        self._renderer.pageRendered.connect(self._rendered)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(30)
        self._timer.timeout.connect(self._request_visible)
        self._wheel_remainder_x = 0.0
        self._wheel_remainder_y = 0.0
        # Step 6A: layers above the pages and the one tool receiving the mouse.
        self._overlays: list[PageOverlay] = []
        self._active_tool: ViewerTool | None = None
        self._tool_dragging = False
        # The page a tool drag started on: the drag stays on it and its points
        # are clamped to it, like the text selection (review of B5).
        self._tool_page: int | None = None
        # Annotation appearances (comments, stamps, filled fields) are part of
        # the page as any PDF reader shows it (#398).
        self._render_annotations = True
        self.verticalScrollBar().valueChanged.connect(self._scrolled)
        self.horizontalScrollBar().valueChanged.connect(lambda _: self.viewport().update())
        self.verticalScrollBar().setSingleStep(48)
        self.horizontalScrollBar().setSingleStep(48)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        # Hovering text shows the text cursor, as in an ordinary PDF reader.
        self.viewport().setMouseTracking(True)

    def set_locale(self, locale):
        self._locale = locale
        self.setAccessibleName(tr("viewer.accessible", locale))
        self.viewport().update()

    def setDocument(self, document):
        self._document = document
        self._renderer.setDocument(document)
        document.pageCountChanged.connect(self._reset)
        document.resultReady.connect(self._result_ready)

    def document(self):
        return self._document

    def enable_text_prefetch(self):
        """Fetch the text boxes of the pages in view, so text is selectable at once."""
        self._prefetch_text = True

    def pageNavigator(self):
        return self._navigator

    def setPageMode(self, mode):
        self._page_mode = mode

    def pageMode(self):
        return self._page_mode

    def setZoomMode(self, mode):
        self._zoom_mode = mode
        self._layout()

    def zoomMode(self):
        return self._zoom_mode

    def zoomFactor(self):
        return self._zoom

    def setZoomFactor(self, zoom, anchor=None):
        """Apply a zoom; with `anchor` (viewport point), the page point under it
        stays under it, so the zoom is centred on the pointer (6A)."""
        kept = None
        if anchor is not None:
            # In the gap between two pages, the nearest page keeps the anchor
            # (review of 6A): the content under the pointer does not jump.
            page = self.page_at(anchor)
            if page is None:
                page = self._nearest_visible_page(anchor)
            if page is not None:
                kept = (page, self.to_page(page, anchor))
        self._zoom = max(0.01, min(self._fit_zoom_ceiling, zoom))
        self._layout()
        if kept is not None:
            moved = self.to_view(kept[0], kept[1]) - anchor
            horizontal, vertical = self.horizontalScrollBar(), self.verticalScrollBar()
            horizontal.setValue(horizontal.value() + round(moved.x()))
            vertical.setValue(vertical.value() + round(moved.y()))
        self.zoomFactorChanged.emit(self._zoom)

    # Geometry (6A): the only conversion between page points and viewport pixels.

    def page_at(self, position):
        """Index of the page under a viewport point, or None."""
        return next((p for p in self._visible() if self._rect(p).contains(position)), None)

    def _nearest_visible_page(self, position):
        visible = self._visible()
        if not visible:
            return None
        return min(
            visible,
            key=lambda p: abs(self._rect(p).center().y() - position.y()),
        )

    def page_rect(self, page):
        """Rectangle of a page in viewport pixels."""
        return self._rect(page)

    def to_page(self, page, position):
        """Viewport point to page units (origin: top-left corner of the page)."""
        return (position - self._rect(page).topLeft()) / self._zoom

    def to_view(self, page, point):
        """Page units to viewport pixels."""
        return self._rect(page).topLeft() + point * self._zoom

    # Overlays and active tool (6A).

    def add_overlay(self, overlay):
        if overlay not in self._overlays:
            self._overlays.append(overlay)
            overlay.changed.connect(self.viewport().update)
            self.viewport().update()

    def remove_overlay(self, overlay):
        if overlay in self._overlays:
            self._overlays.remove(overlay)
            overlay.changed.disconnect(self.viewport().update)
            self.viewport().update()

    def overlays(self):
        return tuple(self._overlays)

    def set_active_tool(self, tool):
        """Give the mouse to `tool`; None restores the plain reader."""
        if tool is self._active_tool:
            return
        previous = self._active_tool
        self._active_tool = None
        self._tool_dragging = False
        if previous is not None:
            previous.changed.disconnect(self.viewport().update)
            previous.deactivated()
        self._active_tool = tool
        if tool is not None:
            tool.changed.connect(self.viewport().update)
            self._clear_selection()
        self.viewport().unsetCursor()
        if self.viewport().underMouse():
            # The new tool's cursor applies at once, before any movement.
            self._update_cursor(self.viewport().mapFromGlobal(QCursor.pos()).toPointF())
        self.viewport().update()

    def active_tool(self):
        return self._active_tool

    def render_annotations(self):
        return self._render_annotations

    def _reset(self, count):
        self._fit_zoom_ceiling = 4.0
        self._cache.clear()
        self._cache_bytes = 0
        self._requests.clear()
        self._failed.clear()
        self._layouts.clear()
        self._layout_requests.clear()
        self._clear_selection()
        # An open search follows the newly loaded document.
        query = self._query
        self.clear_search()
        self._navigator._set(0)
        self.verticalScrollBar().setValue(0)
        self._layout()
        if query and count:
            self.search(query)
        else:
            self._query = query

    def _layout(self):
        anchor_page = self._navigator.currentPage()
        anchor_fraction = 0.0
        if 0 <= anchor_page < len(self._sizes):
            anchor_fraction = max(
                0.0,
                min(
                    1.0,
                    (self.verticalScrollBar().value() - self._offsets[anchor_page])
                    / (self._sizes[anchor_page].height() + SPACING["md"]),
                ),
            )
        count = self._document.pageCount() if self._document else 0
        self._sizes = []
        self._offsets = [0.0]
        if count:
            first = self._document.pagePointSize(min(self._navigator.currentPage(), count - 1))
            old_zoom = self._zoom
            if self._zoom_mode == self.ZoomMode.FitToWidth:
                self._zoom = max(0.01, (self.viewport().width() - SPACING["xl"]) / first.width())
            elif self._zoom_mode == self.ZoomMode.FitInView:
                self._zoom = max(
                    0.01,
                    min(
                        (self.viewport().width() - SPACING["xl"]) / first.width(),
                        (self.viewport().height() - SPACING["xl"]) / first.height(),
                    ),
                )
            if self._zoom_mode != self.ZoomMode.Custom:
                self._fit_zoom_ceiling = max(4.0, self._zoom)
            for page in range(count):
                points = self._document.pagePointSize(page)
                # Qt scrollbars are signed 32-bit. Bound extreme PDF geometry.
                size = QSize(
                    max(1, min(100_000, round(points.width() * self._zoom))),
                    max(1, min(100_000, round(points.height() * self._zoom))),
                )
                self._sizes.append(size)
                self._offsets.append(self._offsets[-1] + size.height() + SPACING["md"])
            if old_zoom != self._zoom:
                self.zoomFactorChanged.emit(self._zoom)
        width = max((s.width() for s in self._sizes), default=0) + SPACING["xl"]
        bar = self.verticalScrollBar()
        was_blocked = bar.blockSignals(True)
        try:
            bar.setRange(
                0, max(0, round(self._offsets[-1] + SPACING["md"] - self.viewport().height()))
            )
            bar.setPageStep(self.viewport().height())
            if self._sizes:
                anchor_page = max(0, min(anchor_page, len(self._sizes) - 1))
                bar.setValue(
                    round(
                        self._offsets[anchor_page]
                        + anchor_fraction * (self._sizes[anchor_page].height() + SPACING["md"])
                    )
                )
        finally:
            bar.blockSignals(was_blocked)
        self.horizontalScrollBar().setRange(0, max(0, width - self.viewport().width()))
        self.horizontalScrollBar().setPageStep(self.viewport().width())
        self._scrolled(bar.value())
        self.viewport().update()
        self._timer.start()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._layout()

    def _visible(self):
        if not self._sizes:
            return range(0)
        y = self.verticalScrollBar().value()
        first = max(0, bisect_right(self._offsets, y) - 1)
        last = min(len(self._sizes), bisect_right(self._offsets, y + self.viewport().height()) + 1)
        return range(first, last)

    def _rect(self, page):
        size = self._sizes[page]
        x = (
            max(SPACING["md"], (self.viewport().width() - size.width()) / 2)
            - self.horizontalScrollBar().value()
        )
        return QRectF(
            x,
            self._offsets[page] + SPACING["md"] / 2 - self.verticalScrollBar().value(),
            size.width(),
            size.height(),
        )

    def _key(self, page):
        size = bounded_render_size(self._sizes[page])
        return page, size.width(), size.height()

    def paintEvent(self, event):
        painter = QPainter(self.viewport())
        painter.fillRect(event.rect(), self.palette().window())
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        for page in self._visible():
            rect = self._rect(page)
            # The paper: rendered pixels may carry transparency.
            painter.fillRect(rect, Qt.GlobalColor.white)
            key = self._key(page)
            image = self._cache.get(key)
            if image is None and key not in self._failed:
                # Zoom just changed: the page keeps its previous pixels, scaled,
                # until the new ones arrive (6A), instead of a white page. A
                # rendering that failed at this size is said so, not hidden
                # behind older pixels (review of 6A).
                image = self._nearest_cached(page)
            elif image is not None:
                self._cache.move_to_end(key)
            if image is not None:
                painter.drawImage(rect, image)
            elif key in self._failed:
                painter.setPen(self.palette().text().color())
                painter.drawText(
                    rect, Qt.AlignmentFlag.AlignCenter, tr("viewer.render_error", self._locale)
                )
        tokens = _current_tokens()
        visible = self._visible()
        for index, (page, boxes) in enumerate(self._matches):
            if page in visible:
                # Search results on white paper; the current one stands out.
                painter.setOpacity(0.6 if index == self._match_index else 0.3)
                self._fill_boxes(painter, page, boxes, QColor(tokens.color_warning))
        page = self._selection_page
        if page is not None and page < len(self._sizes) and self._selection_rects:
            painter.setOpacity(0.35)
            self._fill_boxes(painter, page, self._selection_rects, QColor(tokens.color_info))
        painter.setOpacity(1.0)
        for overlay in self._overlays:
            for page in visible:
                rect = self._rect(page)
                painter.save()
                painter.setClipRect(rect)
                overlay.paint(painter, page, rect, self._zoom)
                painter.restore()
        painter.end()
        if not self._timer.isActive():
            self._timer.start()

    def _nearest_cached(self, page):
        """The largest cached rendering of the page, whatever its size (review
        of 6A: the sharpest intermediate, not the oldest)."""
        candidates = [(w * h, image) for (p, w, h), image in self._cache.items() if p == page]
        return max(candidates, key=lambda item: item[0])[1] if candidates else None

    def _fill_boxes(self, painter, page, boxes, color):
        rect = self._rect(page)
        # Text placed outside the page box is never highlighted over a neighbour.
        painter.save()
        painter.setClipRect(rect)
        for x, y, width, height in boxes:
            painter.fillRect(
                QRectF(
                    rect.x() + x * self._zoom,
                    rect.y() + y * self._zoom,
                    width * self._zoom,
                    height * self._zoom,
                ),
                color,
            )
        painter.restore()

    def search(self, query):
        """Search the whole document in the render worker; results arrive later."""
        self.clear_search()
        # Pasted text may hold line breaks, tabs or no-break spaces: one space each.
        kept = "".join(char for char in query if char.isprintable() or char.isspace())
        query = " ".join(kept.split())[:256].strip()
        if query and self._document is not None and self._document.pageCount():
            self._query = query
            self._search_id = self._document.request("search", query=query)
            self.search_changed.emit(-1, 0, "running")

    def clear_search(self):
        if self._search_id is not None and self._document is not None:
            self._document.cancel_request(self._search_id)
        self._search_id = None
        self._query = ""
        self._matches = []
        self._match_index = -1
        self.search_changed.emit(-1, 0, "idle")
        self.viewport().update()

    def show_match(self, step):
        """Go to the next (1) or previous (-1) match, wrapping around."""
        if not self._matches:
            return
        self._match_index = (self._match_index + step) % len(self._matches)
        page, boxes = self._matches[self._match_index]
        if page < len(self._sizes):
            top = min(box[1] for box in boxes) * self._zoom
            left = min(box[0] for box in boxes) * self._zoom
            self.verticalScrollBar().setValue(
                round(self._offsets[page] + top - self.viewport().height() / 3)
            )
            bar = self.horizontalScrollBar()
            if not bar.value() <= left <= bar.value() + self.viewport().width() * 0.8:
                bar.setValue(round(left - self.viewport().width() / 4))
            # The page indicator names the page of the match, not the page above it.
            self._navigator._set(page)
        self.search_changed.emit(self._match_index, len(self._matches), "done")
        self.viewport().update()

    def _scrolled(self, value):
        visible = self._visible()
        if visible:
            self._navigator._set(visible.start)
        self.viewport().update()
        if not self._timer.isActive():
            self._timer.start()

    def _request_visible(self):
        if not self._document or self._document.status() != self._document.Status.Ready:
            return
        pending = set(self._requests.values())
        for page in self._visible():
            key = self._key(page)
            if key in self._cache or key in pending or key in self._failed:
                continue
            if len(self._requests) >= 2:
                break
            options = RemoteRenderOptions()
            options.setAnnotations(self._render_annotations)
            request = self._renderer.requestPage(page, QSize(*key[1:]), options)
            self._requests[request] = key
        # Text becomes selectable without waiting for the pointer: once the pixels
        # are in, fetch the text boxes of the pages nearest the middle of the view,
        # one request at a time. Fewer pages than the cache holds: no refetch loop.
        if self._prefetch_text and not self._requests and not self._layout_requests:
            middle = self.viewport().height() / 2
            nearest = sorted(
                self._visible(), key=lambda page: abs(self._rect(page).center().y() - middle)
            )[:_PREFETCH_PAGES]
            missing = next((page for page in nearest if page not in self._layouts), None)
            if missing is not None:
                self._layout_for(missing)

    def _rendered(self, page, size, image, options, request):
        key = self._requests.pop(request, None)
        if key is None:
            return
        if image.isNull():
            self._failed.add(key)
        elif key == self._key(page):
            self._cache[key] = image
            self._cache_bytes += image.sizeInBytes()
            while self._cache and self._cache_bytes > 48 * 1024**2:
                _, evicted = self._cache.popitem(last=False)
                self._cache_bytes -= evicted.sizeInBytes()
        self.viewport().update()
        if not self._timer.isActive():
            self._timer.start()

    def _page_point(self, position, page=None):
        """Page and point in page units under a viewport position."""
        if page is None:
            page = self.page_at(position)
            if page is None:
                return None, QPointF()
        return page, self.to_page(page, position)

    def _layout_for(self, page):
        layout = self._layouts.get(page)
        if layout is not None:
            self._layouts.move_to_end(page)
        elif page not in self._layout_requests.values() and self._document is not None:
            request = self._document.request("text_lines", page=page)
            self._layout_requests[request] = page
        return layout

    def _clear_selection(self):
        if self._selection_id is not None and self._document is not None:
            self._document.cancel_request(self._selection_id)
        self._selection_page = None
        self._selection_rects = []
        self._selection_text = ""
        self._selection_id = None
        self._copy_pending = False

    def _carets(self):
        layout = self._layouts.get(self._selection_page)
        if layout is None:
            return None
        start = layout.caret(self._anchor.x(), self._anchor.y())
        end = layout.caret(self._focus.x(), self._focus.y())
        return (layout, start, end) if start is not None and end is not None else None

    def _update_highlight(self):
        carets = self._carets()
        self._selection_rects = carets[0].highlight(carets[1], carets[2]) if carets else []
        self.viewport().update()

    def _request_selection(self):
        carets = self._carets()
        if carets is None or carets[1].key() == carets[2].key():
            self._selection_rects = []
            self.viewport().update()
            return
        # QtPdf completes the last character only when the points are in reading order.
        start, end = sorted(carets[1:], key=lambda caret: caret.key())
        self._selection_id = self._document.request(
            "selection", page=self._selection_page, points=[start.x, start.y, end.x, end.y]
        )

    def _update_cursor(self, position):
        page, point = self._page_point(position)
        if self._active_tool is not None:
            shape = self._active_tool.cursor(page, point)
            if shape is None:
                self.viewport().unsetCursor()
            else:
                self.viewport().setCursor(shape)
            return
        layout = self._layout_for(page) if page is not None else None
        if layout is not None and layout.is_text_at(point.x(), point.y()):
            self.viewport().setCursor(Qt.CursorShape.IBeamCursor)
        else:
            self.viewport().unsetCursor()

    def _tool_handles(self, handler, event):
        """Route an event to the active tool; True when it consumed it.

        During a drag, the page is the one the drag started on and the point
        is clamped to it: a rectangle dragged past the page edge ends at the
        edge, never on a neighbour nor at the page corner.
        """
        if self._active_tool is None:
            return False
        if self._tool_dragging and self._tool_page is not None:
            page = self._tool_page
            point = self.to_page(page, event.position())
            if self._document is not None and page < len(self._sizes):
                size = self._document.pagePointSize(page)
                point = QPointF(
                    min(max(point.x(), 0.0), size.width()),
                    min(max(point.y(), 0.0), size.height()),
                )
        else:
            page, point = self._page_point(event.position())
        return bool(handler(page, point, event))

    def mousePressEvent(self, event):
        if self._active_tool is not None and self._tool_handles(self._active_tool.press, event):
            self.setFocus()
            self._tool_dragging = True
            self._tool_page = self.page_at(event.position())
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self.setFocus()
            self._clear_selection()
            page, point = self._page_point(event.position())
            if page is not None:
                self._selection_page = page
                self._anchor = self._focus = point
                self._layout_for(page)
            self.viewport().update()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._active_tool is not None and (self._tool_dragging or not event.buttons()):
            if not event.buttons():
                # The tool's cursor follows the hover whether or not the tool
                # consumes the move (review of 6A).
                self._update_cursor(event.position())
            if self._tool_handles(self._active_tool.move, event):
                event.accept()
                return
            if not event.buttons():
                super().mouseMoveEvent(event)
                return
        if self._selection_page is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self._focus = self._page_point(event.position(), self._selection_page)[1]
            self._update_highlight()
        elif not event.buttons():
            self._update_cursor(event.position())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._active_tool is not None and self._tool_dragging:
            # The release is routed while the drag is still on (clamped to the
            # page it started on); the released button no longer counts after.
            consumed = self._tool_handles(self._active_tool.release, event)
            self._tool_dragging = bool(event.buttons() & ~event.button())
            if not self._tool_dragging:
                self._tool_page = None
            if consumed:
                event.accept()
                return
        if self._selection_page is not None and event.button() == Qt.MouseButton.LeftButton:
            self._focus = self._page_point(event.position(), self._selection_page)[1]
            self._update_highlight()
            self._request_selection()
        super().mouseReleaseEvent(event)

    def _result_ready(self, request, action, result):
        if action == "search" and request == self._search_id:
            self._search_id = None
            if not isinstance(result, dict) or "error" in result:
                # A worker failure (very long document, damaged file) is not "no result".
                self._matches = []
                self.search_changed.emit(-1, 0, "failed")
                self.viewport().update()
                return
            matches = result.get("matches", [])
            self._matches = [
                (page, [tuple(box) for box in boxes])
                for page, boxes in matches
                if page < len(self._sizes)
            ]
            self._match_index = -1
            if self._matches:
                self.show_match(1)
            else:
                self.search_changed.emit(-1, 0, "done")
                self.viewport().update()
        elif action == "text_lines":
            page = self._layout_requests.pop(request, None)
            if page is None:
                return
            rects = result.get("rects", []) if isinstance(result, dict) else []
            self._layouts[page] = TextLayout([tuple(rect) for rect in rects])
            while len(self._layouts) > _MAX_TEXT_LAYOUTS:
                self._layouts.popitem(last=False)
            if not self._timer.isActive():
                self._timer.start()
            if self.viewport().underMouse():
                self._update_cursor(self.viewport().mapFromGlobal(QCursor.pos()).toPointF())
            if page == self._selection_page:
                self._update_highlight()
                if not QGuiApplication.mouseButtons() & Qt.MouseButton.LeftButton:
                    self._request_selection()
        elif action == "selection" and request == self._selection_id:
            self._selection_text = result.get("text", "").replace("\r\n", "\n")
            bounds = result.get("bounds", [])
            # Exact character boxes replace the line-level highlight.
            self._selection_rects = [tuple(rect) for rect in bounds] if bounds else []
            self.viewport().update()
            if self._copy_pending:
                QApplication.clipboard().setText(self._selection_text)
                self._copy_pending = False

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            pixels = event.pixelDelta().y()
            angle = event.angleDelta().y()
            delta = (
                pixels
                if pixels and (QGuiApplication.platformName() != "xcb" or not angle)
                else angle
            )
            if delta:
                self.zoom_requested.emit(1.12 ** (delta / 120), event.position())
            event.accept()
            return
        pixels = event.pixelDelta()
        angles = event.angleDelta()
        # Qt documents X11 pixelDelta as driver-specific; prefer angle there.
        if not pixels.isNull() and (QGuiApplication.platformName() != "xcb" or angles.isNull()):
            dx, dy = pixels.x(), pixels.y()
        else:
            notch = min(180, max(96, self.viewport().height() * 0.33))
            dx, dy = angles.x() * notch / 120, angles.y() * notch / 120
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier and not dx:
            dx, dy = dy, 0
        moved = False
        if dx:
            moved = self._scroll_wheel_axis(self.horizontalScrollBar(), dx, "_wheel_remainder_x")
        if dy:
            moved = (
                self._scroll_wheel_axis(self.verticalScrollBar(), dy, "_wheel_remainder_y") or moved
            )
        if moved or dx or dy:
            event.accept()
        else:
            event.ignore()

    def _scroll_wheel_axis(self, bar, delta, remainder_name):
        motion = getattr(self, remainder_name) - delta
        if (bar.value() == bar.minimum() and motion < 0) or (
            bar.value() == bar.maximum() and motion > 0
        ):
            setattr(self, remainder_name, 0.0)
            return False
        pixels = trunc(motion)
        old = bar.value()
        bar.setValue(old + pixels)
        setattr(self, remainder_name, motion - pixels if bar.value() == old + pixels else 0.0)
        return bar.value() != old

    def keyPressEvent(self, event):
        if event.matches(QKeySequence.StandardKey.Copy):
            if self._selection_text:
                QApplication.clipboard().setText(self._selection_text)
            elif self._selection_id is not None or (
                self._selection_page is not None and self._selection_page not in self._layouts
            ):
                # The text arrives after the boxes of the page or the selection request.
                self._copy_pending = True
            event.accept()
        else:
            super().keyPressEvent(event)
