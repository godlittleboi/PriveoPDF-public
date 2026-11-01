"""Offline text-only PDF layers through libtesseract's C API (no CLI child)."""

from __future__ import annotations

import ctypes
from pathlib import Path
from types import SimpleNamespace

from priveopdf.domain.errors import PdfModError
from priveopdf.domain.jobs import OCR_TESSDATA
from priveopdf.domain.ocr_languages import is_ocr_language_code

SYSTEM_TESSDATA = OCR_TESSDATA
# Orientation model shipped by tesseract-ocr-osd, a dependency of tesseract-ocr.
OSD_MODEL = "osd"
_DPI = 200
_PSM_OSD_ONLY = 0
# Simple cleanup of the image Tesseract reads, never of the page: Sauvola's
# local thresholding (Tesseract 5) copes with shadows and uneven lighting.
_SAUVOLA = b"2"


class OcrNativeError(PdfModError):
    user_message = "La reconnaissance locale a echoue. Aucun fichier cree."
    technical_code = "ocr_native_error"


class OcrModelMissing(OcrNativeError):
    user_message = "Le modele OCR demande n'est pas installe localement."
    technical_code = "ocr_model_missing"


class OcrLibraryMissing(OcrNativeError):
    user_message = "Le moteur OCR local libtesseract 5 est absent."
    technical_code = "ocr_library_missing"


def _check_image(pixels: bytes, size: tuple[int, int]) -> None:
    width, height = size
    if width < 1 or height < 1 or width * height > 20_000_000 or len(pixels) != width * height * 3:
        raise OcrNativeError()


def _tesseract() -> SimpleNamespace:
    try:
        # find_library can spawn ldconfig, forbidden by the worker seccomp profile.
        lib = ctypes.CDLL("libtesseract.so.5")
    except OSError:
        raise OcrLibraryMissing() from None

    def bind(name: str, result: object, *arguments: object):
        method = getattr(lib, name)
        method.restype = result
        method.argtypes = list(arguments)
        return method

    pointer, integer, text = ctypes.c_void_p, ctypes.c_int, ctypes.c_char_p
    return SimpleNamespace(
        create=bind("TessBaseAPICreate", pointer),
        init=bind("TessBaseAPIInit3", integer, pointer, text, text),
        set_psm=bind("TessBaseAPISetPageSegMode", None, pointer, integer),
        set_variable=bind("TessBaseAPISetVariable", integer, pointer, text, text),
        set_image=bind(
            "TessBaseAPISetImage", None, pointer, pointer, integer, integer, integer, integer
        ),
        set_dpi=bind("TessBaseAPISetSourceResolution", None, pointer, integer),
        detect=bind(
            "TessBaseAPIDetectOrientationScript",
            integer,
            pointer,
            ctypes.POINTER(integer),
            ctypes.POINTER(ctypes.c_float),
            ctypes.POINTER(text),
            ctypes.POINTER(ctypes.c_float),
        ),
        recognize=bind("TessBaseAPIRecognize", integer, pointer, pointer),
        mean_confidence=bind("TessBaseAPIMeanTextConf", integer, pointer),
        get_text=bind("TessBaseAPIGetUTF8Text", pointer, pointer),
        delete_text=bind("TessDeleteText", None, pointer),
        renderer_create=bind("TessPDFRendererCreate", pointer, text, text, integer),
        begin=bind("TessResultRendererBeginDocument", integer, pointer, text),
        add=bind("TessResultRendererAddImage", integer, pointer, pointer),
        end=bind("TessResultRendererEndDocument", integer, pointer),
        delete_renderer=bind("TessDeleteResultRenderer", None, pointer),
        api_end=bind("TessBaseAPIEnd", None, pointer),
        delete_api=bind("TessBaseAPIDelete", None, pointer),
    )


