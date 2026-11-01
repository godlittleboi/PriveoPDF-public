"""Text selection geometry from the text boxes of one page (no PDF parsing here).

The render worker sends the boxes QtPdf reports for a page's text, in reading
order. Boxes that overlap across the reading direction form a line. A pointer
position is attached to the nearest line, so a drag may start or end in a
margin, and the highlight follows the lines between both ends, as in an
ordinary PDF reader.

Computations happen in a reading frame where text runs along +u and lines
follow each other along +v. On a page displayed turned (/Rotate, or a sideways
scan with its OCR layer), the screen axes are swapped and/or reversed.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise

Rect = tuple[float, float, float, float]  # x, y, width, height in page points

# The snapped point sits this far inside a box, so QtPdf hits a character.
_INSET = 0.6
_HOVER_MARGIN = 2.0


@dataclass(frozen=True)
class Caret:
    line: int
    position: float  # along the reading direction
    x: float
    y: float

    def key(self) -> tuple[int, float]:
        return self.line, self.position


@dataclass(frozen=True)
class _Line:
    boxes: tuple[Rect, ...]  # in the reading frame: (u, v, length, thickness)
    start: float
    top: float
    end: float
    bottom: float


@dataclass(frozen=True)
class _Frame:
    vertical: bool = False
    reading: int = 1  # +1 when text runs towards growing screen coordinates
    lines: int = 1  # +1 when lines follow each other towards growing coordinates

    def point(self, x: float, y: float) -> tuple[float, float]:
        along, across = (y, x) if self.vertical else (x, y)
        return self.reading * along, self.lines * across

    def page(self, u: float, v: float) -> tuple[float, float]:
        along, across = self.reading * u, self.lines * v
        return (across, along) if self.vertical else (along, across)

    def rect(self, rect: Rect, *, to_page: bool = False) -> Rect:
        convert = self.page if to_page else self.point
        ax, ay = convert(rect[0], rect[1])
        bx, by = convert(rect[0] + rect[2], rect[1] + rect[3])
        return min(ax, bx), min(ay, by), abs(bx - ax), abs(by - ay)


class TextLayout:
    def __init__(self, rects: list[Rect]) -> None:
        self._frame = _detect_frame(rects)
        self._lines = tuple(
            _make_line(boxes) for boxes in _group_lines([self._frame.rect(r) for r in rects])
        )

    def is_empty(self) -> bool:
        return not self._lines

    def is_text_at(self, x: float, y: float) -> bool:
        u, v = self._frame.point(x, y)
        return any(
            box[0] - _HOVER_MARGIN <= u <= box[0] + box[2] + _HOVER_MARGIN
            and box[1] - _HOVER_MARGIN <= v <= box[1] + box[3] + _HOVER_MARGIN
            for line in self._lines
            for box in line.boxes
        )

    def caret(self, x: float, y: float) -> Caret | None:
        """The nearest point inside a text box, on the line the pointer designates.

        Before a line, the caret goes to its start; after it, to its end;
        level with it, to the nearest character.
        """
        if not self._lines:
            return None
        u, v = self._frame.point(x, y)
        index = min(range(len(self._lines)), key=lambda i: _distance(self._lines[i], u, v))
        line = self._lines[index]
        if v < line.top:
            u = line.start
        elif v > line.bottom:
            u = line.end
        box = min(line.boxes, key=lambda b: _gap(b, u))
        if box[2] <= 2 * _INSET:
            inside = box[0] + box[2] / 2
        else:
            inside = min(max(u, box[0] + _INSET), box[0] + box[2] - _INSET)
        px, py = self._frame.page(inside, box[1] + box[3] / 2)
        return Caret(index, inside, px, py)

    def highlight(self, start: Caret, end: Caret) -> list[Rect]:
        """Page rectangles covering the text between two carets, line by line."""
        first, last = sorted((start, end), key=Caret.key)
        rects: list[Rect] = []
        for index in range(first.line, last.line + 1):
            line = self._lines[index]
            low = first.position if index == first.line else line.start
            high = last.position if index == last.line else line.end
            if high > low:
                reading = (low, line.top, high - low, line.bottom - line.top)
                rects.append(self._frame.rect(reading, to_page=True))
        return rects


def _detect_frame(rects: list[Rect]) -> _Frame:
    vertical = _reads_vertically(rects)
    frame = _Frame(vertical)
    lines = _group_lines([frame.rect(r) for r in rects])
    # Within a line, boxes follow the reading direction; lines follow each other.
    steps = [b[0] - a[0] for line in lines for a, b in pairwise(line)]
    reading = -1 if sum(1 for s in steps if s < 0) > sum(1 for s in steps if s > 0) else 1
    centres = [min(b[1] for b in line) + max(b[1] + b[3] for b in line) for line in lines]
    gaps = [b - a for a, b in pairwise(centres)]
    order = -1 if sum(1 for g in gaps if g < 0) > sum(1 for g in gaps if g > 0) else 1
    return _Frame(vertical, reading, order)


def _reads_vertically(rects: list[Rect]) -> bool:
    """Whether the text runs along y on screen.

    A run of several characters is longer along its reading direction: the shape
    of each box is the main evidence. Consecutive boxes side by side along x or
    along y only weigh in a tie, since a column of short entries (amounts, dates)
    stacks horizontal text.
    """
    score = 0
    for a, b in pairwise(rects):
        if _overlap(a[1], a[3], b[1], b[3]) > 0.5 * min(a[3], b[3]):
            score += 1
        elif _overlap(a[0], a[2], b[0], b[2]) > 0.5 * min(a[2], b[2]):
            score -= 1
    for _x, _y, width, height in rects:
        if width > 1.5 * height:
            score += 4 if width > 4 * height else 2
        elif height > 1.5 * width:
            score -= 4 if height > 4 * width else 2
    return score < 0


def _group_lines(rects: list[Rect]) -> list[list[Rect]]:
    lines: list[list[Rect]] = []
    for rect in rects:
        if lines and _same_line(lines[-1][-1], rect):
            lines[-1].append(rect)
        else:
            lines.append([rect])
    return lines


def _overlap(start_a: float, size_a: float, start_b: float, size_b: float) -> float:
    return min(start_a + size_a, start_b + size_b) - max(start_a, start_b)


def _same_line(previous: Rect, rect: Rect) -> bool:
    return _overlap(previous[1], previous[3], rect[1], rect[3]) > 0.5 * min(previous[3], rect[3])


def _make_line(boxes: list[Rect]) -> _Line:
    return _Line(
        tuple(boxes),
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[0] + b[2] for b in boxes),
        max(b[1] + b[3] for b in boxes),
    )


def _gap(box: Rect, u: float) -> float:
    return max(box[0] - u, 0.0, u - (box[0] + box[2]))


def _distance(line: _Line, u: float, v: float) -> float:
    """Distance across lines first: a margin drag stays on the line it is level with."""
    across = max(line.top - v, 0.0, v - line.bottom)
    along = max(line.start - u, 0.0, u - line.end)
    return across * 1000 + along
