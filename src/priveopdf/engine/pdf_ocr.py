"""Bounded OCR operation inside the existing isolated PDF worker."""

from __future__ import annotations

import hashlib
import math
import os
import stat
import time
from collections.abc import Callable
from pathlib import Path

import pikepdf
from PySide6.QtCore import QSize
from PySide6.QtGui import QImage, QTransform
from PySide6.QtPdf import QPdfDocument, QPdfDocumentRenderOptions

from priveopdf.domain.errors import (
    EncryptedPdfError,
    InputPathError,
    InvalidPageSelectionError,
    InvalidPdfError,
    OutputWriteError,
    PdfModError,
)
from priveopdf.domain.jobs import (
    OCR_MAX_DOCUMENT_PAGES,
    OCR_MAX_SCANNED_PAGES,
    OCR_MAX_SCANNED_PIXELS,
    JobRequest,
    JobResult,
    OcrOptions,
)
from priveopdf.engine.ocr_native import SYSTEM_TESSDATA, OcrModelMissing, detect_turn, text_layer
from priveopdf.engine.pdf_compression import (
    CompressionIntegrityError,
    SignedPdfError,
    _geometry,
    _reject_signatures,
    has_digital_signature,
    reject_decompression_bombs,
    strip_signatures,
)
from priveopdf.engine.pdf_photocopy import (
    DPI,
    PhotocopyError,
    PhotocopyLimitError,
    PhotocopyRendererUnavailable,
    PhotocopyUnsupportedError,
    open_renderer,
    render_pixels,
    source_geometry,
)
from priveopdf.utils.validation import prepare_pdf_output_path, validate_pdf_inputs


class OcrIntegrityError(PdfModError):
    user_message = "La copie OCR n'a pas pu etre verifiee. Aucun fichier cree."
    technical_code = "ocr_integrity"


class OcrUnsupportedError(PdfModError):
    user_message = "Cette geometrie ou ce formulaire PDF n'est pas encore pris en charge par l'OCR."
    technical_code = "ocr_unsupported"


class OcrLimitError(PdfModError):
    user_message = "Ce PDF depasse les limites de l'OCR local."
    technical_code = "ocr_limit"


class OcrRendererUnavailable(PdfModError):
    user_message = "Le rendu OCR est incompatible avec le budget memoire du worker."
    technical_code = "ocr_renderer_unavailable"


class OcrAlreadySearchable(PdfModError):
    user_message = "Toutes les pages contiennent deja du texte. Aucun fichier cree."
    technical_code = "ocr_already_searchable"


class OcrNoEligiblePages(PdfModError):
    user_message = "Aucun texte n'a ete reconnu sur les pages scannees."
    technical_code = "ocr_no_eligible_pages"


class OcrSignedError(PdfModError):
    user_message = "Ce PDF porte une signature. L'OCR est refuse."
    technical_code = "ocr_signed"


def _identity(info: os.stat_result) -> tuple[int, int, int, int, int]:
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


# One point per pixel, at most four megapixels: a page with a small /UserUnit
# can declare 14400 x 14400 points without being large on paper.
_DIGEST_MAX_PIXELS = 4_000_000


def _small_render_digest(document: QPdfDocument, index: int) -> bytes:
    """Independent, bounded visual check for every page, including untouched pages."""
    size = document.pagePointSize(index)
    if not 0 < size.width() <= 14400 or not 0 < size.height() <= 14400:
        raise OcrUnsupportedError()
    scale = min(1.0, math.sqrt(_DIGEST_MAX_PIXELS / (size.width() * size.height())))
    options = QPdfDocumentRenderOptions()
    options.setRenderFlags(QPdfDocumentRenderOptions.RenderFlag.Annotations)
    image = document.render(
        index,
        QSize(math.ceil(size.width() * scale), math.ceil(size.height() * scale)),
        options,
    ).convertToFormat(QImage.Format.Format_RGBA8888)
    if image.isNull():
        raise OcrIntegrityError()
    return hashlib.sha256(bytes(image.constBits())).digest()


