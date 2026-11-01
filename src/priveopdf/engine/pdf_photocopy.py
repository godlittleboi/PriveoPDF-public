"""Pixels-only reconstruction and an independent strict candidate verifier."""

from __future__ import annotations

import hashlib
import math
import os
import zlib
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

import pikepdf
from PySide6.QtCore import QSize
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtPdf import QPdfDocument, QPdfDocumentRenderOptions

from priveopdf.domain.errors import PdfModError
from priveopdf.utils import keep_c_numeric_locale

DPI = 200
MAX_PAGE_PIXELS = 20_000_000
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_PAGES = 500
# Avoid Qt creating an implicit display connection in the isolated subprocess.
_QT_APP = None


class PhotocopyError(PdfModError):
    user_message = "La photocopie n'a pas pu etre verifiee. Aucun fichier cree."
    technical_code = "photocopy_integrity"


class PhotocopyRendererUnavailable(PhotocopyError):
    user_message = (
        "Le moteur Qt est incompatible avec la limite memoire du worker. Photocopie indisponible."
    )
    technical_code = "photocopy_renderer_unavailable"


class PhotocopyLimitError(PhotocopyError):
    user_message = "Ce PDF depasse les limites de taille de la photocopie."
    technical_code = "photocopy_limit"


class PhotocopyUnsupportedError(PhotocopyError):
    user_message = "Un formulaire ou contenu interactif ne peut pas etre rendu fidelement."
    technical_code = "photocopy_unsupported"


@dataclass(frozen=True)
class PixelPage:
    width_points: float
    height_points: float
    width: int
    height: int
    pixels: bytes


@dataclass(frozen=True)
class ExpectedPage:
    width_points: float
    height_points: float
    width: int
    height: int
    digest: bytes


def open_renderer(path: Path) -> QPdfDocument:
    global _QT_APP
    if QGuiApplication.instance() is None:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        _QT_APP = QGuiApplication([])
        keep_c_numeric_locale()
    import resource

    address_limit = resource.getrlimit(resource.RLIMIT_AS)[0]
    if address_limit != resource.RLIM_INFINITY and address_limit < 36 * 1024**3:
        # Qt 6.11.2 PDFium reserves 32 GiB even for an empty document. Keep the
        # existing hard worker limit; fail explicitly instead of native SIGTRAP.
        raise PhotocopyRendererUnavailable()
    document = QPdfDocument()
    if document.load(str(path)) != QPdfDocument.Error.None_ or document.pageCount() < 1:
        document.close()
        raise PhotocopyError()
    return document


def render_pixels(
    document: QPdfDocument, index: int, geometry: tuple[float, float], dpi: int = DPI
) -> PixelPage:
    width_pt, height_pt = geometry
    if not all(math.isfinite(v) and 0 < v <= 14400 for v in geometry):
        raise PhotocopyLimitError()
    width, height = (math.ceil(v * dpi / 72) for v in geometry)
    if width * height > MAX_PAGE_PIXELS:
        raise PhotocopyLimitError()
    options = QPdfDocumentRenderOptions()
    options.setRenderFlags(QPdfDocumentRenderOptions.RenderFlag.Annotations)
    image = document.render(index, QSize(width, height), options)
    if image.isNull() or image.size() != QSize(width, height):
        raise PhotocopyError()
    # Initialize every channel, composite alpha on white, and strip row padding.
    opaque = QImage(width, height, QImage.Format.Format_RGB888)
    if opaque.isNull():
        raise PhotocopyLimitError()
    opaque.fill(0xFFFFFFFF)
    painter = QPainter(opaque)
    painter.drawImage(0, 0, image)
    painter.end()
    data = opaque.constBits()
    stride = opaque.bytesPerLine()
    pixels = b"".join(bytes(data[y * stride : y * stride + width * 3]) for y in range(height))
    return PixelPage(width_pt, height_pt, width, height, pixels)


