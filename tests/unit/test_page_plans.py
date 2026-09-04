from __future__ import annotations

import pytest

from pdfmod.domain.page_plans import (
    PageOutputGroupModel,
    PageSelectionModel,
    ReorderPlanModel,
    SplitPlanModel,
)


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
