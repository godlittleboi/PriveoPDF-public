from __future__ import annotations

import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import BinaryIO, TypeGuard

import pikepdf

from pdfmod.domain.errors import (
    EncryptedPdfError,
    InputPathError,
    InternalPdfEngineError,
    InvalidPageOrderError,
    InvalidPageSelectionError,
    InvalidPdfError,
    InvalidSplitPlanError,
    OutputWriteError,
    PdfModError,
)
from pdfmod.domain.jobs import (
    ExtractOptions,
    InsertBlankPageOptions,
    InsertPagesOptions,
    JobRequest,
    JobResult,
    MergeOptions,
    OperationType,
    RemoveOptions,
    ReorderOptions,
    RotateOptions,
    SplitOptions,
)
from pdfmod.domain.page_ranges import (
    PageRange,
    validate_page_assembly,
    validate_page_numbers,
    validate_page_ranges,
)
from pdfmod.domain.paper_sizes import millimetres_to_points, validate_page_dimension_mm
from pdfmod.utils.secure_paths import (
    PublishedOutput,
    atomic_write_no_replace_tracked,
    build_confined_destination,
    normalize_filename_component,
)
from pdfmod.utils.validation import (
    prepare_pdf_output_path,
    validate_pdf_inputs,
    validate_pdf_output_path,
)

type _StructuralJobHandler = Callable[[JobRequest, float], JobResult]

_MAX_SPLIT_BASE_NAME_BYTES = 180


def run_structural_job(job: JobRequest) -> JobResult:
    started = time.monotonic()
    try:
        handler = _STRUCTURAL_JOB_HANDLERS.get(job.operation)
        if handler is None:
            raise PdfModError("Unsupported operation")
        return handler(job, started)
    except PdfModError as exc:
        return _error_result(exc, started)
    except Exception as exc:
        error = InternalPdfEngineError(
            technical_detail=f"{InternalPdfEngineError.technical_code}:{type(exc).__name__}"
        )
        return _error_result(error, started)


def get_page_count(pdf_path: Path) -> int:
    with _open_pdf(Path(pdf_path)) as pdf:
        return len(pdf.pages)


def merge_pdfs(input_paths: tuple[Path, ...] | list[Path], output_path: Path) -> Path:
    inputs = tuple(Path(path) for path in input_paths)
    requested_output = Path(output_path)
    validate_pdf_inputs(inputs, minimum_count=2)
    output = prepare_pdf_output_path(requested_output, inputs)

    merged = pikepdf.Pdf.new()
    try:
        for input_path in inputs:
            with _open_pdf(input_path) as source:
                first_added_page = len(merged.pages)
                merged.add_pages_from(source, forms="preserve")
                _preserve_optional_content_defaults(
                    merged,
                    source,
                    range(first_added_page, len(merged.pages)),
                )
        _save_pdf_to_new_output(merged, output, inputs)
        return output
    finally:
        merged.close()


def extract_pages(input_path: Path, output_path: Path, page_numbers: Sequence[int]) -> Path:
    input_pdf = Path(input_path)
    requested_output = Path(output_path)
    validate_pdf_inputs((input_pdf,), minimum_count=1)
    output = prepare_pdf_output_path(requested_output, (input_pdf,))

    with _open_pdf(input_pdf) as source:
        page_indexes = _page_numbers_to_zero_based(page_numbers, len(source.pages))
        extracted = pikepdf.Pdf.new()
        try:
            extracted.add_pages_from(source, pages=page_indexes, forms="preserve")
            _preserve_optional_content_defaults(extracted, source, range(len(extracted.pages)))
            _save_pdf_to_new_output(extracted, output, (input_pdf,))
            return output
        finally:
            extracted.close()


