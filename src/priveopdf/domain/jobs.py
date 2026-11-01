from __future__ import annotations

import math
import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Literal, cast

from priveopdf.domain.ocr_languages import validate_ocr_languages
from priveopdf.domain.page_ranges import PageRange
from priveopdf.domain.paper_sizes import validate_page_dimension_mm

MAX_OPTION_SEQUENCE_ITEMS = 100_000
MAX_PAGE_NUMBER = 10_000_000
MAX_BASE_NAME_CHARS = 255


class OperationType(StrEnum):
    REMOVE_METADATA = "remove_metadata"
    PHOTOCOPY_PDF = "photocopy_pdf"
    OCR_PDF = "ocr_pdf"
    REDACT_PDF = "redact_pdf"
    WATERMARK_PDF = "watermark_pdf"
    PROTECT_PDF = "protect_pdf"
    UNLOCK_PDF = "unlock_pdf"
    COMPRESS_PDF = "compress_pdf"
    MERGE_PDFS = "merge_pdfs"
    EXTRACT_PAGES = "extract_pages"
    REMOVE_PAGES = "remove_pages"
    SPLIT_BY_RANGES = "split_by_ranges"
    ROTATE_PAGES = "rotate_pages"
    REORDER_PAGES = "reorder_pages"
    INSERT_PDF_PAGES = "insert_pdf_pages"
    INSERT_BLANK_PAGE = "insert_blank_page"


type NamingStrategy = Literal["explicit"]
type CompressionProfile = Literal["lossless", "strong"]


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


@dataclass(frozen=True, eq=False)
class CompressionOptions(_OptionsMapping):
    output_path: Path
    profile: CompressionProfile = "lossless"
    operation: Literal[OperationType.COMPRESS_PDF] = field(
        default=OperationType.COMPRESS_PDF, init=False, repr=False
    )

    def __post_init__(self) -> None:
        if not isinstance(self.output_path, Path):
            raise TypeError("compression requires an output Path")
        if not isinstance(self.profile, str) or self.profile not in {"lossless", "strong"}:
            raise ValueError("unsupported compression profile")


@dataclass(frozen=True, eq=False)
class ProtectOptions(_OptionsMapping):
    output_path: Path
    replace_input: bool = False
    operation: Literal[OperationType.PROTECT_PDF] = field(
        default=OperationType.PROTECT_PDF, init=False, repr=False
    )

    def __post_init__(self) -> None:
        if not isinstance(self.output_path, Path):
            raise TypeError("protection requires an output Path")
        if type(self.replace_input) is not bool:
            raise TypeError("replace_input must be a boolean")


@dataclass(frozen=True, eq=False)
class UnlockOptions(_OptionsMapping):
    output_path: Path
    replace_input: bool = False
    operation: Literal[OperationType.UNLOCK_PDF] = field(
        default=OperationType.UNLOCK_PDF, init=False, repr=False
    )

    def __post_init__(self) -> None:
        if not isinstance(self.output_path, Path):
            raise TypeError("unlock requires an output Path")
        if type(self.replace_input) is not bool:
            raise TypeError("replace_input must be a boolean")


@dataclass(frozen=True, eq=False)
class RemoveMetadataOptions(_OptionsMapping):
    output_path: Path
    replace_input: bool = False
    operation: Literal[OperationType.REMOVE_METADATA] = field(
        default=OperationType.REMOVE_METADATA, init=False, repr=False
    )

    def __post_init__(self) -> None:
        if not isinstance(self.output_path, Path):
            raise TypeError("sharing requires an output Path")
        if type(self.replace_input) is not bool:
            raise TypeError("replace_input must be a boolean")