def detect_turn(
    pixels: bytes, size: tuple[int, int], *, tessdata: Path = SYSTEM_TESSDATA
) -> tuple[int, float]:
    """Counter-clockwise quarter turn that puts the text upright, with Tesseract's confidence.

    (0, 0.0) when the orientation model is absent or the page has too little
    text to decide: the page is then recognized as displayed.
    """
    _check_image(pixels, size)
    if not (tessdata / f"{OSD_MODEL}.traineddata").is_file():
        return 0, 0.0
    tess = _tesseract()
    api = tess.create()
    if not api:
        raise OcrNativeError()
    try:
        if tess.init(api, str(tessdata).encode(), OSD_MODEL.encode("ascii")) != 0:
            return 0, 0.0
        tess.set_psm(api, _PSM_OSD_ONLY)
        buffer = ctypes.create_string_buffer(pixels)
        width, height = size
        tess.set_image(api, ctypes.cast(buffer, ctypes.c_void_p), width, height, 3, width * 3)
        tess.set_dpi(api, _DPI)
        degrees, confidence = ctypes.c_int(), ctypes.c_float()
        script, script_confidence = ctypes.c_char_p(), ctypes.c_float()
        found = tess.detect(
            api,
            ctypes.byref(degrees),
            ctypes.byref(confidence),
            ctypes.byref(script),
            ctypes.byref(script_confidence),
        )
        if not found or degrees.value not in {0, 90, 180, 270}:
            return 0, 0.0
        return degrees.value, float(confidence.value)
    finally:
        tess.api_end(api)
        tess.delete_api(api)


def text_layer(
    pixels: bytes,
    size: tuple[int, int],
    base: Path,
    *,
    languages: tuple[str, ...] = ("eng",),
    tessdata: Path = SYSTEM_TESSDATA,
) -> tuple[Path, bool, int]:
    """Return an invisible PDF text layer, whether words were found and their mean confidence.

    Call only on a bounded RGB page in a private worker directory. The public
    operation supplies the fixed system model path. No extracted text is logged
    or returned.
    """
    if (
        not languages
        or len(languages) > 3
        or len(set(languages)) != len(languages)
        or any(not is_ocr_language_code(code) for code in languages)
    ):
        raise OcrNativeError()
    if any(not (tessdata / f"{code}.traineddata").is_file() for code in languages):
        raise OcrModelMissing()
    _check_image(pixels, size)
    layer_path = base.with_suffix(".pdf")
    if layer_path.exists() or layer_path.is_symlink():
        raise OcrNativeError()
    tess = _tesseract()
    api = tess.create()
    if not api:
        raise OcrNativeError()
    complete = False
    try:
        if tess.init(api, str(tessdata).encode(), "+".join(languages).encode("ascii")) != 0:
            raise OcrModelMissing()
        tess.set_variable(api, b"thresholding_method", _SAUVOLA)
        buffer = ctypes.create_string_buffer(pixels)
        width, height = size
        tess.set_image(api, ctypes.cast(buffer, ctypes.c_void_p), width, height, 3, width * 3)
        tess.set_dpi(api, _DPI)
        if tess.recognize(api, None) != 0:
            raise OcrNativeError()
        raw_text = tess.get_text(api)
        if not raw_text:
            raise OcrNativeError()
        try:
            recognized = bool(ctypes.string_at(raw_text).strip())
        finally:
            tess.delete_text(raw_text)
        confidence = max(0, int(tess.mean_confidence(api)))
        renderer = tess.renderer_create(str(base).encode(), str(tessdata).encode(), 1)
        if not renderer:
            raise OcrNativeError()
        try:
            if not tess.begin(renderer, b"PriveoPDF OCR"):
                raise OcrNativeError()
            added = bool(tess.add(renderer, api))
            finished = bool(tess.end(renderer))
            if not (added and finished):
                raise OcrNativeError()
        finally:
            tess.delete_renderer(renderer)
        complete = True
    finally:
        tess.api_end(api)
        tess.delete_api(api)
        if not complete:
            layer_path.unlink(missing_ok=True)
    return layer_path, recognized, confidence