def remove_pages(input_path: Path, output_path: Path, page_numbers: Sequence[int]) -> Path:
    input_pdf = Path(input_path)
    requested_output = Path(output_path)
    validate_pdf_inputs((input_pdf,), minimum_count=1)
    output = prepare_pdf_output_path(requested_output, (input_pdf,))

    with _open_pdf(input_pdf) as source:
        page_indexes = set(_page_numbers_to_zero_based(page_numbers, len(source.pages)))
        remaining_indexes = [
            index for index in range(len(source.pages)) if index not in page_indexes
        ]
        if not remaining_indexes:
            raise InvalidPageSelectionError()

        reduced = pikepdf.Pdf.new()
        try:
            reduced.add_pages_from(source, pages=remaining_indexes, forms="preserve")
            _preserve_optional_content_defaults(reduced, source, range(len(reduced.pages)))
            _save_pdf_to_new_output(reduced, output, (input_pdf,))
            return output
        finally:
            reduced.close()


def split_pdf_by_ranges(
    input_path: Path,
    output_dir: Path,
    ranges: Sequence[PageRange],
    base_name: str | None = None,
) -> tuple[Path, ...]:
    input_pdf = Path(input_path)
    destination_dir = Path(output_dir)
    validate_pdf_inputs((input_pdf,), minimum_count=1)
    _validate_output_dir(destination_dir)

    with _open_pdf(input_pdf) as source:
        page_ranges = tuple(ranges)
        try:
            validate_page_ranges(page_ranges, len(source.pages))
        except ValueError as exc:
            raise InvalidSplitPlanError() from exc

        name = normalize_filename_component(
            base_name if base_name else input_pdf.stem,
            max_bytes=_MAX_SPLIT_BASE_NAME_BYTES,
        )
        output_paths = tuple(
            build_confined_destination(
                destination_dir,
                f"{name}_pages-{page_range.label}.pdf",
                required_suffix=".pdf",
            )
            for page_range in page_ranges
        )
        if len(set(output_paths)) != len(output_paths):
            raise OutputWriteError()
        for output_path in output_paths:
            validate_pdf_output_path(output_path, (input_pdf,))

        created: list[PublishedOutput] = []
        try:
            for page_range, output_path in zip(page_ranges, output_paths, strict=True):
                split_pdf = pikepdf.Pdf.new()
                try:
                    split_pdf.add_pages_from(
                        source,
                        pages=(page_number - 1 for page_number in page_range.pages),
                        forms="preserve",
                    )
                    _preserve_optional_content_defaults(
                        split_pdf, source, range(len(split_pdf.pages))
                    )
                    created.append(
                        _save_pdf_to_new_output_tracked(split_pdf, output_path, (input_pdf,))
                    )
                finally:
                    split_pdf.close()
        except Exception:
            _cleanup_created_outputs(created)
            raise
    output_paths = tuple(output.path for output in created)
    _close_published_outputs(created)
    return output_paths


def split_pdf_by_page_groups(
    input_path: Path,
    output_dir: Path,
    page_groups: Sequence[Sequence[int]],
    base_name: str | None = None,
) -> tuple[Path, ...]:
    input_pdf = Path(input_path)
    destination_dir = Path(output_dir)
    validate_pdf_inputs((input_pdf,), minimum_count=1)
    _validate_output_dir(destination_dir)

    with _open_pdf(input_pdf) as source:
        groups = tuple(tuple(group) for group in page_groups)
        if not groups or any(not group for group in groups):
            raise InvalidSplitPlanError()
        for group in groups:
            try:
                validate_page_numbers(group, len(source.pages))
            except ValueError as exc:
                raise InvalidSplitPlanError() from exc

        name = normalize_filename_component(
            base_name if base_name else input_pdf.stem,
            max_bytes=_MAX_SPLIT_BASE_NAME_BYTES,
        )
        output_paths = tuple(
            build_confined_destination(
                destination_dir,
                f"{name}_part-{index}.pdf",
                required_suffix=".pdf",
            )
            for index, _group in enumerate(groups, start=1)
        )
        if len(set(output_paths)) != len(output_paths):
            raise OutputWriteError()
        for output_path in output_paths:
            validate_pdf_output_path(output_path, (input_pdf,))

        created: list[PublishedOutput] = []
        try:
            for group, output_path in zip(groups, output_paths, strict=True):
                split_pdf = pikepdf.Pdf.new()
                try:
                    split_pdf.add_pages_from(
                        source,
                        pages=(page_number - 1 for page_number in group),
                        forms="preserve",
                    )
                    _preserve_optional_content_defaults(
                        split_pdf, source, range(len(split_pdf.pages))
                    )
                    created.append(
                        _save_pdf_to_new_output_tracked(split_pdf, output_path, (input_pdf,))
                    )
                finally:
                    split_pdf.close()
        except Exception:
            _cleanup_created_outputs(created)
            raise
    output_paths = tuple(output.path for output in created)
    _close_published_outputs(created)
    return output_paths


