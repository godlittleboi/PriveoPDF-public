"""Destructive redaction (SEC05) and its independent verification (SEC06).

The redacted document is a photocopy: every page is rendered to pixels, the
chosen areas are painted black in those pixels, and a new PDF is built from
pixels only (`pdf_photocopy`). No object of the source survives, so nothing
under a black area can remain: no text, no vector, no image, no annotation,
no hidden layer. The price is the one of a photocopy: the text is no longer
selectable (the OCR tool can add a text layer afterwards, which finds nothing
under a black area).

Verification (SEC06) is independent of the construction: the output is
re-opened, every object is allow-listed, every page is re-rendered by the PDF
engine and compared pixel for pixel, no page carries extractable text, and
every requested area is uniformly black in that independent rendering.

Areas are given in page units: PDF points of the displayed page, origin at
its top-left corner, as the reader hands them (`IsolatedPdfView.to_page`).
The reader works in the unscaled geometry the PDF engine reports; a page
with `/UserUnit` is rendered at its physical size, so the areas are scaled by
that unit before they meet the pixels.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

from priveopdf.domain.errors import PdfModError
from priveopdf.engine.pdf_photocopy import (
    DPI,
    ExpectedPage,
    PhotocopyError,
    PixelPage,
    build_image_pdf,
    open_renderer,
    render_pixels,
    source_geometry,
    verify_image_pdf,
)

MAX_AREAS = 500
# One pixel of margin all around each area, so an anti-aliased edge of the
# hidden content never survives at the border of the black box.
MARGIN_PX = 1


class RedactionError(PdfModError):
    user_message = "Le caviardage n'a pas pu etre verifie. Aucun fichier cree."
    technical_code = "redaction_integrity"


class RedactionAreaError(RedactionError):
    user_message = "Une zone a caviarder est hors de sa page ou invalide."
    technical_code = "redaction_area_invalid"


@dataclass(frozen=True)
class RedactionArea:
    """A rectangle to black out, in page units of the displayed page."""

    page: int
    x: float
    y: float
    width: float
    height: float

    def __post_init__(self) -> None:
        if type(self.page) is not int or self.page < 0:
            raise RedactionAreaError()
        values = (self.x, self.y, self.width, self.height)
        if any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in values):
            raise RedactionAreaError()
        if self.width <= 0 or self.height <= 0 or self.x < 0 or self.y < 0:
            raise RedactionAreaError()

    def pixel_box(
        self, geometry: tuple[float, float], size: tuple[int, int], unit: float = 1.0
    ) -> tuple[int, int, int, int]:
        """Pixel rectangle (left, top, right, bottom; right/bottom excluded) on a
        page of `geometry` physical points rendered at `size` pixels, with the
        margin. The area is in the reader's unscaled units: `unit` is the page's
        `/UserUnit` (review of B5)."""
        width_pt, height_pt = geometry
        width_px, height_px = size
        if not math.isfinite(unit) or unit <= 0:
            raise RedactionAreaError()
        x, y, width, height = (v * unit for v in (self.x, self.y, self.width, self.height))
        if x + width > width_pt + 0.01 or y + height > height_pt + 0.01:
            raise RedactionAreaError()
        scale_x, scale_y = width_px / width_pt, height_px / height_pt
        left = max(0, math.floor(x * scale_x) - MARGIN_PX)
        top = max(0, math.floor(y * scale_y) - MARGIN_PX)
        right = min(width_px, math.ceil((x + width) * scale_x) + MARGIN_PX)
        bottom = min(height_px, math.ceil((y + height) * scale_y) + MARGIN_PX)
        if right <= left or bottom <= top:
            raise RedactionAreaError()
        return left, top, right, bottom


@dataclass(frozen=True)
class RedactionReport:
    """What the independent verification established on the written file."""

    pages: int
    areas: int
    redacted_pages: int
    black_pixels: int
    objects: int


def page_user_units(source_pdf) -> tuple[float, ...]:  # noqa: ANN001 - pikepdf.Pdf
    """``/UserUnit`` of every page (1 when absent); invalid values are refused
    earlier by ``source_geometry``."""
    return tuple(float(page.obj.get("/UserUnit", 1)) for page in source_pdf.pages)


def pixel_boxes(
    areas: tuple[RedactionArea, ...],
    geometry: tuple[tuple[float, float], ...],
    units: tuple[float, ...],
) -> dict[int, list[tuple[int, int, int, int]]]:
    """Per page, the pixel boxes of the areas at the photocopy's resolution."""
    validate_areas(areas, len(geometry))
    boxes: dict[int, list[tuple[int, int, int, int]]] = {}
    for area in areas:
        width_pt, height_pt = geometry[area.page]
        size = (math.ceil(width_pt * DPI / 72), math.ceil(height_pt * DPI / 72))
        boxes.setdefault(area.page, []).append(
            area.pixel_box(geometry[area.page], size, units[area.page])
        )
    return boxes


