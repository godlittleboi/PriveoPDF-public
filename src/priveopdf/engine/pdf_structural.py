from __future__ import annotations

import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import BinaryIO, TypeGuard

import pikepdf

from priveopdf.domain.errors import (
    EncryptedPdfError,
    InputPathError,
    InternalPdfEngineError,
    InvalidPageOrderError,
    InvalidPageSelectionError,
    InvalidPdfError,
    InvalidSplitPlanError,
    OutputWriteError,
    PdfModError,
    PdfStructureTooComplexError,
)
from priveopdf.domain.jobs import (
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
from priveopdf.domain.page_plans import split_group_file_names, split_range_file_names
from priveopdf.domain.page_ranges import (
    PageRange,
    validate_page_assembly,
    validate_page_numbers,
    validate_page_ranges,
)
from priveopdf.domain.paper_sizes import millimetres_to_points, validate_page_dimension_mm
from priveopdf.engine.pdf_compression import has_digital_signature, run_compression_job
from priveopdf.engine.pdf_ocr import run_ocr_job
from priveopdf.engine.pdf_password import run_password_job
from priveopdf.engine.pdf_share import run_share_job
from priveopdf.utils.secure_paths import (
    PublishedOutput,
    atomic_write_no_replace_tracked,
    build_confined_destination,
    portable_filename_stem,
)
from priveopdf.utils.validation import (
    prepare_pdf_output_path,
    validate_pdf_inputs,
    validate_pdf_output_path,
)

type _StructuralJobHandler = Callable[[JobRequest, float], JobResult]


def run_structural_job(
    job: JobRequest, progress: Callable[[int, int], None] = lambda *_: None
) -> JobResult:
    started = time.monotonic()
    try:
        if job.operation in {
            OperationType.REMOVE_METADATA,
            OperationType.PHOTOCOPY_PDF,
            OperationType.REDACT_PDF,
            OperationType.WATERMARK_PDF,
        }:
            return run_share_job(job, started, progress)
        if job.operation is OperationType.OCR_PDF:
            return run_ocr_job(job, started, progress)
        handler = _STRUCTURAL_JOB_HANDLERS.get(job.operation)
        if handler is None:
            raise PdfModError("Unsupported operation")
        return handler(job, started)
    except PdfModError as exc:
        return _error_result(exc, started)
    except Exception as exc:
        error = InternalPdfEngineError(
            technical_detail=f"{InternalPdfEngineError.technical_code}:{type(exc).__name__.lower()}"
        )
        return _error_result(error, started)


def get_page_count(pdf_path: Path) -> int:
    return page_summary(pdf_path)[0]


def page_summary(pdf_path: Path) -> tuple[int, bool]:
    """Page count and whether the PDF carries a digital signature (one opening)."""

    with _open_pdf(Path(pdf_path)) as pdf:
        if not len(pdf.pages):
            # No tool can act on it; the protocol counts from one.
            raise InvalidPdfError()
        return len(pdf.pages), has_digital_signature(pdf)


def merge_pdfs(input_paths: tuple[Path, ...] | list[Path], output_path: Path) -> Path:
    inputs = tuple(Path(path) for path in input_paths)
    requested_output = Path(output_path)
    validate_pdf_inputs(inputs, minimum_count=2)
    output = prepare_pdf_output_path(requested_output, inputs)

    merged = pikepdf.Pdf.new()
    walk = _ResourceWalk()
    try:
        for input_path in inputs:
            with _open_pdf(input_path) as source:
                _copy_pages(merged, source, range(len(source.pages)), walk)
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
            _copy_pages(extracted, source, page_indexes, _ResourceWalk())
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
            _copy_pages(reduced, source, remaining_indexes, _ResourceWalk())
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

        file_names = split_range_file_names(
            base_name if base_name else portable_filename_stem(input_pdf.stem),
            tuple(page_range.label for page_range in page_ranges),
        )
        output_paths = tuple(
            build_confined_destination(destination_dir, file_name, required_suffix=".pdf")
            for file_name in file_names
        )
        if len(set(output_paths)) != len(output_paths):
            raise OutputWriteError()
        for output_path in output_paths:
            validate_pdf_output_path(output_path, (input_pdf,))

        created: list[PublishedOutput] = []
        try:
            walk = _ResourceWalk()
            for page_range, output_path in zip(page_ranges, output_paths, strict=True):
                split_pdf = pikepdf.Pdf.new()
                try:
                    _copy_pages(
                        split_pdf,
                        source,
                        tuple(page_number - 1 for page_number in page_range.pages),
                        walk,
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

        file_names = split_group_file_names(
            base_name if base_name else portable_filename_stem(input_pdf.stem), len(groups)
        )
        output_paths = tuple(
            build_confined_destination(destination_dir, file_name, required_suffix=".pdf")
            for file_name in file_names
        )
        if len(set(output_paths)) != len(output_paths):
            raise OutputWriteError()
        for output_path in output_paths:
            validate_pdf_output_path(output_path, (input_pdf,))

        created: list[PublishedOutput] = []
        try:
            walk = _ResourceWalk()
            for group, output_path in zip(groups, output_paths, strict=True):
                split_pdf = pikepdf.Pdf.new()
                try:
                    _copy_pages(
                        split_pdf, source, tuple(page_number - 1 for page_number in group), walk
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
            for page_index in dict.fromkeys(page_indexes):
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
            _copy_pages(reordered, source, page_indexes, _ResourceWalk())
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
        walk = _ResourceWalk()
        try:
            if insert_after_page:
                _copy_pages(combined, primary, range(insert_after_page), walk)
            _copy_pages(combined, inserted, inserted_indexes, walk)
            if insert_after_page < len(primary.pages):
                _copy_pages(combined, primary, range(insert_after_page, len(primary.pages)), walk)

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
        walk = _ResourceWalk()
        try:
            if insert_after_page:
                _copy_pages(combined, source, range(insert_after_page), walk)
            combined.add_blank_page(page_size=(width_points, height_points))
            if insert_after_page < len(source.pages):
                _copy_pages(combined, source, range(insert_after_page, len(source.pages)), walk)
            _save_pdf_to_new_output(combined, output, (input_pdf,))
            return output
        finally:
            combined.close()


class _ResourceWalk:
    """Remaining budgets of one operation's resource walks (F07).

    One instance per operation, shared by every `_copy_pages` call of it
    (merge of several inputs, insertion in two segments, every output of a
    split): the budgets bound the whole operation. Visited objects are
    remembered per call, because object numbers belong to one document. The
    layer catalog of each source is read once per operation.
    """

    def __init__(self) -> None:
        self.budget = OPTIONAL_CONTENT_WALK_BUDGET
        self.entries = OPTIONAL_CONTENT_ENTRY_BUDGET
        # Keyed by ``id`` but holding the source: an ``id`` is only unique while
        # its object lives, and a merge releases each input before the next
        # (Codex review of CA1).
        self.catalogs: dict[int, tuple[pikepdf.Pdf, _LayerCatalog | None]] = {}

    def spend(self, containers: int, entries: int) -> None:
        self.budget -= containers
        self.entries -= entries
        if self.budget < 0 or self.entries < 0:
            raise PdfStructureTooComplexError()

    def catalog(self, source: pikepdf.Pdf) -> _LayerCatalog | None:
        cached = self.catalogs.get(id(source))
        if cached is None or cached[0] is not source:
            cached = (source, _read_layer_catalog(source, self))
            self.catalogs[id(source)] = cached
        return cached[1]


class _LayerCatalog:
    """Groups listed in a source's catalog and those hidden by default."""

    def __init__(self, listed: set[tuple[int, int]], hidden: set[tuple[int, int]]) -> None:
        self.listed = listed
        self.hidden = hidden


def _read_layer_catalog(source: pikepdf.Pdf, walk: _ResourceWalk) -> _LayerCatalog | None:
    properties = source.Root.get("/OCProperties")
    if not _is_pdf_dictionary(properties):
        return None
    groups = properties.get("/OCGs", ())
    if not isinstance(groups, pikepdf.Array) or not len(groups):
        return None
    default_configuration = properties.get("/D")
    on_array: object = None
    off_array: object = None
    base_state = "/ON"
    if _is_pdf_dictionary(default_configuration):
        base_state = str(default_configuration.get("/BaseState", "/ON"))
        on_array = default_configuration.get("/ON")
        off_array = default_configuration.get("/OFF")
    # Charged before any list is built (Codex review of CA1).
    walk.spend(1, len(groups) + _array_length(on_array) + _array_length(off_array))
    on = _array_items(on_array)
    off = _array_items(off_array)
    listed = {
        group.objgen for group in groups if _is_pdf_dictionary(group) and group.objgen != (0, 0)
    }
    explicitly_on = {item.objgen for item in on}
    explicitly_off = {item.objgen for item in off}
    hidden = {
        identity
        for identity in listed
        if identity in explicitly_off or (base_state == "/OFF" and identity not in explicitly_on)
    }
    return _LayerCatalog(listed, hidden)


def _array_length(value: object) -> int:
    return len(value) if isinstance(value, pikepdf.Array) else 0


def _array_items(value: object) -> list[pikepdf.Object]:
    return list(value) if isinstance(value, pikepdf.Array) else []


def _copy_pages(
    destination: pikepdf.Pdf,
    source: pikepdf.Pdf,
    page_indexes: Sequence[int] | range,
    walk: _ResourceWalk,
) -> None:
    """Append source pages to ``destination`` and keep their layer visibility.

    The layers are looked for before the copy, so a resource graph beyond the
    budget is refused before QPDF imports it (Codex review of CA1).
    """

    indexes = tuple(page_indexes)
    catalog = walk.catalog(source)
    reachable: list[pikepdf.Object] = []
    if catalog is not None:
        seen: set[tuple[int, int]] = set()
        for page_index in indexes:
            reachable.extend(_page_optional_content_groups(source.pages[page_index], walk, seen))
    destination.add_pages_from(source, pages=indexes, forms="preserve")
    if catalog is not None:
        _preserve_optional_content_defaults(destination, catalog, reachable)


def _preserve_optional_content_defaults(
    destination: pikepdf.Pdf,
    catalog: _LayerCatalog,
    reachable: Sequence[pikepdf.Object],
) -> None:
    """Keep the source's default layer visibility after pages are copied.

    ``Pdf.add_pages_from`` copies page resources, including optional-content
    groups, but not the catalog-level ``/OCProperties`` configuration. Merely
    copying that catalog dictionary would create a second set of OCG objects,
    so its ``/OFF`` entries would not control the layers referenced by the
    copied pages. Rebuild a normalized destination configuration with the
    groups reachable from the copied source pages, paired with their copies.
    """
    # Only groups the copied pages reach are passed to ``copy_foreign``: QPDF
    # returns the copy ``add_pages_from`` already made, so the pairing follows
    # the object, not its name (F18), and a catalog listing many groups no
    # copied page uses copies nothing (review of CA1).
    mapped_groups = [
        (group, destination.copy_foreign(group))
        for group in _unique_pdf_objects(reachable)
        if group.objgen in catalog.listed
    ]
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

    mapped_off = [
        destination_group
        for source_group, destination_group in mapped_groups
        if source_group.objgen in catalog.hidden
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


# Containers (dictionaries, streams, arrays) visited while looking for the
# groups of one operation's pages, about 90 µs each: beyond that, the PDF is
# refused rather than guessed about (F07). 500 000 is about 250 pages of a
# dense CAD profile (50 layers, 1 000 form XObjects per page), well under the
# worker's delay.
OPTIONAL_CONTENT_WALK_BUDGET = 500_000
# Entries read in those containers and in the layer catalog: a single huge
# array costs one container but millions of entries (review of CA1). Measured
# from 0.7 µs (direct numbers) to 9 µs (indirect groups of the catalog) each:
# 3 000 000 stays under 30 s, a quarter of the worker's delay.
OPTIONAL_CONTENT_ENTRY_BUDGET = 3_000_000
_PAGE_TREE_TYPES = frozenset({"/Page", "/Pages"})


def _page_optional_content_groups(
    page: pikepdf.Page, walk: _ResourceWalk, seen: set[tuple[int, int]]
) -> list[pikepdf.Object]:
    """Groups reachable from the page, found without recursion (F07).

    ``seen`` is shared by the pages of one copy, so shared resources are
    walked once; ``walk`` carries the budget of the whole operation. Arrays
    count and are remembered like dictionaries: a cycle through an indirect
    array ends.
    """

    groups: list[pikepdf.Object] = []
    stack: list[object] = [page.obj.get(key) for key in ("/OC", "/Annots", "/Resources")]
    while stack:
        value = stack.pop()
        if not isinstance(value, pikepdf.Array) and not _is_pdf_dictionary(value):
            continue
        # Direct-object wrappers are short-lived and Python may reuse their
        # ``id`` while walking the tree. Only indirect objects have a stable
        # identity suitable for cycle detection.
        if value.objgen != (0, 0):
            if value.objgen in seen:
                continue
            seen.add(value.objgen)
        walk.spend(1, len(value) if isinstance(value, pikepdf.Array) else len(value.keys()))
        if isinstance(value, pikepdf.Array):
            stack.extend(reversed(list(value)))
            continue
        value_type = value.get("/Type")
        if str(value_type) == "/OCG":
            groups.append(value)
            continue
        # Pages and the page tree (reached through /P or /Parent) are not walked,
        # as QPDF recognises them: a dictionary whose /Type is the name /Page or
        # /Pages. A stream, a /Type string or a resource named /P still is.
        if (
            isinstance(value, pikepdf.Dictionary)
            and isinstance(value_type, pikepdf.Name)
            and str(value_type) in _PAGE_TREE_TYPES
        ):
            continue
        stack.extend(child for _key, child in reversed(list(value.items())))
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
    OperationType.REMOVE_METADATA: run_share_job,
    OperationType.PHOTOCOPY_PDF: run_share_job,
    OperationType.REDACT_PDF: run_share_job,
    OperationType.WATERMARK_PDF: run_share_job,
    OperationType.OCR_PDF: run_ocr_job,
    OperationType.PROTECT_PDF: run_password_job,
    OperationType.UNLOCK_PDF: run_password_job,
    OperationType.COMPRESS_PDF: run_compression_job,
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
    # Opened without a password: an empty user password only carries usage
    # restrictions, which the copy written by `save` no longer has (issue 446).
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