def source_geometry(
    pdf: pikepdf.Pdf,
    renderer: QPdfDocument,
    *,
    max_total_bytes: int | None = MAX_TOTAL_BYTES,
) -> tuple[tuple[float, float], ...]:
    """Physical geometry of every page; `max_total_bytes=None` leaves the budget to the caller.

    OCR renders only its scanned pages, one at a time, and bounds them itself.
    """
    if not 1 <= len(pdf.pages) <= MAX_PAGES or renderer.pageCount() != len(pdf.pages):
        raise PhotocopyLimitError()
    acro = pdf.Root.get("/AcroForm")
    if isinstance(acro, pikepdf.Dictionary) and (
        "/XFA" in acro or acro.get("/NeedAppearances", False)
    ):
        raise PhotocopyUnsupportedError()
    result = []
    total = 0
    for index, page in enumerate(pdf.pages):
        # PDFium renders the intersection of CropBox and MediaBox. No masked outer pixels.
        media, crop = tuple(map(float, page.mediabox)), tuple(map(float, page.cropbox))
        unit = float(page.obj.get("/UserUnit", 1))
        rotation = int(page.obj.get("/Rotate", 0)) % 360
        if rotation not in {0, 90, 180, 270} or not math.isfinite(unit) or unit <= 0:
            raise PhotocopyUnsupportedError()
        width = (min(media[2], crop[2]) - max(media[0], crop[0])) * unit
        height = (min(media[3], crop[3]) - max(media[1], crop[1])) * unit
        if rotation in {90, 270}:
            width, height = height, width
        if not all(math.isfinite(v) and 0 < v <= 14400 for v in (width, height)):
            raise PhotocopyLimitError()
        qt_size = renderer.pagePointSize(index)
        # Qt PDFium reports unscaled UserUnit geometry; retain physical size explicitly.
        if not (
            math.isclose(qt_size.width() * unit, width, abs_tol=0.02)
            and math.isclose(qt_size.height() * unit, height, abs_tol=0.02)
        ):
            raise PhotocopyUnsupportedError()
        pixels = math.ceil(width * DPI / 72) * math.ceil(height * DPI / 72)
        if pixels > MAX_PAGE_PIXELS:
            raise PhotocopyLimitError()
        total += pixels * 3
        if max_total_bytes is not None and total > max_total_bytes:
            raise PhotocopyLimitError()
        for annot in page.obj.get("/Annots", []):
            if not isinstance(annot, pikepdf.Dictionary):
                raise PhotocopyUnsupportedError()
            if annot.get("/Subtype") in (
                pikepdf.Name.RichMedia,
                pikepdf.Name.Screen,
                pikepdf.Name.Movie,
                pikepdf.Name("/3D"),
            ):
                raise PhotocopyUnsupportedError()
            if annot.get("/Subtype") == pikepdf.Name.Widget:
                appearance = annot.get("/AP")
                if not isinstance(appearance, pikepdf.Dictionary) or "/N" not in appearance:
                    raise PhotocopyUnsupportedError()
        result.append((width, height))
    return tuple(result)