def rotate_pages(
    input_path: Path, output_path: Path, page_numbers: Sequence[int], angle: int
) -> Path:
    input_pdf = Path(input_path)
    requested_output = Path(output_path)
    validate_pdf_inputs((input_pdf,), minimum_count=1)
    output = prepare_pdf_output_path(requested_output, (input_pdf,))
    _validate_rotation_angle(angle)

    with _open_pdf(input_pdf) as source:
        page_indexes = _page_numbers_to_zero_based(page_numbers, len(source.pages))
        if angle:
            for page_index in page_indexes:
                pikepdf.Page(source.pages[page_index]).rotate(angle, relative=True)
        _save_pdf_to_new_output(source, output, (input_pdf,))
        return output


def reorder_pages(input_path: Path, output_path: Path, page_order: Sequence[int]) -> Path:
    input_pdf = Path(input_path)
    requested_output = Path(output_path)
    validate_pdf_inputs((input_pdf,), minimum_count=1)
    output = prepare_pdf_output_path(requested_output, (input_pdf,))

    with _open_pdf(input_pdf) as source:
        page_indexes = _page_order_to_zero_based(page_order, len(source.pages))
        reordered = pikepdf.Pdf.new()
        try:
            reordered.add_pages_from(source, pages=page_indexes, forms="preserve")
            _preserve_optional_content_defaults(reordered, source, range(len(reordered.pages)))
            _save_pdf_to_new_output(reordered, output, (input_pdf,))
            return output
        finally:
            reordered.close()


def insert_pdf_pages(
    primary_path: Path,
    inserted_path: Path,
    output_path: Path,
    page_numbers: Sequence[int],
    insert_after_page: int,
) -> Path:
    primary_pdf = Path(primary_path)
    inserted_pdf = Path(inserted_path)
    requested_output = Path(output_path)
    inputs = (primary_pdf, inserted_pdf)
    validate_pdf_inputs(inputs, minimum_count=2)
    if primary_pdf.resolve(strict=False) == inserted_pdf.resolve(strict=False):
        raise InvalidPdfError()
    output = prepare_pdf_output_path(requested_output, inputs)

    with _open_pdf(primary_pdf) as primary, _open_pdf(inserted_pdf) as inserted:
        if (
            not _is_strict_int(insert_after_page)
            or insert_after_page < 0
            or insert_after_page > len(primary.pages)
        ):
            raise InvalidPageSelectionError()
        inserted_indexes = _page_numbers_to_zero_based(page_numbers, len(inserted.pages))
        combined = pikepdf.Pdf.new()
        try:
            if insert_after_page:
                combined.add_pages_from(
                    primary,
                    pages=range(insert_after_page),
                    forms="preserve",
                )
                _preserve_optional_content_defaults(
                    combined,
                    primary,
                    range(insert_after_page),
                )

            inserted_start = len(combined.pages)
            combined.add_pages_from(inserted, pages=inserted_indexes, forms="preserve")
            _preserve_optional_content_defaults(
                combined,
                inserted,
                range(inserted_start, len(combined.pages)),
            )

            if insert_after_page < len(primary.pages):
                primary_suffix_start = len(combined.pages)
                combined.add_pages_from(
                    primary,
                    pages=range(insert_after_page, len(primary.pages)),
                    forms="preserve",
                )
                _preserve_optional_content_defaults(
                    combined,
                    primary,
                    range(primary_suffix_start, len(combined.pages)),
                )

            _save_pdf_to_new_output(combined, output, inputs)
            return output
        finally:
            combined.close()