@dataclass(frozen=True, eq=False)
class PhotocopyOptions(_OptionsMapping):
    output_path: Path
    replace_input: bool = False
    source_identity: tuple[int, ...] = ()
    operation: Literal[OperationType.PHOTOCOPY_PDF] = field(
        default=OperationType.PHOTOCOPY_PDF, init=False, repr=False
    )

    def __post_init__(self) -> None:
        if not isinstance(self.output_path, Path):
            raise TypeError("sharing requires an output Path")
        if type(self.replace_input) is not bool:
            raise TypeError("replace_input must be a boolean")

        if (
            not isinstance(self.source_identity, tuple)
            or len(self.source_identity) not in {0, 5}
            or any(type(v) is not int or not 0 <= v < 2**64 for v in self.source_identity)
        ):
            raise ValueError("invalid preview source identity")


# Debian/Ubuntu system models (tesseract-ocr-<code>); never bundled nor downloaded.
# Codes: `priveopdf.domain.ocr_languages`.
OCR_TESSDATA = Path("/usr/share/tesseract-ocr/5/tessdata")
# Bounds of one OCR job: the document, then the scanned pages actually recognized
# (each rendered at 200 dpi, about 3.9 Mpx for A4; one page in memory at a time).
OCR_MAX_DOCUMENT_PAGES = 500
OCR_MAX_SCANNED_PAGES = 50
OCR_MAX_SCANNED_PIXELS = 200_000_000
# Recognition takes several seconds per page, twice that for a turned scan read
# both ways: 50 dense pages need far more than the default two minutes. The
# interface, the corpus and the versioned gate all apply this same delay.
OCR_TIMEOUT_SECONDS = 1800.0
# Tesseract uses at most two threads: CPU time stays within twice the wall time.
OCR_CPU_SECONDS = 3600
OCR_STATE_PREFIXES: tuple[str, ...] = (
    "ocr_pages_recognized_",
    "ocr_pages_text_present_",
    "ocr_pages_no_text_",
)


@dataclass(frozen=True, eq=False)
class OcrOptions(_OptionsMapping):
    """Searchable copy of the scanned pages; pages that already carry text stay intact.

    ``page_numbers`` (OCR10) restricts recognition to those 1-based pages;
    empty means every scanned page. Pages left out stay exactly as they were.
    ``allow_unsigned_copy`` accepts a digitally signed source: the copy is
    produced without its signatures, which the operation would invalidate.
    """

    output_path: Path
    languages: tuple[str, ...] = ("eng",)
    page_numbers: tuple[int, ...] = ()
    allow_unsigned_copy: bool = False
    operation: Literal[OperationType.OCR_PDF] = field(
        default=OperationType.OCR_PDF, init=False, repr=False
    )

    def __post_init__(self) -> None:
        if not isinstance(self.output_path, Path):
            raise TypeError("OCR requires an output Path")
        if not isinstance(self.page_numbers, tuple):
            raise TypeError("page_numbers must be a tuple")
        if type(self.allow_unsigned_copy) is not bool:
            raise TypeError("allow_unsigned_copy must be a bool")
        if self.page_numbers:
            _validate_page_sequence(self.page_numbers, "page_numbers", unique=True)
            if len(self.page_numbers) > OCR_MAX_DOCUMENT_PAGES:
                raise ValueError("page_numbers exceeds the OCR document bound")
        if not isinstance(self.languages, tuple):
            raise TypeError("languages must be a tuple")
        validate_ocr_languages(self.languages)


# One redaction job: areas in page units (PDF points of the displayed page,
# origin top-left), at most this many; the photocopy bounds (pages, pixels) apply.
REDACTION_MAX_AREAS = 500
REDACTION_MAX_COORDINATE = 14_400.0
type RedactionAreaTuple = tuple[int, float, float, float, float]


WATERMARK_MAX_TEXT = 120
WATERMARK_LAYOUTS: tuple[str, ...] = ("diagonal", "tiled")
WATERMARK_STRENGTHS: tuple[str, ...] = ("light", "medium", "strong")