def build_image_pdf(pages: Iterator[PixelPage], candidate: Path) -> tuple[ExpectedPage, ...]:
    """This boundary receives only normalized pixels and physical geometry, never source objects."""
    expected = []
    total = 0
    with pikepdf.Pdf.new() as output:
        for pixels in pages:
            if (
                len(expected) >= MAX_PAGES
                or pixels.width * pixels.height > MAX_PAGE_PIXELS
                or len(pixels.pixels) != pixels.width * pixels.height * 3
            ):
                raise PhotocopyLimitError()
            total += len(pixels.pixels)
            if total > MAX_TOTAL_BYTES:
                raise PhotocopyLimitError()
            page = output.add_blank_page(page_size=(pixels.width_points, pixels.height_points))
            image = pikepdf.Stream(output, zlib.compress(pixels.pixels))
            image.Type = pikepdf.Name.XObject
            image.Subtype = pikepdf.Name.Image
            image.Width, image.Height = pixels.width, pixels.height
            image.ColorSpace = pikepdf.Name.DeviceRGB
            image.BitsPerComponent = 8
            image.Filter = pikepdf.Name.FlateDecode
            page.Resources = pikepdf.Dictionary(XObject=pikepdf.Dictionary(Im0=image))
            page.Contents = pikepdf.Stream(
                output,
                (
                    f"q {pixels.width_points:.8f} 0 0 {pixels.height_points:.8f} 0 0 cm /Im0 Do Q\n"
                ).encode("ascii"),
            )
            expected.append(
                ExpectedPage(
                    pixels.width_points,
                    pixels.height_points,
                    pixels.width,
                    pixels.height,
                    hashlib.sha256(pixels.pixels).digest(),
                )
            )
        if not expected:
            raise PhotocopyError()
        # Deterministic technical ID derives from newly constructed output, never the source ID.
        fd = os.open(candidate, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        try:
            with os.fdopen(fd, "wb") as stream:
                output.save(
                    stream,
                    fix_metadata_version=False,
                    deterministic_id=True,
                    object_stream_mode=pikepdf.ObjectStreamMode.disable,
                )
        except BaseException:
            candidate.unlink(missing_ok=True)
            raise
    return tuple(expected)


def verify_image_pdf(
    candidate: Path,
    expected: tuple[ExpectedPage, ...],
    *,
    progress: Callable[[int, int], None] = lambda *_: None,
) -> None:
    """Allowlist every object; validate pixels and independently render every output page."""
    renderer = open_renderer(candidate)
    try:
        with pikepdf.open(candidate, attempt_recovery=False, suppress_warnings=True) as pdf:
            if (
                pdf.is_encrypted
                or pdf.check_pdf_syntax()
                or set(pdf.Root.keys()) != {"/Type", "/Pages"}
                or not set(pdf.trailer.keys()) <= {"/Root", "/Size", "/ID"}
            ):
                raise PhotocopyError()
            if len(pdf.pages) != len(expected) or renderer.pageCount() != len(expected):
                raise PhotocopyError()
            tree = pdf.Root.Pages
            if (
                set(tree.keys()) != {"/Type", "/Kids", "/Count"}
                or tree.Type != pikepdf.Name.Pages
                or int(tree.Count) != len(expected)
                or len(tree.Kids) != len(expected)
            ):
                raise PhotocopyError()
            allowed_objects = {pdf.Root.objgen, tree.objgen}
            for index, (page, want) in enumerate(zip(pdf.pages, expected, strict=True)):
                if (
                    set(page.obj.keys())
                    != {"/Type", "/Parent", "/MediaBox", "/Resources", "/Contents"}
                    or page.obj.Type != pikepdf.Name.Page
                    or page.obj.Parent.objgen != tree.objgen
                    or tree.Kids[index].objgen != page.obj.objgen
                ):
                    raise PhotocopyError()
                box = tuple(map(float, page.mediabox))
                if len(box) != 4 or any(
                    abs(a - b) > 0.00001
                    for a, b in zip(box, (0, 0, want.width_points, want.height_points), strict=True)
                ):
                    raise PhotocopyError()
                resources = page.Resources
                if (
                    set(resources.keys()) != {"/XObject"}
                    or set(resources.XObject.keys()) != {"/Im0"}
                    or resources.is_indirect
                    or resources.XObject.is_indirect
                ):
                    raise PhotocopyError()
                image = resources.XObject.Im0
                if (
                    not isinstance(image, pikepdf.Stream)
                    or set(image.keys())
                    != {
                        "/Type",
                        "/Subtype",
                        "/Width",
                        "/Height",
                        "/ColorSpace",
                        "/BitsPerComponent",
                        "/Filter",
                        "/Length",
                    }
                    or image.Type != pikepdf.Name.XObject
                    or image.Subtype != pikepdf.Name.Image
                    or image.ColorSpace != pikepdf.Name.DeviceRGB
                    or image.BitsPerComponent != 8
                    or image.Filter != pikepdf.Name.FlateDecode
                    or image.Width != want.width
                    or image.Height != want.height
                ):
                    raise PhotocopyError()
                raw = image.read_raw_bytes()
                decoder = zlib.decompressobj()
                decoded = decoder.decompress(raw, want.width * want.height * 3 + 1)
                if (
                    len(decoded) != want.width * want.height * 3
                    or not decoder.eof
                    or decoder.unused_data
                    or hashlib.sha256(decoded).digest() != want.digest
                ):
                    raise PhotocopyError()
                del decoded, raw
                contents = page.Contents
                if (
                    not isinstance(contents, pikepdf.Stream)
                    or not set(contents.keys()) <= {"/Length", "/Filter"}
                    or int(contents.Length) > 1024
                ):
                    raise PhotocopyError()
                ops = list(pikepdf.parse_content_stream(page))
                if (
                    [str(op.operator) for op in ops] != ["q", "cm", "Do", "Q"]
                    or ops[0].operands
                    or ops[3].operands
                    or list(ops[2].operands) != [pikepdf.Name.Im0]
                ):
                    raise PhotocopyError()
                matrix = list(map(float, ops[1].operands))
                if len(matrix) != 6 or any(
                    abs(a - b) > 0.00001
                    for a, b in zip(
                        matrix, (want.width_points, 0, 0, want.height_points, 0, 0), strict=True
                    )
                ):
                    raise PhotocopyError()
                allowed_objects.update((page.obj.objgen, contents.objgen, image.objgen))
                rendered = render_pixels(renderer, index, (want.width_points, want.height_points))
                # Same dimensions and integer alignment: exact lossless comparison.
                if (
                    hashlib.sha256(rendered.pixels).digest() != want.digest
                    or renderer.getAllText(index).text()
                ):
                    raise PhotocopyError()
                progress(index + 1, len(expected))
            if {obj.objgen for obj in pdf.objects} != allowed_objects:
                raise PhotocopyError()
    except (pikepdf.PdfError, ValueError, TypeError, AttributeError, zlib.error):
        raise PhotocopyError() from None
    finally:
        renderer.close()