def insert_blank_page(
    input_path: Path,
    output_path: Path,
    width_mm: float,
    height_mm: float,
    insert_after_page: int,
) -> Path:
    input_pdf = Path(input_path)
    validate_pdf_inputs((input_pdf,), minimum_count=1)
    output = prepare_pdf_output_path(Path(output_path), (input_pdf,))
    width_points = millimetres_to_points(validate_page_dimension_mm(width_mm, "width_mm"))
    height_points = millimetres_to_points(validate_page_dimension_mm(height_mm, "height_mm"))
    with _open_pdf(input_pdf) as source:
        if not _is_strict_int(insert_after_page) or not 0 <= insert_after_page <= len(source.pages):
            raise InvalidPageSelectionError()
        combined = pikepdf.Pdf.new()
        try:
            if insert_after_page:
                combined.add_pages_from(source, pages=range(insert_after_page), forms="preserve")
                _preserve_optional_content_defaults(combined, source, range(insert_after_page))
            combined.add_blank_page(page_size=(width_points, height_points))
            if insert_after_page < len(source.pages):
                suffix_start = len(combined.pages)
                combined.add_pages_from(
                    source, pages=range(insert_after_page, len(source.pages)), forms="preserve"
                )
                _preserve_optional_content_defaults(
                    combined, source, range(suffix_start, len(combined.pages))
                )
            _save_pdf_to_new_output(combined, output, (input_pdf,))
            return output
        finally:
            combined.close()


def _preserve_optional_content_defaults(
    destination: pikepdf.Pdf,
    source: pikepdf.Pdf,
    destination_page_indexes: Sequence[int] | range,
) -> None:
    """Keep the source's default layer visibility after pages are copied.

    ``Pdf.add_pages_from`` copies page resources, including optional-content
    groups, but not the catalog-level ``/OCProperties`` configuration. Merely
    copying that catalog dictionary would create a second set of OCG objects,
    so its ``/OFF`` entries would not control the layers referenced by the
    copied pages. Rebuild a normalized destination configuration with the OCG
    objects that are actually reachable from those pages.
    """
    source_properties = source.Root.get("/OCProperties")
    if not _is_pdf_dictionary(source_properties):
        return
    source_groups = tuple(source_properties.get("/OCGs", ()) or ())
    if not source_groups:
        return

    copied_groups: list[pikepdf.Object] = []
    for page_index in destination_page_indexes:
        copied_groups.extend(_page_optional_content_groups(destination.pages[page_index]))
    copied_groups = _unique_pdf_objects(copied_groups)
    mapped_groups = _match_optional_content_groups(source_groups, copied_groups)
    if not mapped_groups:
        return

    existing_properties = destination.Root.get("/OCProperties")
    existing_groups: list[pikepdf.Object] = []
    existing_off: list[pikepdf.Object] = []
    if _is_pdf_dictionary(existing_properties):
        existing_groups = list(existing_properties.get("/OCGs", ()) or ())
        default_configuration = existing_properties.get("/D")
        if _is_pdf_dictionary(default_configuration):
            existing_off = list(default_configuration.get("/OFF", ()) or ())

    source_default = source_properties.get("/D")
    source_off = _source_groups_hidden_by_default(source_groups, source_default)
    mapped_off = [
        destination_group
        for source_group, destination_group in mapped_groups
        if _contains_pdf_object(source_off, source_group)
    ]
    all_groups = _unique_pdf_objects([*existing_groups, *(group for _, group in mapped_groups)])
    all_off = _unique_pdf_objects([*existing_off, *mapped_off])
    destination.Root["/OCProperties"] = pikepdf.Dictionary(
        OCGs=pikepdf.Array(all_groups),
        D=pikepdf.Dictionary(
            BaseState=pikepdf.Name.ON,
            Order=pikepdf.Array(all_groups),
            OFF=pikepdf.Array(all_off),
        ),
    )