def _check_scanned_geometry(page: pikepdf.Page, dimensions: tuple[float, float]) -> None:
    """Refuse what would misplace the text layer; a quarter-turn /Rotate is supported.

    pikepdf places the overlay in the page's displayed orientation, the same one
    QtPdf renders for Tesseract (checked by test_ocr_layer_follows_page_rotation).
    qpdf ignores a real-number /Rotate that PDFium applies, and an extra `Q` in
    the page content would pop the graphics state that isolates the overlay.
    """
    box = tuple(map(float, page.mediabox))
    crop = tuple(map(float, page.cropbox))
    declared = page.obj.get("/Rotate", 0)
    if not isinstance(declared, int) or isinstance(declared, bool):
        raise OcrUnsupportedError()
    rotation = declared % 360
    if len(box) != 4 or rotation not in {0, 90, 180, 270} or not _balanced_states(page):
        raise OcrUnsupportedError()
    shown = (box[2], box[3]) if rotation in {0, 180} else (box[3], box[2])
    if (
        box[:2] != (0.0, 0.0)
        or crop != box
        or float(page.obj.get("/UserUnit", 1)) != 1
        or page.obj.get("/Annots")
        or not math.isclose(shown[0], dimensions[0], abs_tol=0.02)
        or not math.isclose(shown[1], dimensions[1], abs_tol=0.02)
    ):
        raise OcrUnsupportedError()


def _balanced_states(page: pikepdf.Page) -> bool:
    depth = 0
    for _operands, operator in pikepdf.parse_content_stream(page, "q Q"):
        depth += 1 if str(operator) == "q" else -1
        if depth < 0:
            return False
    return True


def _scanned_pixels(dimensions: tuple[float, float]) -> int:
    return math.ceil(dimensions[0] * DPI / 72) * math.ceil(dimensions[1] * DPI / 72)


# Above this orientation confidence the detected turn is trusted alone: the
# default of OCRmyPDF's --rotate-pages-threshold. Below it, both readings run
# and the one with the higher mean word confidence wins.
TRUSTED_TURN_CONFIDENCE = 14.0


def _turned(pixels: bytes, size: tuple[int, int], turn: int) -> tuple[bytes, tuple[int, int]]:
    """The RGB page turned counter-clockwise by a quarter-turn multiple."""
    if turn == 0:
        return pixels, size
    width, height = size
    image = QImage(pixels, width, height, width * 3, QImage.Format.Format_RGB888)
    # In image coordinates (y down) a negative angle turns counter-clockwise.
    image = image.transformed(QTransform().rotate(-turn))
    if image.isNull():
        raise OcrIntegrityError()
    width, height = image.width(), image.height()
    data, stride = image.constBits(), image.bytesPerLine()
    rows = (bytes(data[y * stride : y * stride + width * 3]) for y in range(height))
    return b"".join(rows), (width, height)


def _recognize(
    pixels: bytes, size: tuple[int, int], base: Path, languages: tuple[str, ...]
) -> tuple[Path, bool, int]:
    """Text layer read in the upright orientation, and the counter-clockwise turn used.

    A sideways or upside-down scan read as displayed gives garbage text, so the
    page is read in the orientation Tesseract detects; the page itself is not
    turned.
    """
    turn, certainty = detect_turn(pixels, size)
    attempts = (turn,) if turn == 0 or certainty >= TRUSTED_TURN_CONFIDENCE else (turn, 0)
    best: tuple[bool, int, int, Path] | None = None
    try:
        for attempt in attempts:
            turned, turned_size = _turned(pixels, size, attempt)
            layer, found, confidence = text_layer(
                turned, turned_size, base.with_name(f"{base.name}-{attempt}"), languages=languages
            )
            if best is None or (found, confidence) > best[:2]:
                if best is not None:
                    best[3].unlink(missing_ok=True)
                best = (found, confidence, attempt, layer)
            else:
                layer.unlink(missing_ok=True)
    except BaseException:
        if best is not None:
            best[3].unlink(missing_ok=True)
        raise
    if best is None:
        raise OcrIntegrityError()
    found, _confidence, turn, layer = best
    return layer, found, turn


