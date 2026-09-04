from __future__ import annotations

from collections.abc import Mapping
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import assert_never

import pytest

from pdfmod.domain.jobs import (
    MAX_BASE_NAME_CHARS,
    MAX_PAGE_NUMBER,
    ExtractOptions,
    InsertBlankPageOptions,
    InsertPagesOptions,
    JobRequest,
    MergeOptions,
    OperationOptions,
    OperationType,
    RemoveOptions,
    ReorderOptions,
    RotateOptions,
    SplitOptions,
    allowed_option_keys,
    coerce_operation_options,
)
from pdfmod.domain.page_ranges import PageRange


def _inputs(operation: OperationType, root: Path) -> tuple[Path, ...]:
    if operation in {OperationType.MERGE_PDFS, OperationType.INSERT_PDF_PAGES}:
        return (root / "first.pdf", root / "second.pdf")
    return (root / "source.pdf",)


@pytest.mark.parametrize(
    ("operation", "raw_options", "expected_type"),
    (
        (OperationType.MERGE_PDFS, {}, MergeOptions),
        (
            OperationType.EXTRACT_PAGES,
            {"page_numbers": (1, 3)},
            ExtractOptions,
        ),
        (
            OperationType.REMOVE_PAGES,
            {"page_numbers": (2,)},
            RemoveOptions,
        ),
        (
            OperationType.SPLIT_BY_RANGES,
            {"page_groups": ((1,), (2, 3)), "base_name": "part"},
            SplitOptions,
        ),
        (
            OperationType.ROTATE_PAGES,
            {"page_numbers": (1,), "angle": 90},
            RotateOptions,
        ),
        (
            OperationType.REORDER_PAGES,
            {"page_order": (2, 1)},
            ReorderOptions,
        ),
        (
            OperationType.INSERT_PDF_PAGES,
            {"page_numbers": (2, 1), "insert_after_page": 0},
            InsertPagesOptions,
        ),
        (
            OperationType.INSERT_BLANK_PAGE,
            {"width_mm": 210.0, "height_mm": 297.0, "insert_after_page": 0},
            InsertBlankPageOptions,
        ),
    ),
)
def test_job_request_coerces_legacy_mappings_to_typed_options(
    tmp_path: Path,
    operation: OperationType,
    raw_options: dict[str, object],
    expected_type: type[OperationOptions],
) -> None:
    job = JobRequest(
        operation=operation,
        input_files=_inputs(operation, tmp_path),
        output_dir=tmp_path,
        options=raw_options,
    )

    assert isinstance(job.options, expected_type)
    assert isinstance(job.options, Mapping)
    assert job.options.operation is operation
    assert dict(job.options) == raw_options
    assert "operation" not in job.options


def test_job_request_preserves_a_matching_typed_options_object(tmp_path: Path) -> None:
    options = ExtractOptions(
        page_numbers=(1, 2),
        output_path=tmp_path / "extract.pdf",
    )

    job = JobRequest(
        operation=OperationType.EXTRACT_PAGES,
        input_files=(tmp_path / "source.pdf",),
        output_dir=tmp_path,
        options=options,
    )

    assert job.options is options
    assert job.require_options(ExtractOptions) is options
    assert options == {
        "page_numbers": (1, 2),
        "output_path": tmp_path / "extract.pdf",
    }
    assert options != RemoveOptions((1, 2), tmp_path / "extract.pdf")


def test_options_are_deeply_immutable_for_supported_values() -> None:
    options = SplitOptions(page_groups=((1, 2), (3,)), base_name="part")

    with pytest.raises(FrozenInstanceError):
        options.__setattr__("base_name", "changed")
    with pytest.raises(TypeError):
        options.page_groups[0][0] = 99  # type: ignore[index]


def test_operation_options_form_an_exhaustive_discriminated_union() -> None:
    options: tuple[OperationOptions, ...] = (
        MergeOptions(),
        ExtractOptions((1,)),
        RemoveOptions((1,)),
        SplitOptions(page_groups=((1,),)),
        RotateOptions((1,), 90),
        ReorderOptions((1,)),
        InsertPagesOptions((1,), 0),
        InsertBlankPageOptions(210, 297, 0),
    )

    assert tuple(_option_payload(option) for option in options) == (
        (),
        (1,),
        (1,),
        (1,),
        (1,),
        (1,),
        (1,),
        (),
    )


def _option_payload(options: OperationOptions) -> tuple[int, ...]:
    if options.operation is OperationType.MERGE_PDFS:
        return ()
    if options.operation is OperationType.EXTRACT_PAGES:
        return options.page_numbers
    if options.operation is OperationType.REMOVE_PAGES:
        return options.page_numbers
    if options.operation is OperationType.SPLIT_BY_RANGES:
        if options.page_groups is not None:
            return options.page_groups[0]
        if options.ranges is not None:
            return options.ranges[0].pages
        raise AssertionError("validated split options always have a plan")
    if options.operation is OperationType.ROTATE_PAGES:
        return options.page_numbers
    if options.operation is OperationType.REORDER_PAGES:
        return options.page_order
    if options.operation is OperationType.INSERT_PDF_PAGES:
        return options.page_numbers
    if options.operation is OperationType.INSERT_BLANK_PAGE:
        return ()
    assert_never(options)


