from __future__ import annotations

import hashlib
import math
import sys
import unicodedata
from collections import Counter
from collections.abc import Mapping, Sequence
from contextlib import ExitStack
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

import pikepdf


class OracleStatus(StrEnum):
    OK = "OK"
    MISMATCH = "MISMATCH"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True)
class PageReference:
    source_index: int
    page_index: int
    rotation_delta: int = 0


@dataclass(frozen=True)
class StructuralOracleResult:
    semantic_status: OracleStatus
    visual_status: OracleStatus
    semantic_pages_checked: int = 0
    visual_pages_checked: int = 0
    text_pages_checked: int = 0
    visual_pages_skipped: int = 0
    visual_max_normalized_mae: float = 0.0
    visual_max_changed_fraction: float = 0.0
    failure_code: str = ""
    detail: str = ""


@dataclass(frozen=True)
class _PageSnapshot:
    boxes: tuple[tuple[str, ...], ...]
    rotation: int
    user_unit: str
    content_sha256: str | None
    annotation_signature: tuple[tuple[str, ...], ...]


@dataclass(frozen=True)
class _VisualResult:
    status: OracleStatus
    pages_checked: int = 0
    text_pages_checked: int = 0
    pages_skipped: int = 0
    max_normalized_mae: float = 0.0
    max_changed_fraction: float = 0.0
    failure_code: str = ""
    detail: str = ""


class _QtPageUnavailableError(RuntimeError):
    """QtPdf loaded a document but could not rasterize one of its pages."""


_BOX_NAMES = ("mediabox", "cropbox", "trimbox", "bleedbox", "artbox")
_RENDER_LONG_EDGE = 256
_MAX_NORMALIZED_MAE = 0.003
_MAX_CHANGED_PIXEL_FRACTION = 0.02
_CHANGED_CHANNEL_TOLERANCE = 8
_QT_APP: Any = None


def validate_structural_outputs(
    *,
    tool_id: str,
    input_files: Sequence[Path],
    output_paths: Sequence[Path],
    options: Mapping[str, Any],
    render_visual: bool = True,
) -> StructuralOracleResult:
    """Compare outputs with independently mapped source pages without persisting content."""
    if tool_id == "blank_page":
        return _validate_blank_page_output(
            input_files,
            output_paths,
            options,
            render_visual=render_visual,
        )
    try:
        plans = _expected_plans(tool_id, input_files, options)
    except (TypeError, ValueError) as exc:
        return _semantic_failure("invalid_plan", type(exc).__name__)
    if len(plans) != len(output_paths):
        return _semantic_failure("output_count", "unexpected output count")

    checked = 0
    try:
        with ExitStack() as stack:
            sources = [stack.enter_context(pikepdf.open(Path(path))) for path in input_files]
            outputs = [stack.enter_context(pikepdf.open(Path(path))) for path in output_paths]
            for output_index, (output, plan) in enumerate(zip(outputs, plans, strict=True)):
                if len(output.pages) != len(plan):
                    return _semantic_failure(
                        "page_count",
                        f"output {output_index + 1} has an unexpected page count",
                        checked,
                    )
                for output_page_index, reference in enumerate(plan):
                    source_page = pikepdf.Page(
                        sources[reference.source_index].pages[reference.page_index]
                    )
                    output_page = pikepdf.Page(output.pages[output_page_index])
                    failure = _compare_page_snapshots(
                        _page_snapshot(source_page),
                        _page_snapshot(output_page),
                        rotation_delta=reference.rotation_delta,
                    )
                    if failure:
                        code, detail = failure
                        return _semantic_failure(
                            code,
                            f"output {output_index + 1}, page {output_page_index + 1}: {detail}",
                            checked,
                        )
                    checked += 1
                form_failure = _validate_form_reachability(sources, output, plan)
                if form_failure:
                    return _semantic_failure(
                        "form_reachability",
                        f"output {output_index + 1}: {form_failure}",
                        checked,
                    )
    except Exception as exc:
        return _semantic_failure("oracle_exception", type(exc).__name__, checked)

    if not render_visual:
        return StructuralOracleResult(
            semantic_status=OracleStatus.OK,
            visual_status=OracleStatus.NOT_APPLICABLE,
            semantic_pages_checked=checked,
        )

    visual = _validate_visual_outputs(input_files, output_paths, plans)
    return StructuralOracleResult(
        semantic_status=OracleStatus.OK,
        visual_status=visual.status,
        semantic_pages_checked=checked,
        visual_pages_checked=visual.pages_checked,
        text_pages_checked=visual.text_pages_checked,
        visual_pages_skipped=visual.pages_skipped,
        visual_max_normalized_mae=visual.max_normalized_mae,
        visual_max_changed_fraction=visual.max_changed_fraction,
        failure_code=visual.failure_code,
        detail=visual.detail,
    )


