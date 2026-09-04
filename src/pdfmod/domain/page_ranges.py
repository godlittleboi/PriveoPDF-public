from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PageRange:
    start: int
    end: int
    pages: tuple[int, ...]

    def __post_init__(self) -> None:
        if not _is_page_number(self.start) or not _is_page_number(self.end):
            raise ValueError("page range bounds must be positive integers")
        if self.start > self.end:
            raise ValueError("page range start must be before end")
        if not isinstance(self.pages, tuple) or not self.pages:
            raise ValueError("page range pages must be a non-empty tuple")
        for page_number in self.pages:
            if not _is_page_number(page_number):
                raise ValueError("page range pages must contain positive integers")

    @property
    def label(self) -> str:
        if self.start == self.end:
            return str(self.start)
        return f"{self.start}-{self.end}"


def parse_page_ranges(expression: str) -> list[int]:
    """Parse 1-based page ranges and preserve user order and duplicates.

    Duplicates are intentional: extraction repeats duplicated pages in the
    requested order, while removal treats repeated page numbers as one removal.
    Bounds are validated separately with validate_page_numbers().
    """
    return [page for page_range in parse_page_range_groups(expression) for page in page_range.pages]


def parse_page_order(expression: str) -> list[int]:
    """Parse a 1-based textual page sequence.

    Descending ranges are rejected by the shared range parser. The Organizer
    may repeat page numbers to duplicate pages; completeness and bounds are
    validated separately with validate_page_assembly().
    """
    return parse_page_ranges(expression)


def parse_page_range_groups(expression: str) -> tuple[PageRange, ...]:
    """Parse 1-based page ranges into comma-separated groups for split jobs."""
    cleaned = expression.replace(" ", "")
    if not cleaned:
        raise ValueError("page range is empty")

    ranges: list[PageRange] = []
    for part in cleaned.split(","):
        if not part:
            raise ValueError("empty page range segment")
        ranges.append(_parse_segment(part))
    return tuple(ranges)


def validate_page_numbers(page_numbers: list[int] | tuple[int, ...], page_count: int) -> None:
    if page_count < 1:
        raise ValueError("page_count must be greater than zero")
    if not page_numbers:
        raise ValueError("page range is empty")
    for page_number in page_numbers:
        if not _is_page_number(page_number):
            raise ValueError("page number must be a positive integer")
        if page_number < 1 or page_number > page_count:
            raise ValueError("page number is out of bounds")


def validate_page_assembly(page_order: list[int] | tuple[int, ...], page_count: int) -> None:
    """Validate an ordered output containing every source page at least once.

    Repeated page numbers are intentional and represent duplicated pages.
    Omitting a source page remains invalid in the reorganization workflow.
    """
    validate_page_numbers(page_order, page_count)
    expected_pages = set(range(1, page_count + 1))
    if set(page_order) != expected_pages:
        raise ValueError("page order must include every source page at least once")


def validate_complete_page_order(page_order: list[int] | tuple[int, ...], page_count: int) -> None:
    validate_page_numbers(page_order, page_count)

    unique_pages = set(page_order)
    if len(unique_pages) != len(page_order):
        raise ValueError("page order contains duplicates")

    expected_pages = set(range(1, page_count + 1))
    if unique_pages != expected_pages:
        raise ValueError("page order must include every page exactly once")


def validate_page_ranges(page_ranges: tuple[PageRange, ...], page_count: int) -> None:
    if not page_ranges:
        raise ValueError("page range is empty")
    for page_range in page_ranges:
        validate_page_numbers(page_range.pages, page_count)


def _parse_segment(part: str) -> PageRange:
    if "-" in part:
        return _parse_range(part)
    page_number = _parse_page_number(part)
    return PageRange(start=page_number, end=page_number, pages=(page_number,))


def _parse_range(part: str) -> PageRange:
    bounds = part.split("-")
    if len(bounds) != 2 or not bounds[0] or not bounds[1]:
        raise ValueError("invalid page range")
    start = _parse_page_number(bounds[0])
    end = _parse_page_number(bounds[1])
    if start > end:
        raise ValueError("page range start must be before end")
    return PageRange(start=start, end=end, pages=tuple(range(start, end + 1)))


def _parse_page_number(value: str) -> int:
    if not value.isdecimal():
        raise ValueError("page number must be numeric")
    page_number = int(value)
    if page_number < 1:
        raise ValueError("page number must be positive")
    return page_number


def _is_page_number(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 1