def validate_watermark_text(text: object) -> str:
    """The visible text: 1 to 120 printable Latin-1 (cp1252) characters.

    Returns the text as written: a no-break space (pasted from an office
    document) becomes a space and a soft hyphen is dropped, two invisible
    characters the PDF engine would not find again (review of B6).
    """
    if not isinstance(text, str):
        raise ValueError("watermark text must be a string")
    text = text.replace("\u00a0", " ").replace("\u00ad", "")
    if not text.strip() or len(text) > WATERMARK_MAX_TEXT:
        raise ValueError("watermark text must be 1 to 120 characters")
    try:
        encoded = text.encode("cp1252")
    except UnicodeEncodeError:
        raise ValueError("watermark text must use Latin-1 characters") from None
    if any(code < 32 or code == 127 for code in encoded):
        raise ValueError("watermark text must be printable")
    return text


@dataclass(frozen=True, eq=False)
class WatermarkOptions(_OptionsMapping):
    """Traceability watermark (SEC13): a visible text drawn into the content of
    every page, verified after export. ``allow_unsigned_copy``: see `OcrOptions`."""

    output_path: Path
    text: str = ""
    layout: str = "diagonal"
    strength: str = "medium"
    source_identity: tuple[int, ...] = ()
    allow_unsigned_copy: bool = False
    operation: Literal[OperationType.WATERMARK_PDF] = field(
        default=OperationType.WATERMARK_PDF, init=False, repr=False
    )

    def __post_init__(self) -> None:
        if not isinstance(self.output_path, Path):
            raise TypeError("watermark requires an output Path")
        if type(self.allow_unsigned_copy) is not bool:
            raise TypeError("allow_unsigned_copy must be a bool")
        validate_watermark_text(self.text)
        if self.layout not in WATERMARK_LAYOUTS or self.strength not in WATERMARK_STRENGTHS:
            raise ValueError("watermark layout or strength unknown")
        if (
            not isinstance(self.source_identity, tuple)
            or len(self.source_identity) not in {0, 5}
            or any(type(v) is not int or not 0 <= v < 2**64 for v in self.source_identity)
        ):
            raise ValueError("invalid preview source identity")


@dataclass(frozen=True, eq=False)
class RedactOptions(_OptionsMapping):
    """Destructive redaction (SEC05): every page becomes pixels, the areas become
    black, and the result is verified independently (SEC06).

    ``areas`` holds ``(page_index, x, y, width, height)`` with a 0-based page
    index and page units of the displayed page. ``allow_unsigned_copy``: see
    `OcrOptions`.
    """

    output_path: Path
    areas: tuple[RedactionAreaTuple, ...] = ()
    source_identity: tuple[int, ...] = ()
    allow_unsigned_copy: bool = False
    operation: Literal[OperationType.REDACT_PDF] = field(
        default=OperationType.REDACT_PDF, init=False, repr=False
    )

    def __post_init__(self) -> None:
        if not isinstance(self.output_path, Path):
            raise TypeError("redaction requires an output Path")
        if type(self.allow_unsigned_copy) is not bool:
            raise TypeError("allow_unsigned_copy must be a bool")
        if not isinstance(self.areas, tuple) or not 1 <= len(self.areas) <= REDACTION_MAX_AREAS:
            raise ValueError("redaction requires 1 to 500 areas")
        for area in self.areas:
            validate_redaction_area(area)
        if (
            not isinstance(self.source_identity, tuple)
            or len(self.source_identity) not in {0, 5}
            or any(type(v) is not int or not 0 <= v < 2**64 for v in self.source_identity)
        ):
            raise ValueError("invalid preview source identity")


def validate_redaction_area(area: object) -> RedactionAreaTuple:
    if not isinstance(area, tuple) or len(area) != 5:
        raise ValueError("a redaction area is (page, x, y, width, height)")
    page, x, y, width, height = area
    if type(page) is not int or not 0 <= page < 10_000:
        raise ValueError("redaction area page out of range")
    for value in (x, y, width, height):
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError("redaction area coordinates must be finite numbers")
    if x < 0 or y < 0 or width <= 0 or height <= 0:
        raise ValueError("redaction area must have a positive size inside the page")
    if x + width > REDACTION_MAX_COORDINATE or y + height > REDACTION_MAX_COORDINATE:
        raise ValueError("redaction area beyond the largest page")
    return (page, float(x), float(y), float(width), float(height))