def _validate_blank_page_output(
    input_files: Sequence[Path],
    output_paths: Sequence[Path],
    options: Mapping[str, Any],
    *,
    render_visual: bool,
) -> StructuralOracleResult:
    if len(input_files) != 1 or len(output_paths) != 1:
        return _semantic_failure("output_count", "blank page requires one input and one output")
    position = options.get("insert_after_page")
    width = options.get("width_mm")
    height = options.get("height_mm")
    if not isinstance(position, int) or isinstance(position, bool):
        return _semantic_failure("invalid_plan", "invalid blank page position")
    if not isinstance(width, (int, float)) or not isinstance(height, (int, float)):
        return _semantic_failure("invalid_plan", "invalid blank page dimensions")
    checked = 0
    plan: tuple[PageReference, ...] = ()
    output_page_indices: tuple[int, ...] = ()
    try:
        with pikepdf.open(input_files[0]) as source, pikepdf.open(output_paths[0]) as output:
            if not 0 <= position <= len(source.pages) or len(output.pages) != len(source.pages) + 1:
                return _semantic_failure("page_count", "unexpected blank page position or count")
            blank = pikepdf.Page(output.pages[position])
            actual = (float(blank.MediaBox[2]), float(blank.MediaBox[3]))
            expected = (float(width) * 72 / 25.4, float(height) * 72 / 25.4)
            if any(abs(left - right) > 0.001 for left, right in zip(actual, expected, strict=True)):
                return _semantic_failure("page_box", "blank page dimensions differ")
            if blank.get("/Contents") or blank.get("/Annots"):
                return _semantic_failure("page_content", "generated page is not blank")
            plan = tuple(PageReference(0, page_index) for page_index in range(len(source.pages)))
            output_page_indices = tuple(
                page_index if page_index < position else page_index + 1
                for page_index in range(len(source.pages))
            )
            for output_page_index, reference in zip(output_page_indices, plan, strict=True):
                failure = _compare_page_snapshots(
                    _page_snapshot(pikepdf.Page(source.pages[reference.page_index])),
                    _page_snapshot(pikepdf.Page(output.pages[output_page_index])),
                    rotation_delta=0,
                )
                if failure:
                    code, detail = failure
                    return _semantic_failure(
                        code,
                        f"retained page {reference.page_index + 1}: {detail}",
                        checked,
                    )
                checked += 1
            form_failure = _validate_form_reachability((source,), output, plan)
            if form_failure:
                return _semantic_failure(
                    "form_reachability",
                    f"output 1: {form_failure}",
                    checked,
                )
    except Exception as exc:
        return _semantic_failure("oracle_exception", type(exc).__name__, checked)
    if not render_visual:
        return StructuralOracleResult(
            semantic_status=OracleStatus.OK,
            visual_status=OracleStatus.NOT_APPLICABLE,
            semantic_pages_checked=checked + 1,
        )
    visual = _validate_visual_outputs(
        input_files,
        output_paths,
        (plan,),
        output_page_indices=(output_page_indices,),
    )
    return StructuralOracleResult(
        semantic_status=OracleStatus.OK,
        visual_status=visual.status,
        semantic_pages_checked=checked + 1,
        visual_pages_checked=visual.pages_checked,
        text_pages_checked=visual.text_pages_checked,
        visual_pages_skipped=visual.pages_skipped,
        visual_max_normalized_mae=visual.max_normalized_mae,
        visual_max_changed_fraction=visual.max_changed_fraction,
        failure_code=visual.failure_code,
        detail=visual.detail,
    )


def _semantic_failure(
    code: str,
    detail: str,
    checked: int = 0,
) -> StructuralOracleResult:
    return StructuralOracleResult(
        semantic_status=OracleStatus.MISMATCH,
        visual_status=OracleStatus.NOT_APPLICABLE,
        semantic_pages_checked=checked,
        failure_code=code,
        detail=detail,
    )


