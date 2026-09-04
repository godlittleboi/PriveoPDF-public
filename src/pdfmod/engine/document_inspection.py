from __future__ import annotations

import time
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from itertools import islice
from pathlib import Path
from typing import Literal

import pikepdf

ScanLikelihood = Literal["unknown", "low", "medium", "high"]

MAX_SAMPLE_PAGES = 3
MAX_CONTENT_SAMPLE_BYTES = 256 * 1024


@dataclass(frozen=True)
class InspectionBudget:
    """Soft structural-analysis limits; the subprocess supervisor supplies the hard timeout."""

    max_pages: int = MAX_SAMPLE_PAGES
    max_content_streams: int = 24
    max_declared_content_bytes: int = MAX_CONTENT_SAMPLE_BYTES
    max_resource_objects: int = 512
    timeout_seconds: float = 0.5

    def __post_init__(self) -> None:
        integer_limits = (
            self.max_pages,
            self.max_content_streams,
            self.max_declared_content_bytes,
            self.max_resource_objects,
        )
        if any(
            not isinstance(value, int) or isinstance(value, bool) or value < 1
            for value in integer_limits
        ):
            raise ValueError("inspection limits must be positive integers")
        if (
            not isinstance(self.timeout_seconds, (int, float))
            or isinstance(self.timeout_seconds, bool)
            or self.timeout_seconds <= 0
            or self.timeout_seconds > 60
        ):
            raise ValueError("inspection timeout must be between zero and 60 seconds")


@dataclass(frozen=True)
class DocumentInspection:
    page_count: int | None
    size_bytes: int
    is_encrypted: bool
    can_open: bool
    has_extractable_text: bool
    scan_likelihood: ScanLikelihood
    ocr_recommended: bool
    warnings: tuple[str, ...] = ()


class DocumentInspectionService:
    def __init__(self, budget: InspectionBudget | None = None) -> None:
        self._budget = budget or InspectionBudget()

    def inspect(self, source_path: Path) -> DocumentInspection:
        started = time.monotonic()
        path = Path(source_path)
        size_bytes = _size_bytes(path)
        if path.suffix.lower() != ".pdf":
            return _unavailable(size_bytes, "not_pdf")
        if not path.exists() or not path.is_file():
            return _unavailable(size_bytes, "missing")

        try:
            with pikepdf.open(path) as pdf:
                page_count = len(pdf.pages)
                is_encrypted = bool(getattr(pdf, "is_encrypted", False))
                sample = _inspect_sample_pages(pdf, self._budget, started)
        except pikepdf.PasswordError:
            return DocumentInspection(
                page_count=None,
                size_bytes=size_bytes,
                is_encrypted=True,
                can_open=False,
                has_extractable_text=False,
                scan_likelihood="unknown",
                ocr_recommended=False,
                warnings=("encrypted",),
            )
        except (pikepdf.PdfError, OSError, ValueError, TypeError):
            return _unavailable(size_bytes, "analysis_failed")

        scan_likelihood = _scan_likelihood(sample)
        has_extractable_text = sample.text_pages > 0
        return DocumentInspection(
            page_count=page_count,
            size_bytes=size_bytes,
            is_encrypted=is_encrypted,
            can_open=True,
            has_extractable_text=has_extractable_text,
            scan_likelihood=scan_likelihood,
            ocr_recommended=scan_likelihood in {"medium", "high"} and not has_extractable_text,
            warnings=tuple(sample.warnings),
        )


@dataclass
class _SampleInspection:
    sampled_pages: int = 0
    text_pages: int = 0
    image_pages: int = 0
    warnings: list[str] = field(default_factory=list)


@dataclass
class _InspectionState:
    budget: InspectionBudget
    started: float
    content_streams: int = 0
    declared_content_bytes: int = 0
    resource_objects: int = 0
    warnings: list[str] = field(default_factory=list)

    def expired(self) -> bool:
        if time.monotonic() - self.started < self.budget.timeout_seconds:
            return False
        self.warn("inspection_timeout")
        return True

    def warn(self, warning: str) -> None:
        if warning not in self.warnings:
            self.warnings.append(warning)


