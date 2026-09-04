from __future__ import annotations

from dataclasses import dataclass

from pdfmod.domain.page_ranges import validate_complete_page_order, validate_page_numbers


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

    def normalized_name(self, fallback: str) -> str:
        return self.name.strip() or fallback

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