def _source_groups_hidden_by_default(
    groups: Sequence[pikepdf.Object], default_configuration: object
) -> list[pikepdf.Object]:
    if not _is_pdf_dictionary(default_configuration):
        return []
    base_state = str(default_configuration.get("/BaseState", "/ON"))
    explicitly_on = list(default_configuration.get("/ON", ()) or ())
    explicitly_off = list(default_configuration.get("/OFF", ()) or ())
    hidden: list[pikepdf.Object] = []
    for group in groups:
        is_visible = base_state != "/OFF"
        if _contains_pdf_object(explicitly_on, group):
            is_visible = True
        if _contains_pdf_object(explicitly_off, group):
            is_visible = False
        if not is_visible:
            hidden.append(group)
    return hidden


def _match_optional_content_groups(
    source_groups: Sequence[pikepdf.Object], copied_groups: Sequence[pikepdf.Object]
) -> list[tuple[pikepdf.Object, pikepdf.Object]]:
    remaining = list(copied_groups)
    matched: list[tuple[pikepdf.Object, pikepdf.Object]] = []
    for source_group in source_groups:
        signature = _optional_content_group_signature(source_group)
        match_index = next(
            (
                index
                for index, copied_group in enumerate(remaining)
                if _optional_content_group_signature(copied_group) == signature
            ),
            None,
        )
        if match_index is not None:
            matched.append((source_group, remaining.pop(match_index)))
    return matched


def _optional_content_group_signature(group: pikepdf.Object) -> tuple[str, str]:
    return str(group.get("/Name", "")), str(group.get("/Intent", "/View"))


def _page_optional_content_groups(page: pikepdf.Page) -> list[pikepdf.Object]:
    groups: list[pikepdf.Object] = []
    seen: set[tuple[int, int]] = set()

    def visit(value: object) -> None:
        if isinstance(value, pikepdf.Array):
            for item in value:
                visit(item)
            return
        if not _is_pdf_dictionary(value):
            return
        # Direct-object wrappers are short-lived and Python may reuse their
        # ``id`` while walking the tree. Only indirect objects have a stable
        # identity suitable for cycle detection.
        if value.objgen != (0, 0):
            if value.objgen in seen:
                return
            seen.add(value.objgen)
        if str(value.get("/Type", "")) == "/OCG":
            groups.append(value)
            return
        for key, child in value.items():
            if str(key) not in {"/Parent", "/P", "/Contents"}:
                visit(child)

    for key in ("/Resources", "/Annots", "/OC"):
        visit(page.obj.get(key))
    return _unique_pdf_objects(groups)


def _is_pdf_dictionary(
    value: object,
) -> TypeGuard[pikepdf.Dictionary | pikepdf.Stream]:
    return isinstance(value, (pikepdf.Dictionary, pikepdf.Stream))


def _unique_pdf_objects(objects: Sequence[pikepdf.Object]) -> list[pikepdf.Object]:
    unique: list[pikepdf.Object] = []
    identities: set[tuple[int, int] | int] = set()
    for item in objects:
        identity = _pdf_object_identity(item)
        if identity not in identities:
            identities.add(identity)
            unique.append(item)
    return unique


def _contains_pdf_object(objects: Sequence[pikepdf.Object], expected: pikepdf.Object) -> bool:
    identity = _pdf_object_identity(expected)
    return any(_pdf_object_identity(item) == identity for item in objects)


def _pdf_object_identity(value: pikepdf.Object) -> tuple[int, int] | int:
    return value.objgen if value.objgen != (0, 0) else id(value)


def _run_merge_job(job: JobRequest, started: float) -> JobResult:
    options = job.require_options(MergeOptions)
    output_path = _output_path_from_options(job, options.output_path, "fusion.pdf")
    output_path = merge_pdfs(job.input_files, output_path)
    return _success_result(
        started,
        (output_path,),
        f"PDF fusionne cree : {output_path.name}",
    )


