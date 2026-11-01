from __future__ import annotations

import math
from typing import Final

MIN_PDF_PAGE_MM: Final = 1.0
MAX_PDF_PAGE_MM: Final = 5_080.0
POINTS_PER_MM: Final = 72.0 / 25.4

PAPER_SIZES_MM: Final[dict[str, tuple[float, float]]] = {
    "a3": (297.0, 420.0),
    "a4": (210.0, 297.0),
    "a5": (148.0, 210.0),
    "letter": (215.9, 279.4),
    "legal": (215.9, 355.6),
}


def validate_page_dimension_mm(value: object, field_name: str = "dimension") -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be a real number")
    dimension = float(value)
    if not math.isfinite(dimension):
        raise ValueError(f"{field_name} must be finite")
    if not MIN_PDF_PAGE_MM <= dimension <= MAX_PDF_PAGE_MM:
        raise ValueError(f"{field_name} must be between {MIN_PDF_PAGE_MM} and {MAX_PDF_PAGE_MM} mm")
    return dimension


def orient_page_dimensions(
    width_mm: object, height_mm: object, *, landscape: bool
) -> tuple[float, float]:
    width = validate_page_dimension_mm(width_mm, "width_mm")
    height = validate_page_dimension_mm(height_mm, "height_mm")
    short, long = sorted((width, height))
    return (long, short) if landscape else (short, long)


def millimetres_to_points(value: object) -> float:
    return validate_page_dimension_mm(value) * POINTS_PER_MM
