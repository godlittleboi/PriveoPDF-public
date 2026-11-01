from __future__ import annotations

from pathlib import Path

import pikepdf
import pytest

from priveopdf.domain.page_plans import (
    PageOutputGroupModel,
    PageSelectionModel,
    ReorderPlanModel,
    SplitPlanModel,
    every_n_pages_groups,
    split_group_file_names,
    split_range_file_names,
)
from priveopdf.domain.page_ranges import parse_page_range_groups
from priveopdf.engine.pdf_structural import split_pdf_by_page_groups, split_pdf_by_ranges


def test_page_selection_model_deduplicates_and_validates() -> None:
    selection = PageSelectionModel.from_pages(5, [3, 1, 3])

    assert selection.as_page_numbers() == (1, 3)

    with pytest.raises(ValueError, match="cannot include every page"):
        PageSelectionModel.from_pages(2, [1, 2]).as_page_numbers(allow_all=False)


def test_split_plan_model_rejects_duplicate_pages_by_default() -> None:
    plan = SplitPlanModel(
        5,
        (
            PageOutputGroupModel("first", (1, 2)),
            PageOutputGroupModel("second", (2, 3)),
        ),
    )

    with pytest.raises(ValueError, match="duplicate"):
        plan.page_groups()


def test_split_plan_model_ignores_empty_groups_and_preserves_order() -> None:
    plan = SplitPlanModel(
        5,
        (
            PageOutputGroupModel("first", (3, 1)),
            PageOutputGroupModel("empty", ()),
            PageOutputGroupModel("second", (2,)),
        ),
    )

    assert plan.to_job_options() == {"page_groups": ((3, 1), (2,))}


def test_reorder_plan_model_requires_complete_permutation() -> None:
    assert ReorderPlanModel(3, (3, 1, 2)).to_job_options() == {"page_order": (3, 1, 2)}

    with pytest.raises(ValueError, match="duplicates"):
        ReorderPlanModel(3, (1, 1, 2)).validate()


def test_every_n_pages_groups_keeps_the_remainder_in_the_last_file() -> None:
    assert every_n_pages_groups(7, 3) == ((1, 2, 3), (4, 5, 6), (7,))
    assert every_n_pages_groups(3, 1) == ((1,), (2,), (3,))
    assert every_n_pages_groups(2, 5) == ((1, 2),)
    with pytest.raises(ValueError):
        every_n_pages_groups(3, 0)


def test_announced_split_names_are_the_names_the_engine_writes(tmp_path: Path) -> None:
    source = tmp_path / "Rapport annuel.pdf"
    pdf = pikepdf.Pdf.new()
    for _ in range(5):
        pdf.add_blank_page(page_size=(200, 200))
    pdf.save(source)
    pdf.close()
    by_groups = tmp_path / "groups"
    by_ranges = tmp_path / "ranges"
    by_groups.mkdir()
    by_ranges.mkdir()

    written = split_pdf_by_page_groups(source, by_groups, every_n_pages_groups(5, 2))
    ranges = parse_page_range_groups("1-2,3-5")
    written_ranges = split_pdf_by_ranges(source, by_ranges, ranges)

    assert tuple(path.name for path in written) == split_group_file_names(source.stem, 3)
    assert tuple(path.name for path in written_ranges) == split_range_file_names(
        source.stem, tuple(page_range.label for page_range in ranges)
    )