def validate_areas(areas: tuple[RedactionArea, ...], page_count: int) -> None:
    if not areas or len(areas) > MAX_AREAS:
        raise RedactionAreaError()
    if any(area.page >= page_count for area in areas):
        raise RedactionAreaError()


def black_out(page: PixelPage, boxes: list[tuple[int, int, int, int]]) -> PixelPage:
    """The page pixels with each box painted pure black."""
    if not boxes:
        return page
    rows = bytearray(page.pixels)
    stride = page.width * 3
    for left, top, right, bottom in boxes:
        run = b"\x00" * ((right - left) * 3)
        for y in range(top, bottom):
            start = y * stride + left * 3
            rows[start : start + len(run)] = run
    return PixelPage(page.width_points, page.height_points, page.width, page.height, bytes(rows))


def redact_to_candidate(
    source_fd_path: Path,
    source_pdf,  # pikepdf.Pdf, already open and checked by the caller
    areas: tuple[RedactionArea, ...],
    candidate: Path,
    progress: Callable[[int, int], None] = lambda *_: None,
) -> tuple[tuple[ExpectedPage, ...], tuple[float, ...]]:
    """Render every page, black out the areas, write the pixels-only PDF.

    Returns what the verifier must find: the expected pages and the
    ``/UserUnit`` of every page, which the verifier applies to the areas.
    """
    renderer = open_renderer(source_fd_path)
    try:
        geometry = source_geometry(source_pdf, renderer)
        units = page_user_units(source_pdf)
        boxes = pixel_boxes(areas, geometry, units)
        total = 2 * len(geometry)

        def pages() -> Iterator[PixelPage]:
            for index, dimensions in enumerate(geometry):
                rendered = render_pixels(renderer, index, dimensions)
                yield black_out(rendered, boxes.get(index, []))
                progress(index + 1, total)

        expected = build_image_pdf(pages(), candidate)
    finally:
        renderer.close()
    return expected, units


def verify_redaction(
    candidate: Path,
    expected: tuple[ExpectedPage, ...],
    areas: tuple[RedactionArea, ...],
    units: tuple[float, ...],
    progress: Callable[[int, int], None] = lambda *_: None,
) -> RedactionReport:
    """SEC06: allow-list the file, re-render it, find no text, find black areas.

    The black rectangles are derived again here from the areas, as fractions
    of the written page's MediaBox, not from the boxes the construction used
    (review of B5): a construction that misplaced an area is caught.
    """
    import pikepdf

    try:
        verify_image_pdf(candidate, expected, progress=progress)
    except PhotocopyError as exc:
        raise RedactionError() from exc
    if not areas or len(units) != len(expected):
        raise RedactionError()
    by_page: dict[int, list[RedactionArea]] = {}
    for area in areas:
        if area.page >= len(expected):
            raise RedactionError()
        by_page.setdefault(area.page, []).append(area)
    with pikepdf.open(candidate, attempt_recovery=False, suppress_warnings=True) as pdf:
        objects = sum(1 for _ in pdf.objects)
        boxes_pt = {index: tuple(float(v) for v in pdf.pages[index].mediabox) for index in by_page}
    renderer = open_renderer(candidate)
    black = 0
    try:
        for index, page_areas in by_page.items():
            want = expected[index]
            rendered = render_pixels(renderer, index, (want.width_points, want.height_points))
            if rendered.width != want.width or rendered.height != want.height:
                raise RedactionError()
            left_pt, top_pt, right_pt, bottom_pt = boxes_pt[index]
            page_w, page_h = right_pt - left_pt, bottom_pt - top_pt
            if page_w <= 0 or page_h <= 0:
                raise RedactionError()
            stride = rendered.width * 3
            unit = units[index]
            for area in page_areas:
                # Fractions of the written page: independent of the source geometry.
                x0, y0 = area.x * unit / page_w, area.y * unit / page_h
                x1 = (area.x + area.width) * unit / page_w
                y1 = (area.y + area.height) * unit / page_h
                if x1 > 1.0001 or y1 > 1.0001:
                    raise RedactionError()
                left = math.floor(x0 * rendered.width)
                right = min(rendered.width, math.ceil(x1 * rendered.width))
                top = math.floor(y0 * rendered.height)
                bottom = min(rendered.height, math.ceil(y1 * rendered.height))
                if right <= left or bottom <= top:
                    raise RedactionError()
                for y in range(top, bottom):
                    row = rendered.pixels[y * stride + left * 3 : y * stride + right * 3]
                    if row.count(0) != len(row):
                        raise RedactionError()
                black += (right - left) * (bottom - top)
            if renderer.getAllText(index).text():
                raise RedactionError()
    finally:
        renderer.close()
    return RedactionReport(
        pages=len(expected),
        areas=len(areas),
        redacted_pages=len(by_page),
        black_pixels=black,
        objects=objects,
    )