def _expected_plans(
    tool_id: str,
    input_files: Sequence[Path],
    options: Mapping[str, Any],
) -> tuple[tuple[PageReference, ...], ...]:
    page_counts = tuple(_page_count(Path(path)) for path in input_files)
    if tool_id == "merge":
        return (
            tuple(
                PageReference(source_index, page_index)
                for source_index, count in enumerate(page_counts)
                for page_index in range(count)
            ),
        )
    if tool_id == "insert":
        if len(page_counts) != 2:
            raise ValueError("insert requires exactly two sources")
        inserted_pages = _one_based_pages(options.get("page_numbers"), page_counts[1])
        insert_after_page = options.get("insert_after_page")
        if (
            not isinstance(insert_after_page, int)
            or isinstance(insert_after_page, bool)
            or insert_after_page < 0
            or insert_after_page > page_counts[0]
        ):
            raise ValueError("insert_after_page is outside the primary document")
        return (
            (
                *(PageReference(0, page) for page in range(insert_after_page)),
                *(PageReference(1, page - 1) for page in inserted_pages),
                *(PageReference(0, page) for page in range(insert_after_page, page_counts[0])),
            ),
        )
    if len(page_counts) != 1:
        raise ValueError(f"{tool_id} requires exactly one source")
    page_count = page_counts[0]
    if tool_id == "extract":
        pages = _one_based_pages(options.get("page_numbers"), page_count)
        return (tuple(PageReference(0, page - 1) for page in pages),)
    if tool_id == "remove":
        removed = set(_one_based_pages(options.get("page_numbers"), page_count))
        return (
            tuple(
                PageReference(0, page - 1)
                for page in range(1, page_count + 1)
                if page not in removed
            ),
        )
    if tool_id == "reorder":
        order = _one_based_pages(options.get("page_order"), page_count)
        if len(order) != page_count or len(set(order)) != page_count:
            raise ValueError("page_order must be a complete permutation")
        return (tuple(PageReference(0, page - 1) for page in order),)
    if tool_id == "rotate":
        selected = set(_one_based_pages(options.get("page_numbers"), page_count))
        angle = options.get("angle")
        if not isinstance(angle, int) or isinstance(angle, bool) or angle not in {0, 90, 180, 270}:
            raise ValueError("angle must be 0, 90, 180 or 270")
        return (
            tuple(
                PageReference(0, page - 1, angle if page in selected else 0)
                for page in range(1, page_count + 1)
            ),
        )
    if tool_id == "split":
        raw_groups = options.get("page_groups")
        if not isinstance(raw_groups, (tuple, list)) or not raw_groups:
            raise ValueError("split page_groups are required")
        return tuple(
            tuple(PageReference(0, page - 1) for page in _one_based_pages(group, page_count))
            for group in raw_groups
        )
    raise ValueError(f"unsupported tool: {tool_id}")


def _page_count(path: Path) -> int:
    with pikepdf.open(path) as pdf:
        return len(pdf.pages)


def _one_based_pages(value: object, page_count: int) -> tuple[int, ...]:
    if not isinstance(value, (tuple, list, range)):
        raise TypeError("page selection must be a sequence")
    pages = tuple(value)
    if not pages or any(
        not isinstance(page, int) or isinstance(page, bool) or page < 1 or page > page_count
        for page in pages
    ):
        raise ValueError("page selection is outside the document")
    return pages


def _page_snapshot(page: pikepdf.Page) -> _PageSnapshot:
    return _PageSnapshot(
        boxes=tuple(_box_tuple(getattr(page, name)) for name in _BOX_NAMES),
        rotation=int(page.rotation) % 360,
        user_unit=_number_text(page.get("/UserUnit", 1)),
        content_sha256=_content_digest(page),
        annotation_signature=_annotation_signature(page),
    )


def _box_tuple(value: object) -> tuple[str, ...]:
    try:
        return tuple(_number_text(number) for number in value)  # type: ignore[union-attr]
    except (TypeError, ValueError):
        return ()


def _number_text(value: Any) -> str:
    number = float(value)
    if number == 0:
        number = 0.0
    return f"{number:.6f}".rstrip("0").rstrip(".")


def _content_digest(page: pikepdf.Page) -> str | None:
    digest = hashlib.sha256()
    contents = page.get("/Contents")
    if contents is None:
        return digest.hexdigest()
    streams = contents if isinstance(contents, pikepdf.Array) else (contents,)
    try:
        for stream in streams:
            payload = stream.read_bytes()
            digest.update(len(payload).to_bytes(8, "big"))
            digest.update(payload)
    except (AttributeError, pikepdf.PdfError):
        return None
    return digest.hexdigest()