def _run_extract_job(job: JobRequest, started: float) -> JobResult:
    options = job.require_options(ExtractOptions)
    input_path = _single_input(job)
    output_path = _output_path_from_options(job, options.output_path, "extraction.pdf")
    output_path = extract_pages(input_path, output_path, options.page_numbers)
    return _success_result(
        started,
        (output_path,),
        f"PDF extrait cree : {output_path.name}",
    )


def _run_remove_job(job: JobRequest, started: float) -> JobResult:
    options = job.require_options(RemoveOptions)
    input_path = _single_input(job)
    output_path = _output_path_from_options(job, options.output_path, "pages_supprimees.pdf")
    output_path = remove_pages(input_path, output_path, options.page_numbers)
    return _success_result(
        started,
        (output_path,),
        f"PDF sans les pages demandees cree : {output_path.name}",
    )


def _run_split_job(job: JobRequest, started: float) -> JobResult:
    options = job.require_options(SplitOptions)
    input_path = _single_input(job)
    if options.page_groups is not None:
        output_files = split_pdf_by_page_groups(
            input_path,
            job.output_dir,
            options.page_groups,
            base_name=options.base_name,
        )
        return _success_result(
            started,
            output_files,
            f"Division terminee : {len(output_files)} fichier(s) cree(s).",
        )

    if options.ranges is None:
        raise InvalidSplitPlanError()
    output_files = split_pdf_by_ranges(
        input_path,
        job.output_dir,
        options.ranges,
        base_name=options.base_name,
    )
    return _success_result(
        started,
        output_files,
        f"Division terminee : {len(output_files)} fichier(s) cree(s).",
    )


def _run_rotate_job(job: JobRequest, started: float) -> JobResult:
    options = job.require_options(RotateOptions)
    input_path = _single_input(job)
    output_path = _output_path_from_options(job, options.output_path, "pages_tournees.pdf")
    output_path = rotate_pages(input_path, output_path, options.page_numbers, options.angle)
    return _success_result(
        started,
        (output_path,),
        f"PDF avec pages tournees cree : {output_path.name}",
    )


def _run_reorder_job(job: JobRequest, started: float) -> JobResult:
    options = job.require_options(ReorderOptions)
    input_path = _single_input(job)
    output_path = _output_path_from_options(job, options.output_path, "pages_reorganisees.pdf")
    output_path = reorder_pages(input_path, output_path, options.page_order)
    return _success_result(
        started,
        (output_path,),
        f"PDF reorganise cree : {output_path.name}",
    )


def _run_insert_pages_job(job: JobRequest, started: float) -> JobResult:
    options = job.require_options(InsertPagesOptions)
    output_path = _output_path_from_options(job, options.output_path, "pages_inserees.pdf")
    output_path = insert_pdf_pages(
        job.input_files[0],
        job.input_files[1],
        output_path,
        options.page_numbers,
        options.insert_after_page,
    )
    return _success_result(
        started,
        (output_path,),
        f"PDF avec pages inserees cree : {output_path.name}",
    )


def _run_insert_blank_page_job(job: JobRequest, started: float) -> JobResult:
    options = job.require_options(InsertBlankPageOptions)
    output_path = _output_path_from_options(job, options.output_path, "avec_page_blanche.pdf")
    output_path = insert_blank_page(
        _single_input(job),
        output_path,
        options.width_mm,
        options.height_mm,
        options.insert_after_page,
    )
    return _success_result(
        started, (output_path,), f"PDF avec page blanche cree : {output_path.name}"
    )


_STRUCTURAL_JOB_HANDLERS: Mapping[OperationType, _StructuralJobHandler] = {
    OperationType.MERGE_PDFS: _run_merge_job,
    OperationType.EXTRACT_PAGES: _run_extract_job,
    OperationType.REMOVE_PAGES: _run_remove_job,
    OperationType.SPLIT_BY_RANGES: _run_split_job,
    OperationType.ROTATE_PAGES: _run_rotate_job,
    OperationType.REORDER_PAGES: _run_reorder_job,
    OperationType.INSERT_PDF_PAGES: _run_insert_pages_job,
    OperationType.INSERT_BLANK_PAGE: _run_insert_blank_page_job,
}


