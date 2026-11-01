"""Traceability watermark (SEC13) and its verification after export.

The watermark is a visible text drawn into the content of every page: the
page's content streams are merged into a single stream, wrapped in a saved
graphics state, and the text is appended to that same stream with a standard
font (Helvetica-Bold, WinAnsi) and a transparency state. It is not an
annotation, a separate stream, an optional content group or a form object
that a viewer or a one-line script removes: taking it out means editing the
page content itself. The source is never modified.

What this does not promise, and the user documentation says so: no visible
watermark in a PDF survives a deliberate re-edit or a rasterisation. The
promise is resistance to trivial removal, not a DRM.

Verification after export reopens the written file: same number of pages, no
annotation added, the watermark text found by the PDF engine on every page,
and every page rendered differently from the source page.
"""

from __future__ import annotations

import io
import math
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pikepdf

from priveopdf.domain.errors import PdfModError
from priveopdf.domain.jobs import WATERMARK_LAYOUTS, WATERMARK_STRENGTHS, validate_watermark_text
from priveopdf.domain.watermark_layout import GRAY, OPACITIES, encode_text, placements
from priveopdf.engine.pdf_photocopy import (
    MAX_PAGE_PIXELS,
    MAX_PAGES,
    open_renderer,
    render_pixels,
)

# Independent rendering for the verification: low resolution, every page.
VERIFY_DPI = 24
_FONT_NAME = "/Helvetica-Bold"


class WatermarkError(PdfModError):
    user_message = "Le filigrane n'a pas pu etre verifie. Aucun fichier cree."
    technical_code = "watermark_integrity"


class WatermarkTextError(WatermarkError):
    user_message = (
        "Le texte du filigrane est vide, trop long ou contient un caractere non pris en charge."
    )
    technical_code = "watermark_text_invalid"


class WatermarkLimitError(WatermarkError):
    user_message = "Ce PDF depasse les limites du filigrane."
    technical_code = "watermark_limit"


class WatermarkUnsupportedError(WatermarkError):
    user_message = "Une page de ce PDF a une taille ou une rotation non prise en charge."
    technical_code = "watermark_unsupported"


@dataclass(frozen=True)
class WatermarkSpec:
    """What to draw: the text, its layout and its strength."""

    text: str
    layout: str = "diagonal"
    strength: str = "medium"

    def __post_init__(self) -> None:
        try:
            encode_text(self.text)
        except ValueError:
            raise WatermarkTextError() from None
        if self.layout not in WATERMARK_LAYOUTS or self.strength not in WATERMARK_STRENGTHS:
            raise WatermarkTextError()


@dataclass(frozen=True)
class WatermarkReport:
    """What the verification established on the written file."""

    pages: int
    changed_pixels: int


def _escape(encoded: bytes) -> bytes:
    return encoded.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def _f(value: float) -> str:
    return f"{value:.3f}".rstrip("0").rstrip(".") or "0"


def page_box(page: pikepdf.Page) -> tuple[float, float, float, float]:
    """Visible box (CropBox within MediaBox) in user space: x0, y0, x1, y1."""
    media, crop = tuple(map(float, page.mediabox)), tuple(map(float, page.cropbox))
    box = (
        max(media[0], crop[0]),
        max(media[1], crop[1]),
        min(media[2], crop[2]),
        min(media[3], crop[3]),
    )
    if not all(math.isfinite(v) for v in box) or box[2] - box[0] <= 1 or box[3] - box[1] <= 1:
        raise WatermarkUnsupportedError()
    width, height = box[2] - box[0], box[3] - box[1]
    if width > 14400 or height > 14400:
        raise WatermarkUnsupportedError()
    # The verification renders the page: refuse before writing what it could
    # not render (review of B6).
    if math.ceil(width * VERIFY_DPI / 72) * math.ceil(height * VERIFY_DPI / 72) > MAX_PAGE_PIXELS:
        raise WatermarkUnsupportedError()
    return box


def _rotation(page: pikepdf.Page) -> int:
    rotation = page.obj.get("/Rotate", 0)
    if not isinstance(rotation, int) or rotation % 90:
        raise WatermarkUnsupportedError()
    return int(rotation) % 360


def _balance(stream: pikepdf.Object | None) -> tuple[int, int, bool]:
    """(excess Q, unclosed q, text object left open) of a content stream, so the
    watermark is isolated whatever the source leaves behind (review of B6)."""
    if not isinstance(stream, pikepdf.Stream):
        return 0, 0, False
    try:
        operators = [str(op) for _operands, op in pikepdf.parse_content_stream(stream)]
    except (pikepdf.PdfError, ValueError, TypeError):
        return 0, 0, False
    depth = excess = 0
    in_text = False
    for operator in operators:
        if operator == "q":
            depth += 1
        elif operator == "Q":
            if depth:
                depth -= 1
            else:
                excess += 1
        elif operator == "BT":
            in_text = True
        elif operator == "ET":
            in_text = False
    return excess, depth, in_text


