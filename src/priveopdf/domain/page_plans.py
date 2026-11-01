from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from priveopdf.domain.page_ranges import validate_complete_page_order, validate_page_numbers
from priveopdf.utils.secure_paths import normalize_filename_component

SPLIT_BASE_NAME_MAX_BYTES = 180


def every_n_pages_groups(page_count: int, size: int) -> tuple[tuple[int, ...], ...]:
    """Consecutive groups of `size` pages; the last group keeps the remainder."""

    if page_count < 1 or size < 1:
        raise ValueError("page count and group size must be positive")
    return tuple(
        tuple(range(start, min(start + size, page_count + 1)))
        for start in range(1, page_count + 1, size)
    )


def split_group_file_names(base_name: str, group_count: int) -> tuple[str, ...]:
    """File names of a split by page groups; the engine writes exactly these names."""

    name = normalize_filename_component(base_name, max_bytes=SPLIT_BASE_NAME_MAX_BYTES)
    return tuple(f"{name}_part-{index}.pdf" for index in range(1, group_count + 1))


def split_range_file_names(base_name: str, range_labels: Sequence[str]) -> tuple[str, ...]:
    """File names of a split by text ranges; the engine writes exactly these names."""

    name = normalize_filename_component(base_name, max_bytes=SPLIT_BASE_NAME_MAX_BYTES)
    return tuple(f"{name}_pages-{label}.pdf" for label in range_labels)


@dataclass(frozen=True)
class PageSelectionModel:
    page_count: int
    pages: tuple[int, ...] = ()

    @classmethod
    def from_pages(cls, page_count: int, pages: tuple[int, ...] | list[int]) -> PageSelectionModel:
        return cls(page_count=page_count, pages=tuple(sorted(set(pages))))

    def validate(self, *, allow_empty: bool = False, allow_all: bool = True) -> None:
        if not self.pages:
            if allow_empty:
                return
            raise ValueError("page selection is empty")
        validate_page_numbers(self.pages, self.page_count)
        if not allow_all and len(set(self.pages)) >= self.page_count:
            raise ValueError("page selection cannot include every page")

    def as_page_numbers(
        self,
        *,
        allow_empty: bool = False,
        allow_all: bool = True,
    ) -> tuple[int, ...]:
        self.validate(allow_empty=allow_empty, allow_all=allow_all)
        return self.pages


@dataclass(frozen=True)
class PageOutputGroupModel:
    name: str
    pages: tuple[int, ...] = ()

    def validate(self, page_count: int, *, allow_empty: bool = False) -> None:
        if not self.pages:
            if allow_empty:
                return
            raise ValueError("page output group is empty")
        validate_page_numbers(self.pages, page_count)


@dataclass(frozen=True)
class SplitPlanModel:
    page_count: int
    groups: tuple[PageOutputGroupModel, ...]
    allow_duplicates: bool = False

    def non_empty_groups(self) -> tuple[PageOutputGroupModel, ...]:
        return tuple(group for group in self.groups if group.pages)

    def page_groups(self) -> tuple[tuple[int, ...], ...]:
        groups = self.non_empty_groups()
        if not groups:
            raise ValueError("split plan has no output groups")

        seen: set[int] = set()
        for group in groups:
            group.validate(self.page_count)
            if self.allow_duplicates:
                continue
            duplicates = seen.intersection(group.pages)
            if duplicates:
                raise ValueError("split plan contains duplicate pages")
            seen.update(group.pages)
        return tuple(group.pages for group in groups)

    def to_job_options(self) -> dict[str, object]:
        return {"page_groups": self.page_groups()}


@dataclass(frozen=True)
class ReorderPlanModel:
    page_count: int
    page_order: tuple[int, ...]

    def validate(self) -> None:
        validate_complete_page_order(self.page_order, self.page_count)

    def to_job_options(self) -> dict[str, object]:
        self.validate()
        return {"page_order": self.page_order}
