from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ScanLikelihood = Literal["unknown", "low", "medium", "high"]


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
    # Digital signature carried by the document; False when it cannot be opened.
    signed: bool = False


def unavailable_inspection(size_bytes: int, warning: str) -> DocumentInspection:
    """Build a safe fallback used when an isolated inspection cannot complete."""

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