def _free_name(used: pikepdf.Dictionary, stem: str, resource: pikepdf.Object) -> str:
    """A resource name the page does not use yet (Codex review of B6): an
    existing `/Fwm` of the source, or of an earlier watermark, is kept. A name
    already bound to this very object (resources shared by pages) is reused."""
    name = f"/{stem}"
    index = 1
    while name in used:
        if used[name].objgen == resource.objgen:
            return name
        name = f"/{stem}{index}"
        index += 1
    return name


def content_for(
    spec: WatermarkSpec,
    box: tuple[float, float, float, float],
    rotation: int,
    font_name: str = "/Fwm",
    state_name: str = "/GSwm",
) -> bytes:
    """The content stream fragment that draws the watermark on one page."""
    size, angle, origins = placements(spec.text, spec.layout, box, rotation)
    radians = math.radians(angle)
    cos, sin = math.cos(radians), math.sin(radians)
    text = _escape(encode_text(spec.text))  # same normalisation as the job
    parts = [
        b"q %s gs %s g BT %s %s Tf"
        % (state_name.encode(), _f(GRAY).encode(), font_name.encode(), _f(size).encode())
    ]
    for x, y in origins:
        matrix = " ".join(_f(v) for v in (cos, sin, -sin, cos, x, y))
        parts.append(b"%s Tm (%s) Tj" % (matrix.encode(), text))
    parts.append(b"ET Q")
    return b"\n".join(parts) + b"\n"


def _own_resources(pdf: pikepdf.Pdf, page: pikepdf.Page) -> pikepdf.Dictionary:
    """The page's own /Resources, copied from an ancestor when inherited."""
    resources = page.obj.get("/Resources")
    if isinstance(resources, pikepdf.Dictionary):
        return resources
    node = page.obj.get("/Parent")
    inherited = None
    while isinstance(node, pikepdf.Dictionary) and inherited is None:
        inherited = node.get("/Resources")
        node = node.get("/Parent")
    copied = pikepdf.Dictionary()
    if isinstance(inherited, pikepdf.Dictionary):
        for key, value in inherited.items():
            copied[key] = value
    page.obj["/Resources"] = pdf.make_indirect(copied)
    resources = page.obj["/Resources"]
    if not isinstance(resources, pikepdf.Dictionary):
        raise WatermarkError()
    return resources


def apply_watermark(pdf: pikepdf.Pdf, spec: WatermarkSpec) -> int:
    """Draw the watermark into the content of every page of the open `pdf`.

    Returns the number of pages marked. The caller writes the result to its
    candidate file; the source file is untouched.
    """
    if not 1 <= len(pdf.pages) <= MAX_PAGES:
        raise WatermarkLimitError()
    font = pdf.make_indirect(
        pikepdf.Dictionary(
            Type=pikepdf.Name.Font,
            Subtype=pikepdf.Name.Type1,
            BaseFont=pikepdf.Name(_FONT_NAME),
            Encoding=pikepdf.Name.WinAnsiEncoding,
        )
    )
    alpha = OPACITIES[spec.strength]
    state = pdf.make_indirect(
        pikepdf.Dictionary(Type=pikepdf.Name.ExtGState, CA=alpha, ca=alpha, BM=pikepdf.Name.Normal)
    )
    for page in pdf.pages:
        rotation = _rotation(page)
        box = page_box(page)
        resources = _own_resources(pdf, page)
        fonts = resources.get("/Font")
        if not isinstance(fonts, pikepdf.Dictionary):
            fonts = resources["/Font"] = pikepdf.Dictionary()
        states = resources.get("/ExtGState")
        if not isinstance(states, pikepdf.Dictionary):
            states = resources["/ExtGState"] = pikepdf.Dictionary()
        font_name = _free_name(fonts, "Fwm", font)
        state_name = _free_name(states, "GSwm", state)
        fonts[font_name] = font
        states[state_name] = state
        page.contents_coalesce()
        existing = page.obj.get("/Contents")
        original = existing.read_bytes() if isinstance(existing, pikepdf.Stream) else b""
        # One stream: the original drawing, isolated whatever it leaves open or
        # pops in excess, then the watermark.
        excess, unclosed, in_text = _balance(existing)
        merged = (
            b"q\n" * (1 + excess)
            + original
            + (b"\nET" if in_text else b"")
            + b"\nQ" * (1 + unclosed)
            + b"\n"
            + content_for(spec, box, rotation, font_name, state_name)
        )
        page.obj["/Contents"] = pdf.make_stream(merged)
    return len(pdf.pages)


def _squeezed(text: str) -> str:
    return "".join(text.split())