def _annotation_signature(page: pikepdf.Page) -> tuple[tuple[str, ...], ...]:
    signatures = []
    for raw_annotation in page.get("/Annots", ()) or ():
        annotation = raw_annotation
        signatures.append(
            (
                str(annotation.get("/Subtype", "")),
                *_box_tuple(annotation.get("/Rect", ())),
                str(int(annotation.get("/F", 0))),
                _field_property_digest(annotation),
                _action_digest(annotation.get("/A")),
            )
        )
    return tuple(sorted(signatures))


def _field_property_digest(annotation: Any) -> str:
    values: list[str] = []
    current = annotation
    seen: set[tuple[int, int]] = set()
    for _ in range(32):
        objgen = _object_key(current)
        if objgen != (0, 0):
            if objgen in seen:
                break
            seen.add(objgen)
        for key in ("/FT", "/T", "/V", "/DV", "/Ff"):
            value = _stable_scalar(current.get(key)) if key in current else None
            if value is not None:
                values.append(f"{key}={value}")
        parent = current.get("/Parent")
        if parent is None:
            break
        current = parent
    return _privacy_digest(values)


def _stable_scalar(value: Any) -> str | None:
    if isinstance(value, (bool, int, float, str)):
        return str(value)
    type_code = getattr(value, "_type_code", None)
    type_name = getattr(type_code, "name", "")
    if type_name in {"boolean", "integer", "name_", "real", "string"}:
        return str(value)
    return None


def _object_key(value: Any) -> tuple[int, int]:
    raw = getattr(value, "objgen", (0, 0))
    if isinstance(raw, tuple) and len(raw) == 2:
        return int(raw[0]), int(raw[1])
    return 0, 0


def _action_digest(action: Any) -> str:
    if action is None:
        return ""
    # Internal destinations may embed page object references whose object numbers
    # legitimately change while copying. URI actions remain stable and comparable.
    values = [f"{key}={action.get(key)}" for key in ("/S", "/URI") if key in action]
    return _privacy_digest(values)


def _privacy_digest(values: Sequence[str]) -> str:
    if not values:
        return ""
    payload = "\x1f".join(values).encode("utf-8", errors="replace")
    return hashlib.sha256(payload).hexdigest()


def _compare_page_snapshots(
    source: _PageSnapshot,
    output: _PageSnapshot,
    *,
    rotation_delta: int,
) -> tuple[str, str] | None:
    if source.boxes != output.boxes:
        return "page_boxes", "page boxes differ from the mapped source page"
    if source.user_unit != output.user_unit:
        return "page_user_unit", "page scale differs from the mapped source page"
    expected_rotation = (source.rotation + rotation_delta) % 360
    if output.rotation != expected_rotation:
        return "page_rotation", f"expected rotation {expected_rotation}, got {output.rotation}"
    if (
        source.content_sha256 is not None
        and output.content_sha256 is not None
        and source.content_sha256 != output.content_sha256
    ):
        return "page_content", "decoded page content differs from the mapped source page"
    if source.annotation_signature != output.annotation_signature:
        return "page_annotations", "annotation or form properties differ"
    return None


def _validate_form_reachability(
    sources: Sequence[pikepdf.Pdf],
    output: pikepdf.Pdf,
    plan: Sequence[PageReference],
) -> str:
    expected_reachable_widgets = sum(
        1
        for reference in plan
        if _source_has_field_catalog(sources[reference.source_index])
        for annotation in (
            sources[reference.source_index].pages[reference.page_index].get("/Annots", ()) or ()
        )
        if str(annotation.get("/Subtype", "")) == "/Widget"
    )
    if expected_reachable_widgets == 0:
        return ""
    if "/AcroForm" not in output.Root:
        return "form widgets are not reachable from the document catalog"
    fields = output.Root.AcroForm.get("/Fields", ())
    if not fields:
        return "form widgets exist but the field catalog is empty"
    if _reachable_widget_count(fields) < expected_reachable_widgets:
        return "the field catalog does not reach every page widget"
    return ""


def _source_has_field_catalog(pdf: pikepdf.Pdf) -> bool:
    return "/AcroForm" in pdf.Root and bool(pdf.Root.AcroForm.get("/Fields", ()))


def _reachable_widget_count(fields: Any) -> int:
    count = 0
    pending = list(fields)
    seen: set[tuple[int, int]] = set()
    while pending:
        field = pending.pop()
        objgen = _object_key(field)
        if objgen != (0, 0):
            if objgen in seen:
                continue
            seen.add(objgen)
        kids = field.get("/Kids", ()) or ()
        pending.extend(kids)
        if str(field.get("/Subtype", "")) == "/Widget":
            count += 1
    return count