SHARE_OPERATIONS = frozenset({OperationType.REMOVE_METADATA, OperationType.PHOTOCOPY_PDF})
PASSWORD_OPERATIONS = frozenset({OperationType.PROTECT_PDF, OperationType.UNLOCK_PDF})
STAGED_OUTPUT_OPERATIONS = (
    PASSWORD_OPERATIONS
    | SHARE_OPERATIONS
    | {
        OperationType.COMPRESS_PDF,
        OperationType.OCR_PDF,
        OperationType.REDACT_PDF,
        OperationType.WATERMARK_PDF,
    }
)
# Jobs that render pages with the PDF engine inside the worker: they run under
# the memory scope of the photocopy.
RENDERING_OPERATIONS = frozenset(
    {
        OperationType.PHOTOCOPY_PDF,
        OperationType.OCR_PDF,
        OperationType.REDACT_PDF,
        OperationType.WATERMARK_PDF,
    }
)


def validate_pdf_password(password: object) -> str:
    """Validate without normalizing or ever echoing the secret in an error."""
    if not isinstance(password, str):
        raise TypeError("password must be a string")
    try:
        length = len(password.encode("utf-8"))
    except UnicodeError:
        raise ValueError("password must be valid UTF-8") from None
    if not 1 <= length <= 127 or any(char in password for char in ("\x00", "\r", "\n")):
        raise ValueError("password must contain 1 to 127 UTF-8 bytes without NUL or newlines")
    return password


@dataclass(frozen=True)
class CompressionMetrics:
    source_bytes: int
    candidate_bytes: int

    def __post_init__(self) -> None:
        for value in (self.source_bytes, self.candidate_bytes):
            if not _is_strict_int(value) or not 0 < value <= 64 * 1024**3:
                raise ValueError("compression sizes must be bounded positive integers")

    @property
    def reduction_percent(self) -> float:
        return 100.0 * (self.source_bytes - self.candidate_bytes) / self.source_bytes