def _single_input(job: JobRequest) -> Path:
    if len(job.input_files) != 1:
        raise InvalidPdfError()
    return job.input_files[0]


def _output_path_from_options(
    job: JobRequest,
    output_path: Path | None,
    default_name: str,
) -> Path:
    requested = output_path or job.output_dir / default_name
    return prepare_pdf_output_path(
        requested,
        job.input_files,
        allowed_dir=job.output_dir,
    )


def _page_numbers_to_zero_based(page_numbers: Sequence[int], page_count: int) -> tuple[int, ...]:
    pages = tuple(page_numbers)
    try:
        validate_page_numbers(pages, page_count)
    except ValueError as exc:
        raise InvalidPageSelectionError() from exc
    return tuple(page_number - 1 for page_number in pages)


def _page_order_to_zero_based(page_order: Sequence[int], page_count: int) -> tuple[int, ...]:
    pages = tuple(page_order)
    try:
        validate_page_assembly(pages, page_count)
    except ValueError as exc:
        raise InvalidPageOrderError() from exc
    return tuple(page_number - 1 for page_number in pages)


def _validate_rotation_angle(angle: int) -> None:
    if not _is_strict_int(angle) or angle not in {0, 90, 180, 270}:
        raise InvalidPdfError()


def _is_strict_int(value: object) -> TypeGuard[int]:
    return isinstance(value, int) and not isinstance(value, bool)


def _open_pdf(input_path: Path) -> pikepdf.Pdf:
    validate_pdf_inputs((input_path,), minimum_count=1)
    try:
        pdf = pikepdf.open(input_path)
    except pikepdf.PasswordError as exc:
        raise EncryptedPdfError() from exc
    except pikepdf.PdfError as exc:
        raise InvalidPdfError() from exc
    except OSError as exc:
        raise InputPathError() from exc

    if pdf.is_encrypted:
        pdf.close()
        raise EncryptedPdfError()
    return pdf


def _save_pdf_to_new_output(
    pdf: pikepdf.Pdf, output_path: Path, input_paths: tuple[Path, ...]
) -> None:
    def write_pdf(stream: BinaryIO) -> None:
        pdf.save(stream)

    try:
        published = atomic_write_no_replace_tracked(
            output_path,
            write_pdf,
            input_paths,
            required_suffix=".pdf",
        )
        published.close()
    except OutputWriteError:
        raise
    except Exception:
        raise OutputWriteError() from None


def _save_pdf_to_new_output_tracked(
    pdf: pikepdf.Pdf,
    output_path: Path,
    input_paths: tuple[Path, ...],
) -> PublishedOutput:
    def write_pdf(stream: BinaryIO) -> None:
        pdf.save(stream)

    try:
        return atomic_write_no_replace_tracked(
            output_path,
            write_pdf,
            input_paths,
            required_suffix=".pdf",
        )
    except OutputWriteError:
        raise
    except Exception:
        raise OutputWriteError() from None


def _validate_output_dir(output_dir: Path) -> None:
    if not output_dir.exists() or not output_dir.is_dir():
        raise OutputWriteError()


def _cleanup_created_outputs(created: Sequence[PublishedOutput]) -> None:
    for output in reversed(created):
        try:
            if output.matches_current_entry():
                output.path.unlink(missing_ok=True)
        except OSError:
            pass
        finally:
            output.close()


def _close_published_outputs(created: Sequence[PublishedOutput]) -> None:
    for output in created:
        output.close()


def _success_result(started: float, output_files: tuple[Path, ...], message: str) -> JobResult:
    duration_ms = int((time.monotonic() - started) * 1000)
    return JobResult(
        success=True,
        output_files=output_files,
        warnings=(),
        user_message=message,
        duration_ms=duration_ms,
    )


def _error_result(error: PdfModError, started: float) -> JobResult:
    duration_ms = int((time.monotonic() - started) * 1000)
    return JobResult(
        success=False,
        output_files=(),
        warnings=(),
        user_message=error.user_message,
        technical_detail=error.technical_detail or error.technical_code,
        duration_ms=duration_ms,
    )