def _validate_visual_outputs(
    input_files: Sequence[Path],
    output_paths: Sequence[Path],
    plans: Sequence[Sequence[PageReference]],
    *,
    output_page_indices: Sequence[Sequence[int]] | None = None,
) -> _VisualResult:
    try:
        source_documents = [_load_qt_document(Path(path)) for path in input_files]
    except Exception as exc:
        return _visual_failure("visual_oracle_exception", type(exc).__name__)
    if any(document is None for document in source_documents):
        skipped = sum(len(plan) for plan in plans)
        _close_qt_documents(source_documents)
        return _VisualResult(OracleStatus.SOURCE_UNAVAILABLE, pages_skipped=skipped)

    checked = 0
    text_checked = 0
    skipped = 0
    max_mae = 0.0
    max_changed = 0.0
    try:
        for output_index, (output_path, plan) in enumerate(zip(output_paths, plans, strict=True)):
            output_document = _load_qt_document(Path(output_path))
            if output_document is None:
                return _visual_failure(
                    "output_render_load",
                    f"output {output_index + 1} is not renderable",
                    checked,
                    text_checked,
                    max_mae,
                    max_changed,
                )
            try:
                page_indices = (
                    tuple(range(len(plan)))
                    if output_page_indices is None
                    else tuple(output_page_indices[output_index])
                )
                if len(page_indices) != len(plan):
                    return _visual_failure(
                        "visual_plan",
                        f"output {output_index + 1} has an invalid visual page map",
                        checked,
                        text_checked,
                        max_mae,
                        max_changed,
                    )
                for output_page_index, reference in zip(page_indices, plan, strict=True):
                    source_document = source_documents[reference.source_index]
                    if source_document is None:  # Kept for type narrowing.
                        raise RuntimeError("source document unexpectedly unavailable")
                    image_size = _render_size(output_document, output_page_index)
                    try:
                        expected = _render_qt_page(
                            source_document,
                            reference.page_index,
                            image_size,
                            reference.rotation_delta,
                        )
                    except _QtPageUnavailableError:
                        expected = None
                    try:
                        observed = _render_qt_page(
                            output_document,
                            output_page_index,
                            image_size,
                            0,
                        )
                    except _QtPageUnavailableError:
                        return _visual_failure(
                            "output_render",
                            f"output {output_index + 1}, page {output_page_index + 1} "
                            "is not renderable",
                            checked,
                            text_checked,
                            max_mae,
                            max_changed,
                        )
                    if expected is None:
                        skipped += 1
                        continue
                    difference = _image_difference(expected, observed)
                    if difference is None:
                        return _visual_failure(
                            "visual_difference",
                            f"output {output_index + 1}, page {output_page_index + 1} differs",
                            checked,
                            text_checked,
                            max_mae,
                            max_changed,
                        )
                    normalized_mae, changed_fraction = difference
                    max_mae = max(max_mae, normalized_mae)
                    max_changed = max(max_changed, changed_fraction)
                    checked += 1
                    if _qt_page_text_signature(
                        source_document, reference.page_index
                    ) != _qt_page_text_signature(output_document, output_page_index):
                        return _visual_failure(
                            "text_difference",
                            f"output {output_index + 1}, page {output_page_index + 1} text differs",
                            checked,
                            text_checked,
                            max_mae,
                            max_changed,
                        )
                    text_checked += 1
            finally:
                output_document.close()
    except Exception as exc:
        return _visual_failure(
            "visual_oracle_exception",
            type(exc).__name__,
            checked,
            text_checked,
            max_mae,
            max_changed,
        )
    finally:
        _close_qt_documents(source_documents)
    if skipped:
        return _VisualResult(
            OracleStatus.SOURCE_UNAVAILABLE,
            pages_checked=checked,
            text_pages_checked=text_checked,
            pages_skipped=skipped,
            max_normalized_mae=max_mae,
            max_changed_fraction=max_changed,
        )
    return _VisualResult(
        OracleStatus.OK,
        pages_checked=checked,
        text_pages_checked=text_checked,
        max_normalized_mae=max_mae,
        max_changed_fraction=max_changed,
    )


