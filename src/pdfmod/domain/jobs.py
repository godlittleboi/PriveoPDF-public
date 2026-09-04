from __future__ import annotations

import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Literal, cast

from pdfmod.domain.page_ranges import PageRange
from pdfmod.domain.paper_sizes import validate_page_dimension_mm

MAX_OPTION_SEQUENCE_ITEMS = 100_000
MAX_PAGE_NUMBER = 10_000_000
MAX_BASE_NAME_CHARS = 255


class OperationType(StrEnum):
    MERGE_PDFS = "merge_pdfs"
    EXTRACT_PAGES = "extract_pages"
    REMOVE_PAGES = "remove_pages"
    SPLIT_BY_RANGES = "split_by_ranges"
    ROTATE_PAGES = "rotate_pages"
    REORDER_PAGES = "reorder_pages"
    INSERT_PDF_PAGES = "insert_pdf_pages"
    INSERT_BLANK_PAGE = "insert_blank_page"


type NamingStrategy = Literal["explicit"]


class _OptionsMapping(Mapping[str, object]):
    operation: OperationType

    def as_dict(self) -> dict[str, object]:
        return {
            field_name: value
            for field_name, value in vars(self).items()
            if field_name != "operation" and value is not None
        }

    def __getitem__(self, key: str) -> object:
        try:
            return self.as_dict()[key]
        except KeyError:
            raise KeyError(key) from None

    def __iter__(self) -> Iterator[str]:
        return iter(self.as_dict())

    def __len__(self) -> int:
        return len(self.as_dict())

    def __eq__(self, other: object) -> bool:
        if isinstance(other, _OptionsMapping) and self.operation is not other.operation:
            return False
        if not isinstance(other, Mapping):
            return False
        return self.as_dict() == dict(other.items())


