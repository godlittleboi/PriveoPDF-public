from __future__ import annotations

import pytest

from pdfmod.domain.page_ranges import (
    parse_page_order,
    parse_page_range_groups,
    parse_page_ranges,
    validate_complete_page_order,
    validate_page_assembly,
    validate_page_numbers,
)


def test_parse_single_page() -> None:
    assert parse_page_ranges("1") == [1]


def test_parse_simple_range() -> None:
    assert parse_page_ranges("1-3") == [1, 2, 3]


def test_parse_multiple_ranges_and_pages() -> None:
    assert parse_page_ranges("1-3,5,8-10") == [1, 2, 3, 5, 8, 9, 10]


def test_parse_allows_spaces() -> None:
    assert parse_page_ranges("1, 3 - 4") == [1, 3, 4]


def test_parse_preserves_duplicates() -> None:
    assert parse_page_ranges("1,1,2-3,2") == [1, 1, 2, 3, 2]


@pytest.mark.parametrize("expression", ["", "0", "-1", "3-1", "texte", "1,,2", "1--3"])
def test_parse_rejects_invalid_ranges(expression: str) -> None:
    with pytest.raises(ValueError):
        parse_page_ranges(expression)


def test_validate_rejects_page_out_of_bounds() -> None:
    with pytest.raises(ValueError):
        validate_page_numbers(parse_page_ranges("1,6"), page_count=5)


def test_validate_rejects_bool_page_numbers() -> None:
    with pytest.raises(ValueError):
        validate_page_numbers((True,), page_count=5)  # type: ignore[arg-type]


def test_parse_range_groups_keeps_split_labels() -> None:
    groups = parse_page_range_groups("1-3,5,8-10")

    assert [group.label for group in groups] == ["1-3", "5", "8-10"]


def test_parse_page_order_accepts_valid_order() -> None:
    assert parse_page_order("3,1,2") == [3, 1, 2]


def test_parse_page_order_accepts_ranges() -> None:
    assert parse_page_order("2,1,3-5") == [2, 1, 3, 4, 5]


def test_validate_complete_page_order_accepts_permutation() -> None:
    validate_complete_page_order(parse_page_order("3,1,2"), page_count=3)


def test_validate_complete_page_order_rejects_empty_order() -> None:
    with pytest.raises(ValueError):
        validate_complete_page_order([], page_count=3)


def test_validate_page_assembly_accepts_duplicates_but_requires_all_source_pages() -> None:
    validate_page_assembly((1, 1, 3, 2), 3)

    with pytest.raises(ValueError, match="at least once"):
        validate_page_assembly((1, 1, 3), 3)

    with pytest.raises(ValueError, match="out of bounds"):
        validate_page_assembly((1, 2, 3, 4), 3)


def test_validate_complete_page_order_rejects_duplicates() -> None:
    with pytest.raises(ValueError):
        validate_complete_page_order(parse_page_order("1,1,2"), page_count=3)


def test_validate_complete_page_order_rejects_missing_page() -> None:
    with pytest.raises(ValueError):
        validate_complete_page_order(parse_page_order("1,3"), page_count=3)


def test_validate_complete_page_order_rejects_page_out_of_bounds() -> None:
    with pytest.raises(ValueError):
        validate_complete_page_order(parse_page_order("1,2,4"), page_count=3)


def test_parse_page_order_rejects_invalid_character() -> None:
    with pytest.raises(ValueError):
        parse_page_order("1,a,2")