type OperationOptions = (
    RemoveMetadataOptions
    | PhotocopyOptions
    | OcrOptions
    | RedactOptions
    | WatermarkOptions
    | CompressionOptions
    | ProtectOptions
    | UnlockOptions
    | MergeOptions
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
    OperationType.REMOVE_METADATA: RemoveMetadataOptions,
    OperationType.PHOTOCOPY_PDF: PhotocopyOptions,
    OperationType.OCR_PDF: OcrOptions,
    OperationType.REDACT_PDF: RedactOptions,
    OperationType.WATERMARK_PDF: WatermarkOptions,
    OperationType.PROTECT_PDF: ProtectOptions,
    OperationType.UNLOCK_PDF: UnlockOptions,
    OperationType.COMPRESS_PDF: CompressionOptions,
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
    OperationType.REMOVE_METADATA: frozenset({"output_path", "replace_input"}),
    OperationType.PHOTOCOPY_PDF: frozenset({"output_path", "replace_input", "source_identity"}),
    OperationType.OCR_PDF: frozenset(
        {"output_path", "languages", "page_numbers", "allow_unsigned_copy"}
    ),
    OperationType.REDACT_PDF: frozenset(
        {"output_path", "areas", "source_identity", "allow_unsigned_copy"}
    ),
    OperationType.WATERMARK_PDF: frozenset(
        {"output_path", "text", "layout", "strength", "source_identity", "allow_unsigned_copy"}
    ),
    OperationType.PROTECT_PDF: frozenset({"output_path", "replace_input"}),
    OperationType.UNLOCK_PDF: frozenset({"output_path", "replace_input"}),
    OperationType.COMPRESS_PDF: frozenset({"output_path", "profile"}),
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
    if operation is OperationType.REMOVE_METADATA:
        return RemoveMetadataOptions(
            output_path=cast(Path, _required_option(values, "output_path")),
            replace_input=cast(bool, values.get("replace_input", False)),
        )
    if operation is OperationType.PHOTOCOPY_PDF:
        return PhotocopyOptions(
            output_path=cast(Path, _required_option(values, "output_path")),
            replace_input=cast(bool, values.get("replace_input", False)),
            source_identity=cast(tuple[int, ...], values.get("source_identity", ())),
        )
    if operation is OperationType.OCR_PDF:
        return OcrOptions(
            output_path=cast(Path, _required_option(values, "output_path")),
            languages=cast(tuple[str, ...], values.get("languages", ("eng",))),
            page_numbers=cast(tuple[int, ...], values.get("page_numbers", ())),
            allow_unsigned_copy=cast(bool, values.get("allow_unsigned_copy", False)),
        )
    if operation is OperationType.REDACT_PDF:
        return RedactOptions(
            output_path=cast(Path, _required_option(values, "output_path")),
            areas=cast(tuple[RedactionAreaTuple, ...], values.get("areas", ())),
            source_identity=cast(tuple[int, ...], values.get("source_identity", ())),
            allow_unsigned_copy=cast(bool, values.get("allow_unsigned_copy", False)),
        )
    if operation is OperationType.WATERMARK_PDF:
        return WatermarkOptions(
            output_path=cast(Path, _required_option(values, "output_path")),
            text=cast(str, values.get("text", "")),
            layout=cast(str, values.get("layout", "diagonal")),
            strength=cast(str, values.get("strength", "medium")),
            source_identity=cast(tuple[int, ...], values.get("source_identity", ())),
            allow_unsigned_copy=cast(bool, values.get("allow_unsigned_copy", False)),
        )
    if operation is OperationType.PROTECT_PDF:
        return ProtectOptions(
            output_path=cast(Path, _required_option(values, "output_path")),
            replace_input=cast(bool, values.get("replace_input", False)),
        )
    if operation is OperationType.UNLOCK_PDF:
        return UnlockOptions(
            output_path=cast(Path, _required_option(values, "output_path")),
            replace_input=cast(bool, values.get("replace_input", False)),
        )
    if operation is OperationType.COMPRESS_PDF:
        return CompressionOptions(
            output_path=cast(Path, _required_option(values, "output_path")),
            profile=cast(CompressionProfile, values.get("profile", "lossless")),
        )
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
    password: str | None = field(default=None, repr=False, compare=False)

    def __init__(
        self,
        operation: OperationType,
        input_files: tuple[Path, ...],
        output_dir: Path,
        options: JobOptions | None = None,
        naming_strategy: NamingStrategy = "explicit",
        job_id: str = "",
        password: str | None = None,
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
        if operation in PASSWORD_OPERATIONS:
            validate_pdf_password(password)
        elif password is not None:
            raise ValueError("password is only allowed for password operations")
        _validate_input_arity(operation, input_files)
        object.__setattr__(self, "operation", operation)
        object.__setattr__(self, "input_files", input_files)
        object.__setattr__(self, "output_dir", output_dir)
        object.__setattr__(self, "options", coerce_operation_options(operation, options))
        object.__setattr__(self, "naming_strategy", naming_strategy)
        object.__setattr__(self, "job_id", job_id)
        object.__setattr__(self, "password", password)

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
    compression: CompressionMetrics | None = None

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
        if self.compression is not None:
            if not isinstance(self.compression, CompressionMetrics):
                raise TypeError("compression must contain typed metrics")
            has_gain = self.compression.candidate_bytes < self.compression.source_bytes
            if self.success and (not has_gain or len(self.output_files) != 1):
                raise ValueError("compression success requires one smaller output")
            if self.technical_detail == "compression_no_gain" and has_gain:
                raise ValueError("no-gain result cannot declare a reduction")
        if self.technical_detail == "compression_no_gain" and (
            self.success or self.compression is None
        ):
            raise ValueError("no-gain result requires failure status and metrics")
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
