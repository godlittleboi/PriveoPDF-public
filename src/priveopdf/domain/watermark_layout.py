"""Geometry of the traceability watermark (SEC13), shared by the engine that
writes it and the preview that shows it.

Text metrics come from the standard Helvetica-Bold font (WinAnsi encoding)
that the engine names in the output; the preview draws with the closest font
the system has, so it approximates the printed result.
"""

from __future__ import annotations

import math

from priveopdf.domain.jobs import WATERMARK_LAYOUTS, WATERMARK_STRENGTHS, validate_watermark_text

# Opacity of the text (PDF constant alpha), per strength.
OPACITIES = dict(zip(WATERMARK_STRENGTHS, (0.15, 0.3, 0.5), strict=True))
GRAY = 0.25
_TILED_ANGLE_DEGREES = 30.0
# Advance widths of Helvetica-Bold for WinAnsiEncoding codes 32 to 255 (1/1000
# em), from the Adobe Core 14 metrics; 0 marks an unassigned code.
_WIDTHS = (
    278, 333, 474, 556, 556, 889, 722, 238, 333, 333, 389, 584, 278, 333, 278, 278,
    556, 556, 556, 556, 556, 556, 556, 556, 556, 556, 333, 333, 584, 584, 584, 611,
    975, 722, 722, 722, 722, 667, 611, 778, 722, 278, 556, 722, 611, 833, 722, 778,
    667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 333, 278, 333, 584, 556,
    333, 556, 611, 556, 611, 556, 333, 611, 611, 278, 278, 556, 278, 889, 611, 611,
    611, 611, 389, 556, 333, 611, 556, 778, 556, 556, 500, 389, 280, 389, 584, 0,
    556, 0, 278, 556, 500, 1000, 556, 556, 333, 1000, 667, 333, 1000, 0, 611, 0,
    0, 278, 278, 500, 500, 350, 556, 1000, 333, 1000, 556, 333, 944, 0, 500, 667,
    278, 333, 556, 556, 556, 556, 280, 556, 333, 737, 370, 556, 584, 333, 737, 333,
    400, 584, 333, 333, 333, 611, 556, 278, 333, 333, 365, 556, 834, 834, 834, 611,
    722, 722, 722, 722, 722, 722, 1000, 722, 667, 667, 667, 667, 278, 278, 278, 278,
    722, 722, 778, 778, 778, 778, 778, 584, 778, 722, 722, 722, 722, 667, 667, 611,
    556, 556, 556, 556, 556, 556, 889, 556, 556, 556, 556, 556, 278, 278, 278, 278,
    611, 611, 611, 611, 611, 611, 611, 584, 611, 611, 611, 611, 611, 556, 611, 556,
)  # fmt: skip


def encode_text(text: str) -> bytes:
    """The text as WinAnsi bytes; refuses empty, long or unsupported text."""
    encoded = validate_watermark_text(text).encode("cp1252")
    if any(_WIDTHS[code - 32] == 0 for code in encoded):
        raise ValueError("watermark text uses an unsupported character")
    return encoded


def text_width(text: str, size: float = 1.0) -> float:
    """Advance width of the text in Helvetica-Bold at `size` points."""
    return sum(_WIDTHS[code - 32] for code in encode_text(text)) * size / 1000


def placements(
    text: str, layout: str, box: tuple[float, float, float, float], rotation: int = 0
) -> tuple[float, float, tuple[tuple[float, float], ...]]:
    """Font size, text angle (degrees, counter-clockwise, y up) and the origins
    of every copy of the text, in the coordinates of `box` (x0, y0, x1, y1).

    `rotation` is the page's /Rotate: the text reads upright on the displayed
    page. The preview passes the displayed page and rotation 0.
    """
    if layout not in WATERMARK_LAYOUTS:
        raise ValueError("unknown watermark layout")
    width, height = box[2] - box[0], box[3] - box[1]
    unit_width = text_width(text)
    diagonal = math.hypot(width, height)
    shown_w, shown_h = (height, width) if rotation in (90, 270) else (width, height)
    if layout == "diagonal":
        size = min(0.8 * diagonal / unit_width, 0.16 * min(width, height))
        angle = math.degrees(math.atan2(shown_h, shown_w))
    else:
        size = min(0.3 * diagonal / unit_width, 0.05 * min(width, height))
        angle = _TILED_ANGLE_DEGREES
    size = max(4.0, size)
    # /Rotate turns the page clockwise on display: turn the text the other way.
    angle = (angle + rotation) % 360
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    line = unit_width * size
    radians = math.radians(angle)
    cos, sin = math.cos(radians), math.sin(radians)

    def origin(along: float, across: float) -> tuple[float, float]:
        # `along` runs with the baseline, `across` perpendicular to it.
        return (cx + along * cos - across * sin, cy + along * sin + across * cos)

    if layout == "diagonal":
        return size, angle, (origin(-line / 2, -size * 0.35),)
    radius = diagonal / 2 + line
    # Bounded number of copies whatever the page: at most 15 x 15 cells.
    step_along = max(line + 3 * size, radius / 6)
    step_across = max(6 * size, radius / 6)
    rows = int(radius / step_across) + 1
    columns = int(radius / step_along) + 1
    copies = tuple(
        origin(column * step_along + (row % 2) * step_along / 2 - line / 2, row * step_across)
        for row in range(-rows, rows + 1)
        for column in range(-columns, columns + 1)
    )
    return size, angle, copies