@pytest.mark.parametrize(
    ("operation", "options"),
    (
        (OperationType.MERGE_PDFS, {"unexpected": True}),
        (OperationType.EXTRACT_PAGES, {}),
        (OperationType.REMOVE_PAGES, {"output_path": Path("out.pdf")}),
        (OperationType.SPLIT_BY_RANGES, {}),
        (OperationType.ROTATE_PAGES, {"page_numbers": (1,)}),
        (OperationType.REORDER_PAGES, {}),
        (OperationType.INSERT_PDF_PAGES, {"page_numbers": (1,)}),
        (OperationType.INSERT_BLANK_PAGE, {"width_mm": 210.0}),
    ),
)
def test_central_validation_rejects_unknown_or_incomplete_options(
    operation: OperationType,
    options: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        coerce_operation_options(operation, options)


@pytest.mark.parametrize(
    ("operation", "options"),
    (
        (OperationType.EXTRACT_PAGES, {"page_numbers": [1]}),
        (OperationType.EXTRACT_PAGES, {"page_numbers": ()}),
        (OperationType.EXTRACT_PAGES, {"page_numbers": (0,)}),
        (OperationType.EXTRACT_PAGES, {"page_numbers": (True,)}),
        (OperationType.EXTRACT_PAGES, {"page_numbers": (MAX_PAGE_NUMBER + 1,)}),
        (
            OperationType.EXTRACT_PAGES,
            {"page_numbers": (1,), "output_path": "out.pdf"},
        ),
        (OperationType.ROTATE_PAGES, {"page_numbers": (1,), "angle": True}),
        (OperationType.ROTATE_PAGES, {"page_numbers": (1,), "angle": 45}),
        (
            OperationType.INSERT_PDF_PAGES,
            {"page_numbers": (1,), "insert_after_page": -1},
        ),
        (OperationType.SPLIT_BY_RANGES, {"ranges": []}),
        (OperationType.SPLIT_BY_RANGES, {"page_groups": ([1],)}),
        (OperationType.SPLIT_BY_RANGES, {"page_groups": ((1,),), "base_name": ""}),
        (
            OperationType.SPLIT_BY_RANGES,
            {"page_groups": ((1,),), "base_name": " part"},
        ),
        (
            OperationType.SPLIT_BY_RANGES,
            {"page_groups": ((1,),), "base_name": "x" * (MAX_BASE_NAME_CHARS + 1)},
        ),
        (
            OperationType.SPLIT_BY_RANGES,
            {"ranges": (PageRange(1, 2, (1,)),)},
        ),
        (
            OperationType.SPLIT_BY_RANGES,
            {
                "ranges": (
                    PageRange(
                        MAX_PAGE_NUMBER + 1,
                        MAX_PAGE_NUMBER + 1,
                        (MAX_PAGE_NUMBER + 1,),
                    ),
                )
            },
        ),
        (
            OperationType.SPLIT_BY_RANGES,
            {"ranges": (PageRange(1, 1, (1,)),), "page_groups": ((1,),)},
        ),
    ),
)
def test_central_validation_rejects_invalid_operation_values(
    operation: OperationType,
    options: dict[str, object],
) -> None:
    with pytest.raises((TypeError, ValueError)):
        coerce_operation_options(operation, options)


def test_reorder_options_allow_repeated_pages_for_duplication() -> None:
    options = ReorderOptions((1, 1, 2, 3))

    assert options.page_order == (1, 1, 2, 3)


def test_typed_options_must_match_the_declared_operation(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="do not match"):
        JobRequest(
            operation=OperationType.MERGE_PDFS,
            input_files=(tmp_path / "first.pdf", tmp_path / "second.pdf"),
            output_dir=tmp_path,
            options=ExtractOptions((1,)),
        )


def test_require_options_rejects_a_wrong_requested_type(tmp_path: Path) -> None:
    job = JobRequest(
        operation=OperationType.MERGE_PDFS,
        input_files=(tmp_path / "first.pdf", tmp_path / "second.pdf"),
        output_dir=tmp_path,
        options=MergeOptions(),
    )

    with pytest.raises(TypeError, match="do not match"):
        job.require_options(ExtractOptions)


@pytest.mark.parametrize(
    ("operation", "input_files"),
    (
        (OperationType.MERGE_PDFS, (Path("only.pdf"),)),
        (OperationType.EXTRACT_PAGES, ()),
        (OperationType.REMOVE_PAGES, (Path("one.pdf"), Path("two.pdf"))),
        (OperationType.INSERT_PDF_PAGES, (Path("one.pdf"),)),
    ),
)
def test_job_request_validates_input_arity_per_operation(
    tmp_path: Path,
    operation: OperationType,
    input_files: tuple[Path, ...],
) -> None:
    if operation is OperationType.MERGE_PDFS:
        options: dict[str, object] = {}
    elif operation is OperationType.INSERT_PDF_PAGES:
        options = {"page_numbers": (1,), "insert_after_page": 0}
    else:
        options = {"page_numbers": (1,)}

    with pytest.raises(ValueError):
        JobRequest(
            operation=operation,
            input_files=input_files,
            output_dir=tmp_path,
            options=options,
        )


def test_allowed_option_keys_are_centralized_for_every_operation() -> None:
    assert {operation: allowed_option_keys(operation) for operation in OperationType} == {
        OperationType.MERGE_PDFS: frozenset({"output_path"}),
        OperationType.EXTRACT_PAGES: frozenset({"output_path", "page_numbers"}),
        OperationType.REMOVE_PAGES: frozenset({"output_path", "page_numbers"}),
        OperationType.SPLIT_BY_RANGES: frozenset({"ranges", "page_groups", "base_name"}),
        OperationType.ROTATE_PAGES: frozenset({"output_path", "page_numbers", "angle"}),
        OperationType.REORDER_PAGES: frozenset({"output_path", "page_order"}),
        OperationType.INSERT_PDF_PAGES: frozenset(
            {"output_path", "page_numbers", "insert_after_page"}
        ),
        OperationType.INSERT_BLANK_PAGE: frozenset(
            {"output_path", "width_mm", "height_mm", "insert_after_page"}
        ),
    }