def _reference_ink(
    spec: WatermarkSpec, shapes: tuple[tuple[float, float, int], ...]
) -> dict[tuple[float, float, int], int]:
    """Channels the watermark alone darkens on a blank page of each shape
    (width, height, rotation), rendered like the verification renders."""
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice
    from PySide6.QtPdf import QPdfDocument

    pdf = pikepdf.Pdf.new()
    font = pdf.make_indirect(
        pikepdf.Dictionary(
            Type=pikepdf.Name.Font,
            Subtype=pikepdf.Name.Type1,
            BaseFont=pikepdf.Name(_FONT_NAME),
            Encoding=pikepdf.Name.WinAnsiEncoding,
        )
    )
    alpha = OPACITIES[spec.strength]
    state = pdf.make_indirect(pikepdf.Dictionary(Type=pikepdf.Name.ExtGState, CA=alpha, ca=alpha))
    for width, height, rotation in shapes:
        page = pdf.add_blank_page(page_size=(width, height))
        if rotation:
            page.obj["/Rotate"] = rotation
        page.obj["/Resources"] = pikepdf.Dictionary(
            Font=pikepdf.Dictionary(Fwm=font), ExtGState=pikepdf.Dictionary(GSwm=state)
        )
        page.obj["/Contents"] = pdf.make_stream(content_for(spec, (0, 0, width, height), rotation))
    data = io.BytesIO()
    pdf.save(data)
    buffer = QBuffer()
    buffer.setData(QByteArray(data.getvalue()))
    buffer.open(QIODevice.OpenModeFlag.ReadOnly)
    document = QPdfDocument()
    # Loading from a device reports through status(), not a return value.
    document.load(buffer)
    if document.status() != QPdfDocument.Status.Ready or document.pageCount() != len(shapes):
        document.close()
        raise WatermarkError()
    ink: dict[tuple[float, float, int], int] = {}
    try:
        for index, shape in enumerate(shapes):
            width, height, rotation = shape
            if rotation in (90, 270):
                width, height = height, width
            pixels = render_pixels(document, index, (width, height), dpi=VERIFY_DPI).pixels
            ink[shape] = len(pixels) - pixels.count(255)
    finally:
        document.close()
    return ink


def verify_watermark(
    source_fd_path: Path,
    source_annotations: tuple[int, ...],
    candidate: Path,
    spec: WatermarkSpec,
    progress: Callable[[int, int], None] = lambda *_: None,
) -> WatermarkReport:
    """SEC13 gate on the written file, independent of the construction.

    `source_annotations` is the number of annotations of every source page.
    """
    with pikepdf.open(candidate, attempt_recovery=False, suppress_warnings=True) as pdf:
        if pdf.is_encrypted or pdf.check_pdf_syntax():
            raise WatermarkError()
        if len(pdf.pages) != len(source_annotations):
            raise WatermarkError()
        for page, count in zip(pdf.pages, source_annotations, strict=True):
            if len(page.obj.get("/Annots", [])) != count:
                raise WatermarkError()
        geometry = tuple(
            (box[2] - box[0], box[3] - box[1]) for box in (page_box(page) for page in pdf.pages)
        )
        rotations = tuple(_rotation(page) for page in pdf.pages)
    wanted = _squeezed(validate_watermark_text(spec.text))
    changed = 0
    source = open_renderer(source_fd_path)
    # What the watermark alone paints on each page shape: the output must
    # change at least half of it, wherever the source content is (review of B6).
    shapes = tuple(dict.fromkeys((w, h, r) for (w, h), r in zip(geometry, rotations, strict=True)))
    expected_ink = _reference_ink(spec, shapes)
    try:
        output = open_renderer(candidate)
        try:
            if output.pageCount() != len(geometry) or source.pageCount() != len(geometry):
                raise WatermarkError()
            for index, (width, height) in enumerate(geometry):
                if rotations[index] in (90, 270):
                    width, height = height, width
                size = output.pagePointSize(index)
                if not (
                    math.isclose(size.width(), width, abs_tol=0.02)
                    and math.isclose(size.height(), height, abs_tol=0.02)
                ):
                    raise WatermarkError()
                if wanted not in _squeezed(output.getAllText(index).text()):
                    raise WatermarkError()
                before = render_pixels(source, index, (width, height), dpi=VERIFY_DPI)
                after = render_pixels(output, index, (width, height), dpi=VERIFY_DPI)
                if before.width != after.width or before.height != after.height:
                    raise WatermarkError()
                # Every channel counts; the reference is measured the same way.
                differing = sum(a != b for a, b in zip(before.pixels, after.pixels, strict=True))
                ink = expected_ink[(geometry[index][0], geometry[index][1], rotations[index])]
                if ink == 0 or differing < ink / 2:
                    raise WatermarkError()
                changed += differing
                progress(index + 1, len(geometry))
        finally:
            output.close()
    finally:
        source.close()
    return WatermarkReport(pages=len(geometry), changed_pixels=changed)
