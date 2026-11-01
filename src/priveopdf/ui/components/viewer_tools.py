"""Skeleton shared by the functions that point at a place on a page (step 6A).

The reader (`IsolatedPdfView`) owns the only conversion between page points
and screen points, draws overlays above the page pixels and routes the mouse
to one active tool. Redaction (SEC05/SEC06) and watermarking (SEC13) plug into
these three seams and add no mouse, coordinate or drawing code of their own.
Without an active tool, the screen is a plain reader: text selection, search.

Page points are in PDF user-space points of the displayed page, with the
origin at the top-left corner of the page as shown (what the render worker
gives back for text boxes and search results); screen points are viewport
pixels.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QMouseEvent, QPainter, QPen


class PageOverlay(QObject):
    """Something drawn above one page's pixels, clipped to that page.

    `paint` receives the painter already clipped to the page rectangle, the
    page index, the page rectangle in viewport pixels and the zoom factor
    (pixels per page point). Emit `changed` when the drawing must be redone.
    """

    changed = Signal()

    def paint(self, painter: QPainter, page: int, rect: QRectF, zoom: float) -> None:
        del painter, page, rect, zoom


class ViewerTool(QObject):
    """The one tool receiving the mouse while it is active.

    Each handler gets the page under the pointer (`None` outside every page),
    the point in page units and the event; a handler returns True when it
    consumed the event, in which case the reader's own text selection does
    not run. While a press is held, `move` and `release` keep the page the
    press landed on and their point is clamped to that page. `cursor` names
    the pointer shape over a page, `None` for the reader's default. `changed`
    asks for a repaint.
    """

    changed = Signal()

    def press(self, page: int | None, point: QPointF, event: QMouseEvent) -> bool:
        del page, point, event
        return False

    def move(self, page: int | None, point: QPointF, event: QMouseEvent) -> bool:
        del page, point, event
        return False

    def release(self, page: int | None, point: QPointF, event: QMouseEvent) -> bool:
        del page, point, event
        return False

    def cursor(self, page: int | None, point: QPointF) -> Qt.CursorShape | None:
        del page, point
        return None

    def deactivated(self) -> None:
        """Called when another tool, or none, takes the mouse."""


class RedactionTool(ViewerTool):
    """Draws black-out rectangles on the page (SEC05) and lists them (6A seam).

    Areas are kept in page units ``(page, x, y, width, height)``; the drawing
    in progress is shown by the paired :class:`RedactionOverlay`. ``areas_changed``
    fires on every change, ``changed`` asks the view to repaint.
    """

    areas_changed = Signal()
    MIN_SIZE = 2.0

    def __init__(self) -> None:
        super().__init__()
        self._areas: list[tuple[int, float, float, float, float]] = []
        self._drawing: tuple[int, QPointF, QPointF] | None = None

    def areas(self) -> tuple[tuple[int, float, float, float, float], ...]:
        return tuple(self._areas)

    def drawing(self) -> tuple[int, QRectF] | None:
        if self._drawing is None:
            return None
        page, start, end = self._drawing
        return page, QRectF(start, end).normalized()

    def remove_last(self) -> None:
        if self._areas:
            self._areas.pop()
            self.areas_changed.emit()
            self.changed.emit()

    def clear(self) -> None:
        if self._areas or self._drawing is not None:
            self._areas.clear()
            self._drawing = None
            self.areas_changed.emit()
            self.changed.emit()

    def press(self, page: int | None, point: QPointF, event: QMouseEvent) -> bool:
        if page is None or event.button() != Qt.MouseButton.LeftButton:
            return False
        self._drawing = (page, point, point)
        self.changed.emit()
        return True

    def move(self, page: int | None, point: QPointF, event: QMouseEvent) -> bool:
        if self._drawing is None:
            return False
        start_page, start, _ = self._drawing
        # The rectangle stays on the page it started on.
        self._drawing = (start_page, start, point)
        self.changed.emit()
        return True

    def release(self, page: int | None, point: QPointF, event: QMouseEvent) -> bool:
        if self._drawing is None:
            return False
        start_page, start, _ = self._drawing
        rect = QRectF(start, point).normalized()
        self._drawing = None
        if rect.width() >= self.MIN_SIZE and rect.height() >= self.MIN_SIZE:
            self._areas.append(
                (start_page, max(0.0, rect.x()), max(0.0, rect.y()), rect.width(), rect.height())
            )
            self.areas_changed.emit()
        self.changed.emit()
        return True

    def cursor(self, page: int | None, point: QPointF) -> Qt.CursorShape | None:
        return Qt.CursorShape.CrossCursor if page is not None else None

    def deactivated(self) -> None:
        self._drawing = None


class RedactionOverlay(PageOverlay):
    """Paints the areas of a :class:`RedactionTool` above the page: black at
    export, shown translucent with a border so the text beneath stays readable
    while choosing."""

    def __init__(self, tool: RedactionTool, color: QColor | None = None) -> None:
        super().__init__()
        self._tool = tool
        self._color = color if color is not None else QColor(0, 0, 0)
        tool.changed.connect(self.changed)

    def paint(self, painter: QPainter, page: int, rect: QRectF, zoom: float) -> None:
        painter.save()
        fill = QColor(self._color)
        fill.setAlpha(150)
        painter.setBrush(fill)
        painter.setPen(QPen(self._color, 1))
        for area_page, x, y, width, height in self._tool.areas():
            if area_page == page:
                painter.drawRect(
                    QRectF(rect.x() + x * zoom, rect.y() + y * zoom, width * zoom, height * zoom)
                )
        drawing = self._tool.drawing()
        if drawing is not None and drawing[0] == page:
            box = drawing[1]
            pen = QPen(self._color, 1, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(
                QRectF(
                    rect.x() + box.x() * zoom,
                    rect.y() + box.y() * zoom,
                    box.width() * zoom,
                    box.height() * zoom,
                )
            )
        painter.restore()


class WatermarkOverlay(PageOverlay):
    """Paints the preview of a traceability watermark (SEC13) above every page,
    with the layout the engine will write (`domain.watermark_layout`). The
    preview uses the closest bold sans-serif font the system has; the output
    names the standard Helvetica-Bold font."""

    def __init__(self, color: QColor | None = None) -> None:
        super().__init__()
        self._text = ""
        self._layout = "diagonal"
        self._opacity = 0.3
        # The engine paints gray 0.25: the preview shows the same ink.
        self._color = color if color is not None else QColor(64, 64, 64)

    def set_watermark(self, text: str, layout: str, opacity: float) -> None:
        self._text, self._layout, self._opacity = text, layout, opacity
        self.changed.emit()

    def paint(self, painter: QPainter, page: int, rect: QRectF, zoom: float) -> None:
        del page
        from priveopdf.domain.watermark_layout import placements, text_width

        try:
            size, angle, origins = placements(
                self._text, self._layout, (0.0, 0.0, rect.width() / zoom, rect.height() / zoom)
            )
        except ValueError:
            return
        painter.save()
        color = QColor(self._color)
        color.setAlphaF(self._opacity)
        painter.setPen(color)
        font = QFont("Helvetica", -1, QFont.Weight.Bold)
        font.setPixelSize(max(1, round(size * zoom)))
        # The copies are placed for Helvetica-Bold widths: stretch the system
        # font to the same line length so the preview sits where the output will.
        measured = QFontMetricsF(font).horizontalAdvance(self._text)
        wanted = text_width(self._text, size) * zoom
        if measured > 0 and wanted > 0:
            font.setStretch(max(1, min(4000, round(100 * wanted / measured))))
        painter.setFont(font)
        height = rect.height() / zoom
        for x, y in origins:
            painter.save()
            # Page points, y up, to viewport pixels, y down.
            painter.translate(rect.x() + x * zoom, rect.y() + (height - y) * zoom)
            painter.rotate(-angle)
            painter.drawText(QPointF(0, 0), self._text)
            painter.restore()
        painter.restore()