def _inspect_sample_pages(
    pdf: pikepdf.Pdf,
    budget: InspectionBudget | None = None,
    started: float | None = None,
) -> _SampleInspection:
    effective_budget = budget or InspectionBudget()
    state = _InspectionState(
        effective_budget,
        time.monotonic() if started is None else started,
    )
    sample = _SampleInspection()
    for page in islice(pdf.pages, effective_budget.max_pages):
        if state.expired():
            break
        sample.sampled_pages += 1
        try:
            has_text = _page_has_font_resources(page) and _page_has_nonempty_content(page, state)
            has_images = _page_has_image_xobjects(page, state)
        except (pikepdf.PdfError, ValueError, TypeError, OverflowError):
            state.warn("page_analysis_failed")
            continue
        if has_text:
            sample.text_pages += 1
        if has_images:
            sample.image_pages += 1
    sample.warnings.extend(state.warnings)
    return sample


def _page_has_nonempty_content(page: pikepdf.Page, state: _InspectionState) -> bool:
    contents = page.obj.get("/Contents")
    if contents is None:
        return False

    has_content = False
    for stream in _content_streams(contents):
        if state.expired():
            break
        if state.content_streams >= state.budget.max_content_streams:
            state.warn("content_stream_budget_exhausted")
            break
        state.content_streams += 1
        declared_length = _declared_stream_length(stream)
        if declared_length <= 0:
            continue
        has_content = True
        remaining = state.budget.max_declared_content_bytes - state.declared_content_bytes
        if declared_length > remaining:
            state.declared_content_bytes = state.budget.max_declared_content_bytes
            state.warn("content_byte_budget_exhausted")
            break
        state.declared_content_bytes += declared_length
    return has_content


def _content_streams(contents: object) -> Iterator[pikepdf.Stream]:
    if isinstance(contents, pikepdf.Stream):
        yield contents
        return
    if isinstance(contents, pikepdf.Array):
        for item in contents:
            if isinstance(item, pikepdf.Stream):
                yield item


def _declared_stream_length(stream: pikepdf.Stream) -> int:
    value = stream.get("/Length", 0)
    if isinstance(value, bool):
        return 0
    try:
        length = int(value)
    except (TypeError, ValueError, OverflowError):
        return 0
    return max(0, length)


def _page_has_font_resources(page: pikepdf.Page) -> bool:
    resources = page.obj.get("/Resources")
    if not isinstance(resources, pikepdf.Dictionary):
        return False
    fonts = resources.get("/Font")
    return isinstance(fonts, pikepdf.Dictionary) and len(fonts) > 0


def _page_has_image_xobjects(page: pikepdf.Page, state: _InspectionState) -> bool:
    resources = page.obj.get("/Resources")
    if not isinstance(resources, pikepdf.Dictionary):
        return False
    xobjects = resources.get("/XObject")
    if not isinstance(xobjects, pikepdf.Dictionary):
        return False
    values = getattr(xobjects, "values", None)
    if not callable(values):
        return False
    xobject_values = values()
    if not isinstance(xobject_values, Iterable):
        return False
    for value in xobject_values:
        if state.expired():
            return False
        if state.resource_objects >= state.budget.max_resource_objects:
            state.warn("resource_budget_exhausted")
            return False
        state.resource_objects += 1
        if _is_image_xobject(value):
            return True
    return False


def _is_image_xobject(value: object) -> bool:
    try:
        getter = getattr(value, "get", None)
        return callable(getter) and str(getter("/Subtype")) == "/Image"
    except (AttributeError, ValueError, pikepdf.PdfError):
        return False


def _scan_likelihood(sample: _SampleInspection) -> ScanLikelihood:
    if sample.sampled_pages == 0:
        return "unknown"
    if sample.text_pages > 0:
        return "low"
    if sample.image_pages == 0:
        return "unknown"
    if sample.image_pages >= max(1, sample.sampled_pages - 1):
        return "high"
    return "medium"


def _size_bytes(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def unavailable_inspection(size_bytes: int, warning: str) -> DocumentInspection:
    """Build a safe fallback used when an isolated inspection cannot complete."""

    return _unavailable(size_bytes, warning)


def _unavailable(size_bytes: int, warning: str) -> DocumentInspection:
    return DocumentInspection(
        page_count=None,
        size_bytes=size_bytes,
        is_encrypted=False,
        can_open=False,
        has_extractable_text=False,
        scan_likelihood="unknown",
        ocr_recommended=False,
        warnings=(warning,),
    )