def _place_layer(page: pikepdf.Page, layer: pikepdf.Page, turn: int) -> None:
    """Lay the text over the glyphs without changing how the page is displayed.

    pikepdf draws an overlay upright on the page as displayed. For a text read
    after a counter-clockwise turn, the page is shown turned the same way while
    the overlay is placed, then its own /Rotate is restored.
    """
    original = page.obj.get("/Rotate")
    if turn:
        page.Rotate = (int(original or 0) - turn) % 360
    try:
        # The MediaBox, not the TrimBox pikepdf would choose by default.
        page.add_overlay(layer, rect=pikepdf.Rectangle(*map(float, page.mediabox)))
    finally:
        if original is None:
            if "/Rotate" in page.obj:
                del page.obj["/Rotate"]
        else:
            page.obj["/Rotate"] = original


def run_ocr_job(
    job: JobRequest, started: float, progress: Callable[[int, int], None] = lambda *_: None
) -> JobResult:
    """Create and verify a private candidate; ProcessSupervisor publishes it.

    Every page without extractable text is recognized; pages that already carry
    text (native or mixed) are left exactly as they were. With ``page_numbers``
    (OCR10), only the chosen pages are considered; the others stay intact and
    the page limits apply to the chosen scanned pages alone.
    """
    options = job.require_options(OcrOptions)
    source_path = job.input_files[0]
    validate_pdf_inputs((source_path,), minimum_count=1)
    candidate = prepare_pdf_output_path(
        options.output_path, job.input_files, allowed_dir=job.output_dir
    )
    if any(not (SYSTEM_TESSDATA / f"{code}.traineddata").is_file() for code in options.languages):
        raise OcrModelMissing()
    try:
        fd = os.open(source_path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError:
        raise InputPathError() from None
    original_renderer = None
    output_created = False
    completed = False
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):
            raise InputPathError()
        with os.fdopen(fd, "rb", closefd=False) as stream:
            try:
                source = pikepdf.open(stream, attempt_recovery=False, suppress_warnings=True)
            except pikepdf.PasswordError:
                raise EncryptedPdfError() from None
            except pikepdf.PdfError:
                raise InvalidPdfError() from None
            with source:
                reject_decompression_bombs(source)
                if source.check_pdf_syntax():
                    raise InvalidPdfError()
                unsigned_copy = False
                try:
                    _reject_signatures(source)
                except SignedPdfError:
                    # The copy may drop the signatures OCR would invalidate, on
                    # the user's explicit choice (E4).
                    if not options.allow_unsigned_copy:
                        raise OcrSignedError() from None
                    unsigned_copy = True
                except CompressionIntegrityError:
                    raise OcrIntegrityError() from None
                original_renderer = open_renderer(Path(f"/proc/self/fd/{fd}"))
                geometry = source_geometry(source, original_renderer, max_total_bytes=None)
                count = len(geometry)
                if count > OCR_MAX_DOCUMENT_PAGES:
                    raise OcrLimitError()
                original_geometry = _geometry(source)
                original_text = tuple(
                    original_renderer.getAllText(index).text() for index in range(count)
                )
                chosen = _chosen_page_indexes(options.page_numbers, count)
                scanned = tuple(
                    index
                    for index in range(count)
                    if index in chosen and not original_text[index].strip()
                )
                if not scanned:
                    raise OcrAlreadySearchable()
                if (
                    len(scanned) > OCR_MAX_SCANNED_PAGES
                    or sum(_scanned_pixels(geometry[index]) for index in scanned)
                    > OCR_MAX_SCANNED_PIXELS
                ):
                    raise OcrLimitError()
                for index in scanned:
                    _check_scanned_geometry(source.pages[index], geometry[index])
                original_renders = tuple(
                    _small_render_digest(original_renderer, index) for index in range(count)
                )
                # One step per recognized page, then one per verified page.
                total_steps = len(scanned) + count
                recognized: set[int] = set()
                for step, index in enumerate(scanned, start=1):
                    rendered = render_pixels(original_renderer, index, geometry[index])
                    layer, found, turn = _recognize(
                        rendered.pixels,
                        (rendered.width, rendered.height),
                        job.output_dir / f"ocr-layer-{index + 1}",
                        options.languages,
                    )
                    del rendered
                    try:
                        if found:
                            with pikepdf.open(
                                layer, attempt_recovery=False, suppress_warnings=True
                            ) as overlay:
                                if len(overlay.pages) != 1 or overlay.check_pdf_syntax():
                                    raise OcrIntegrityError()
                                _place_layer(source.pages[index], overlay.pages[0], turn)
                            recognized.add(index)
                    finally:
                        layer.unlink(missing_ok=True)
                    progress(step, total_steps)
                if not recognized:
                    raise OcrNoEligiblePages()
                if unsigned_copy:
                    strip_signatures(source)
                output_fd = os.open(candidate, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                output_created = True
                with os.fdopen(output_fd, "wb") as output:
                    source.save(output, fix_metadata_version=False)
                original_renderer.close()
                original_renderer = None
                _verify_candidate(
                    candidate,
                    original_geometry,
                    original_text,
                    original_renders,
                    recognized,
                    lambda done: progress(len(scanned) + done, total_steps),
                )
                if unsigned_copy:
                    with pikepdf.open(
                        candidate, attempt_recovery=False, suppress_warnings=True
                    ) as result:
                        if has_digital_signature(result):
                            raise OcrIntegrityError()
        if _identity(before) != _identity(os.fstat(fd)) or _identity(before) != _identity(
            source_path.stat(follow_symlinks=False)
        ):
            raise OcrIntegrityError()
        states = (
            f"ocr_pages_recognized_{len(recognized)}",
            f"ocr_pages_text_present_{count - len(scanned)}",
            f"ocr_pages_no_text_{len(scanned) - len(recognized)}",
        )
        result = JobResult(
            True,
            (candidate,),
            states,
            "Copie OCR verifiee.",
            duration_ms=int((time.monotonic() - started) * 1000),
        )
        completed = True
        return result
    except PhotocopyRendererUnavailable:
        raise OcrRendererUnavailable() from None
    except PhotocopyLimitError:
        raise OcrLimitError() from None
    except PhotocopyUnsupportedError:
        raise OcrUnsupportedError() from None
    except PhotocopyError:
        raise OcrIntegrityError() from None
    except OSError:
        raise OutputWriteError() from None
    except (pikepdf.PdfError, ValueError, TypeError, AttributeError):
        raise OcrIntegrityError() from None
    finally:
        if output_created and not completed:
            candidate.unlink(missing_ok=True)
        if original_renderer is not None:
            original_renderer.close()
        os.close(fd)


def _chosen_page_indexes(page_numbers: tuple[int, ...], count: int) -> frozenset[int]:
    """0-based indexes of the pages to consider: all of them without a choice (OCR10)."""

    if not page_numbers:
        return frozenset(range(count))
    if any(number > count for number in page_numbers):
        raise InvalidPageSelectionError()
    return frozenset(number - 1 for number in page_numbers)


def _verify_candidate(
    candidate: Path,
    geometry: tuple[tuple[object, ...], ...],
    native_text: tuple[str, ...],
    renders: tuple[bytes, ...],
    recognized: set[int],
    progress: Callable[[int], None],
) -> None:
    verifier = open_renderer(candidate)
    try:
        with pikepdf.open(candidate, attempt_recovery=False, suppress_warnings=True) as result:
            if (
                result.is_encrypted
                or result.check_pdf_syntax()
                or _geometry(result) != geometry
                or len(result.pages) != len(native_text)
                or verifier.pageCount() != len(native_text)
            ):
                raise OcrIntegrityError()
            for index, old_text in enumerate(native_text):
                new_text = verifier.getAllText(index).text()
                if (
                    (index in recognized and (not new_text.strip() or new_text == old_text))
                    or (index not in recognized and new_text != old_text)
                    or _small_render_digest(verifier, index) != renders[index]
                ):
                    raise OcrIntegrityError()
                progress(index + 1)
    finally:
        verifier.close()