def _visual_failure(
    code: str,
    detail: str,
    checked: int = 0,
    text_checked: int = 0,
    max_mae: float = 0.0,
    max_changed: float = 0.0,
) -> _VisualResult:
    return _VisualResult(
        OracleStatus.MISMATCH,
        pages_checked=checked,
        text_pages_checked=text_checked,
        max_normalized_mae=max_mae,
        max_changed_fraction=max_changed,
        failure_code=code,
        detail=detail,
    )


def _load_qt_document(path: Path) -> Any | None:
    global _QT_APP
    if sys.platform.startswith("linux"):
        import os

        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtPdf import QPdfDocument
    from PySide6.QtWidgets import QApplication

    _QT_APP = QApplication.instance() or QApplication([])
    document = QPdfDocument()
    error = document.load(str(path))
    _QT_APP.processEvents()
    if error != QPdfDocument.Error.None_ or document.pageCount() <= 0:
        document.close()
        return None
    return document


def _close_qt_documents(documents: Sequence[Any | None]) -> None:
    for document in documents:
        if document is not None:
            document.close()


def _render_size(document: Any, page_index: int) -> Any:
    from PySide6.QtCore import QSize

    points = document.pagePointSize(page_index)
    width = max(float(points.width()), 1.0)
    height = max(float(points.height()), 1.0)
    scale = _RENDER_LONG_EDGE / max(width, height)
    return QSize(max(1, round(width * scale)), max(1, round(height * scale)))


def _render_qt_page(document: Any, page_index: int, size: Any, rotation_delta: int) -> Any:
    from PIL import Image
    from PySide6.QtGui import QImage
    from PySide6.QtPdf import QPdfDocumentRenderOptions

    options = QPdfDocumentRenderOptions()
    options.setRenderFlags(QPdfDocumentRenderOptions.RenderFlag.Annotations)
    rotations = {
        0: QPdfDocumentRenderOptions.Rotation.None_,
        90: QPdfDocumentRenderOptions.Rotation.Clockwise90,
        180: QPdfDocumentRenderOptions.Rotation.Clockwise180,
        270: QPdfDocumentRenderOptions.Rotation.Clockwise270,
    }
    options.setRotation(rotations[rotation_delta % 360])
    image = document.render(page_index, size, options)
    if image.isNull():
        raise _QtPageUnavailableError("QtPdf returned a null page image")
    rgba = image.convertToFormat(QImage.Format.Format_RGBA8888)
    payload = bytes(rgba.constBits())[: rgba.sizeInBytes()]
    rendered = Image.frombytes(
        "RGBA",
        (rgba.width(), rgba.height()),
        payload,
        "raw",
        "RGBA",
        rgba.bytesPerLine(),
    )
    white = Image.new("RGBA", rendered.size, (255, 255, 255, 255))
    return Image.alpha_composite(white, rendered).convert("RGB")


def _qt_page_text_signature(
    document: Any,
    page_index: int,
) -> tuple[tuple[str, int], ...]:
    value = document.getAllText(page_index).text()
    normalized = unicodedata.normalize(
        "NFC",
        value.replace("\r\n", "\n").replace("\r", "\n"),
    )
    # QtPdf may change extraction order when /Rotate changes, especially on macOS.
    # Per-page character multiplicity still detects text loss or mutation while the
    # structural and raster oracles independently enforce page mapping and layout.
    characters = Counter(character for character in normalized if not character.isspace())
    return tuple(sorted(characters.items()))


def _image_difference(expected: Any, observed: Any) -> tuple[float, float] | None:
    from PIL import ImageChops

    if expected.size != observed.size:
        return None
    difference = ImageChops.difference(expected, observed)
    histogram = difference.histogram()
    pixel_count = expected.width * expected.height
    normalized_mae = sum((index % 256) * count for index, count in enumerate(histogram)) / (
        pixel_count * 3 * 255
    )
    changed_pixels = sum(1 for pixel in difference.getdata() if _pixel_changed(pixel))
    changed_fraction = changed_pixels / pixel_count
    if (
        not math.isfinite(normalized_mae)
        or normalized_mae > _MAX_NORMALIZED_MAE
        or changed_fraction > _MAX_CHANGED_PIXEL_FRACTION
    ):
        return None
    return normalized_mae, changed_fraction


def _pixel_changed(pixel: Any) -> bool:
    if isinstance(pixel, tuple):
        return max(int(channel) for channel in pixel) > _CHANGED_CHANNEL_TOLERANCE
    return int(pixel or 0) > _CHANGED_CHANNEL_TOLERANCE