@dataclass(frozen=True, eq=False)
class MergeOptions(_OptionsMapping):
    output_path: Path | None = None
    operation: Literal[OperationType.MERGE_PDFS] = field(
        default=OperationType.MERGE_PDFS,
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        _validate_optional_output_path(self.output_path)


@dataclass(frozen=True, eq=False)
class ExtractOptions(_OptionsMapping):
    page_numbers: tuple[int, ...]
    output_path: Path | None = None
    operation: Literal[OperationType.EXTRACT_PAGES] = field(
        default=OperationType.EXTRACT_PAGES,
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        _validate_page_sequence(self.page_numbers, "page_numbers")
        _validate_optional_output_path(self.output_path)


@dataclass(frozen=True, eq=False)
class RemoveOptions(_OptionsMapping):
    page_numbers: tuple[int, ...]
    output_path: Path | None = None
    operation: Literal[OperationType.REMOVE_PAGES] = field(
        default=OperationType.REMOVE_PAGES,
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        _validate_page_sequence(self.page_numbers, "page_numbers")
        _validate_optional_output_path(self.output_path)


@dataclass(frozen=True, eq=False)
class SplitOptions(_OptionsMapping):
    ranges: tuple[PageRange, ...] | None = None
    page_groups: tuple[tuple[int, ...], ...] | None = None
    base_name: str | None = None
    operation: Literal[OperationType.SPLIT_BY_RANGES] = field(
        default=OperationType.SPLIT_BY_RANGES,
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        if (self.ranges is None) == (self.page_groups is None):
            raise ValueError("split options require exactly one split plan")
        if self.ranges is not None:
            _validate_page_ranges(self.ranges)
        if self.page_groups is not None:
            _validate_page_groups(self.page_groups)
        if self.base_name is not None:
            if not isinstance(self.base_name, str):
                raise TypeError("base_name must be a string or None")
            if (
                not self.base_name
                or self.base_name != self.base_name.strip()
                or len(self.base_name) > MAX_BASE_NAME_CHARS
            ):
                raise ValueError("base_name must be a bounded non-empty string")


@dataclass(frozen=True, eq=False)
class RotateOptions(_OptionsMapping):
    page_numbers: tuple[int, ...]
    angle: int
    output_path: Path | None = None
    operation: Literal[OperationType.ROTATE_PAGES] = field(
        default=OperationType.ROTATE_PAGES,
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        _validate_page_sequence(self.page_numbers, "page_numbers")
        if not _is_strict_int(self.angle) or self.angle not in {0, 90, 180, 270}:
            raise ValueError("angle must be 0, 90, 180 or 270")
        _validate_optional_output_path(self.output_path)


@dataclass(frozen=True, eq=False)
class ReorderOptions(_OptionsMapping):
    page_order: tuple[int, ...]
    output_path: Path | None = None
    operation: Literal[OperationType.REORDER_PAGES] = field(
        default=OperationType.REORDER_PAGES,
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        _validate_page_sequence(self.page_order, "page_order")
        _validate_optional_output_path(self.output_path)


@dataclass(frozen=True, eq=False)
class InsertPagesOptions(_OptionsMapping):
    page_numbers: tuple[int, ...]
    insert_after_page: int
    output_path: Path | None = None
    operation: Literal[OperationType.INSERT_PDF_PAGES] = field(
        default=OperationType.INSERT_PDF_PAGES,
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        _validate_page_sequence(self.page_numbers, "page_numbers")
        if (
            not _is_strict_int(self.insert_after_page)
            or self.insert_after_page < 0
            or self.insert_after_page > MAX_PAGE_NUMBER
        ):
            raise ValueError("insert_after_page must be a bounded positive or zero integer")
        _validate_optional_output_path(self.output_path)


@dataclass(frozen=True, eq=False)
class InsertBlankPageOptions(_OptionsMapping):
    width_mm: float
    height_mm: float
    insert_after_page: int
    output_path: Path | None = None
    operation: Literal[OperationType.INSERT_BLANK_PAGE] = field(
        default=OperationType.INSERT_BLANK_PAGE, init=False, repr=False
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "width_mm", validate_page_dimension_mm(self.width_mm, "width_mm"))
        object.__setattr__(
            self, "height_mm", validate_page_dimension_mm(self.height_mm, "height_mm")
        )
        if (
            not _is_strict_int(self.insert_after_page)
            or not 0 <= self.insert_after_page <= MAX_PAGE_NUMBER
        ):
            raise ValueError("insert_after_page must be a bounded positive or zero integer")
        _validate_optional_output_path(self.output_path)


type OperationOptions = (
    MergeOptions
    | ExtractOptions
    | RemoveOptions
    | SplitOptions
    | RotateOptions
    | ReorderOptions
    | InsertPagesOptions
    | InsertBlankPageOptions
)
type JobOptions = OperationOptions | Mapping[str, object]

_OPTION_TYPES: Mapping[OperationType, type[_OptionsMapping]] = {
    OperationType.MERGE_PDFS: MergeOptions,
    OperationType.EXTRACT_PAGES: ExtractOptions,
    OperationType.REMOVE_PAGES: RemoveOptions,
    OperationType.SPLIT_BY_RANGES: SplitOptions,
    OperationType.ROTATE_PAGES: RotateOptions,
    OperationType.REORDER_PAGES: ReorderOptions,
    OperationType.INSERT_PDF_PAGES: InsertPagesOptions,
    OperationType.INSERT_BLANK_PAGE: InsertBlankPageOptions,
}
_OPTION_KEYS: Mapping[OperationType, frozenset[str]] = {
    OperationType.MERGE_PDFS: frozenset({"output_path"}),
    OperationType.EXTRACT_PAGES: frozenset({"output_path", "page_numbers"}),
    OperationType.REMOVE_PAGES: frozenset({"output_path", "page_numbers"}),
    OperationType.SPLIT_BY_RANGES: frozenset({"ranges", "page_groups", "base_name"}),
    OperationType.ROTATE_PAGES: frozenset({"output_path", "page_numbers", "angle"}),
    OperationType.REORDER_PAGES: frozenset({"output_path", "page_order"}),
    OperationType.INSERT_PDF_PAGES: frozenset({"output_path", "page_numbers", "insert_after_page"}),
    OperationType.INSERT_BLANK_PAGE: frozenset(
        {"output_path", "width_mm", "height_mm", "insert_after_page"}
    ),
}


def allowed_option_keys(operation: OperationType) -> frozenset[str]:
    try:
        return _OPTION_KEYS[operation]
    except KeyError:
        raise ValueError("unsupported operation") from None


def coerce_operation_options(
    operation: OperationType,
    options: JobOptions | None,
) -> OperationOptions:
    expected_type = _OPTION_TYPES[operation]
    if isinstance(options, _OptionsMapping):
        if type(options) is not expected_type:
            raise ValueError("operation and options type do not match")
        return cast(OperationOptions, options)
    if options is None:
        values: dict[str, object] = {}
    elif isinstance(options, Mapping):
        if not all(isinstance(key, str) for key in options):
            raise TypeError("options keys must be strings")
        values = dict(options)
    else:
        raise TypeError("options must be an operation options object or mapping")

    if not set(values).issubset(allowed_option_keys(operation)):
        raise ValueError("options contain unsupported keys")
    if operation is OperationType.MERGE_PDFS:
        return MergeOptions(output_path=cast(Path | None, values.get("output_path")))
    if operation is OperationType.EXTRACT_PAGES:
        return ExtractOptions(
            page_numbers=cast(tuple[int, ...], _required_option(values, "page_numbers")),
            output_path=cast(Path | None, values.get("output_path")),
        )
    if operation is OperationType.REMOVE_PAGES:
        return RemoveOptions(
            page_numbers=cast(tuple[int, ...], _required_option(values, "page_numbers")),
            output_path=cast(Path | None, values.get("output_path")),
        )
    if operation is OperationType.SPLIT_BY_RANGES:
        return SplitOptions(
            ranges=cast(tuple[PageRange, ...] | None, values.get("ranges")),
            page_groups=cast(tuple[tuple[int, ...], ...] | None, values.get("page_groups")),
            base_name=cast(str | None, values.get("base_name")),
        )
    if operation is OperationType.ROTATE_PAGES:
        return RotateOptions(
            page_numbers=cast(tuple[int, ...], _required_option(values, "page_numbers")),
            angle=cast(int, _required_option(values, "angle")),
            output_path=cast(Path | None, values.get("output_path")),
        )
    if operation is OperationType.REORDER_PAGES:
        return ReorderOptions(
            page_order=cast(tuple[int, ...], _required_option(values, "page_order")),
            output_path=cast(Path | None, values.get("output_path")),
        )
    if operation is OperationType.INSERT_PDF_PAGES:
        return InsertPagesOptions(
            page_numbers=cast(tuple[int, ...], _required_option(values, "page_numbers")),
            insert_after_page=cast(int, _required_option(values, "insert_after_page")),
            output_path=cast(Path | None, values.get("output_path")),
        )
    if operation is OperationType.INSERT_BLANK_PAGE:
        return InsertBlankPageOptions(
            width_mm=cast(float, _required_option(values, "width_mm")),
            height_mm=cast(float, _required_option(values, "height_mm")),
            insert_after_page=cast(int, _required_option(values, "insert_after_page")),
            output_path=cast(Path | None, values.get("output_path")),
        )
    raise ValueError("unsupported operation")


@dataclass(frozen=True, init=False)
class JobRequest:
    operation: OperationType
    input_files: tuple[Path, ...]
    output_dir: Path
    options: OperationOptions
    naming_strategy: NamingStrategy
    job_id: str

    def __init__(
        self,
        operation: OperationType,
        input_files: tuple[Path, ...],
        output_dir: Path,
        options: JobOptions | None = None,
        naming_strategy: NamingStrategy = "explicit",
        job_id: str = "",
    ) -> None:
        if not isinstance(operation, OperationType):
            raise TypeError("operation must be an OperationType")
        if not isinstance(input_files, tuple):
            raise TypeError("input_files must be a tuple of Path")
        if not all(isinstance(path, Path) for path in input_files):
            raise TypeError("input_files must contain only Path values")
        if not isinstance(output_dir, Path):
            raise TypeError("output_dir must be a Path")
        if not isinstance(naming_strategy, str):
            raise TypeError("naming_strategy must be a string")
        if naming_strategy != "explicit":
            raise ValueError("naming_strategy must be explicit")
        if not isinstance(job_id, str):
            raise TypeError("job_id must be a string")
        if job_id and not job_id.strip():
            raise ValueError("job_id must be empty or a non-empty string")
        _validate_input_arity(operation, input_files)
        object.__setattr__(self, "operation", operation)
        object.__setattr__(self, "input_files", input_files)
        object.__setattr__(self, "output_dir", output_dir)
        object.__setattr__(self, "options", coerce_operation_options(operation, options))
        object.__setattr__(self, "naming_strategy", naming_strategy)
        object.__setattr__(self, "job_id", job_id)

    def require_options[T: _OptionsMapping](self, option_type: type[T]) -> T:
        if not isinstance(self.options, option_type):
            raise TypeError("job options do not match the requested operation")
        return self.options


def _required_option(options: Mapping[str, object], key: str) -> object:
    try:
        return options[key]
    except KeyError:
        raise ValueError("operation options are incomplete") from None


def _validate_input_arity(operation: OperationType, input_files: tuple[Path, ...]) -> None:
    if operation is OperationType.MERGE_PDFS:
        if len(input_files) < 2:
            raise ValueError("merge requires at least two input files")
        return
    if operation is OperationType.INSERT_PDF_PAGES:
        if len(input_files) != 2:
            raise ValueError("insert pages requires exactly two input files")
        if input_files[0].resolve(strict=False) == input_files[1].resolve(strict=False):
            raise ValueError("insert pages requires two different input files")
        return
    if operation is OperationType.INSERT_BLANK_PAGE:
        if len(input_files) != 1:
            raise ValueError("insert blank page requires exactly one input file")
        return
    if len(input_files) != 1:
        raise ValueError("operation requires exactly one input file")


def _validate_optional_output_path(output_path: Path | None) -> None:
    if output_path is not None and not isinstance(output_path, Path):
        raise TypeError("output_path must be a Path or None")


def _validate_page_sequence(
    page_numbers: tuple[int, ...],
    field_name: str,
    *,
    unique: bool = False,
) -> None:
    if not isinstance(page_numbers, tuple):
        raise TypeError(f"{field_name} must be a tuple")
    if not page_numbers or len(page_numbers) > MAX_OPTION_SEQUENCE_ITEMS:
        raise ValueError(f"{field_name} must be a bounded non-empty tuple")
    if any(
        not _is_strict_int(page_number) or page_number < 1 or page_number > MAX_PAGE_NUMBER
        for page_number in page_numbers
    ):
        raise ValueError(f"{field_name} must contain bounded positive integers")
    if unique and len(set(page_numbers)) != len(page_numbers):
        raise ValueError(f"{field_name} must not contain duplicates")


def _validate_page_ranges(page_ranges: tuple[PageRange, ...]) -> None:
    if not isinstance(page_ranges, tuple):
        raise TypeError("ranges must be a tuple")
    if not page_ranges or len(page_ranges) > MAX_OPTION_SEQUENCE_ITEMS:
        raise ValueError("ranges must be a bounded non-empty tuple")
    total_pages = 0
    for page_range in page_ranges:
        if not isinstance(page_range, PageRange):
            raise TypeError("ranges must contain PageRange values")
        if page_range.start > MAX_PAGE_NUMBER or page_range.end > MAX_PAGE_NUMBER:
            raise ValueError("range bounds must be bounded positive integers")
        expected_count = page_range.end - page_range.start + 1
        if len(page_range.pages) != expected_count or any(
            page_number != page_range.start + index
            for index, page_number in enumerate(page_range.pages)
        ):
            raise ValueError("range pages must match their declared bounds")
        total_pages += len(page_range.pages)
        if total_pages > MAX_OPTION_SEQUENCE_ITEMS:
            raise ValueError("ranges contain too many page numbers")


def _validate_page_groups(page_groups: tuple[tuple[int, ...], ...]) -> None:
    if not isinstance(page_groups, tuple):
        raise TypeError("page_groups must be a tuple")
    if not page_groups or len(page_groups) > MAX_OPTION_SEQUENCE_ITEMS:
        raise ValueError("page_groups must be a bounded non-empty tuple")
    total_pages = 0
    for page_group in page_groups:
        _validate_page_sequence(page_group, "page_group")
        total_pages += len(page_group)
        if total_pages > MAX_OPTION_SEQUENCE_ITEMS:
            raise ValueError("page_groups contain too many page numbers")


def _is_strict_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


@dataclass(frozen=True)
class JobResult:
    success: bool
    output_files: tuple[Path, ...]
    warnings: tuple[str, ...]
    user_message: str
    technical_detail: str = ""
    duration_ms: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.success, bool):
            raise TypeError("success must be a bool")
        if not isinstance(self.output_files, tuple):
            raise TypeError("output_files must be a tuple of Path")
        if not all(isinstance(path, Path) for path in self.output_files):
            raise TypeError("output_files must contain only Path values")
        if not isinstance(self.warnings, tuple):
            raise TypeError("warnings must be a tuple")
        if not all(isinstance(warning, str) for warning in self.warnings):
            raise TypeError("warnings must contain only strings")
        if any(not warning.strip() for warning in self.warnings):
            raise ValueError("warnings must contain only non-empty strings")
        if not isinstance(self.user_message, str) or not self.user_message.strip():
            raise ValueError("user_message must be a non-empty string")
        if not isinstance(self.technical_detail, str):
            raise TypeError("technical_detail must be a string")
        if (
            not isinstance(self.duration_ms, int)
            or isinstance(self.duration_ms, bool)
            or self.duration_ms < 0
        ):
            raise ValueError("duration_ms must be a positive or zero integer")
        if self.success and not self.output_files:
            raise ValueError("successful results must declare output files")
        if not self.success and self.output_files:
            raise ValueError("failed results must not expose output files")
        object.__setattr__(
            self,
            "technical_detail",
            _sanitize_technical_detail(self.technical_detail),
        )


_UNIX_ABSOLUTE_PATH_RE = re.compile(r"(?<![\w.-])/(?:[^\s:/]+/)*[^\s:/]+")
_WINDOWS_ABSOLUTE_PATH_RE = re.compile(r"(?<![\w.-])[A-Za-z]:\\[^\s]+")
_SECRET_DETAIL_RE = re.compile(r"(?i)\b(password|passphrase|pwd|mot de passe)\s*[:=]\s*[^\s;]+")


def _sanitize_technical_detail(detail: str) -> str:
    sanitized = _UNIX_ABSOLUTE_PATH_RE.sub("[path]", detail)
    sanitized = _WINDOWS_ABSOLUTE_PATH_RE.sub("[path]", sanitized)
    return _SECRET_DETAIL_RE.sub(r"\1=[redacted]", sanitized)
