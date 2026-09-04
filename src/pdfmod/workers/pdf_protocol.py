from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from pdfmod.domain.jobs import (
    JobRequest,
    JobResult,
    OperationOptions,
    OperationType,
    allowed_option_keys,
)
from pdfmod.domain.page_ranges import PageRange
from pdfmod.domain.paper_sizes import MAX_PDF_PAGE_MM, MIN_PDF_PAGE_MM, validate_page_dimension_mm
from pdfmod.engine.document_inspection import DocumentInspection

PROTOCOL_NAME = "priveopdf.pdf-worker"
PROTOCOL_VERSION = 1
MAX_REQUEST_BYTES = 1024 * 1024
MAX_RESPONSE_BYTES = 1024 * 1024
MAX_PATH_CHARS = 4096
MAX_INPUT_FILES = 256
MAX_OUTPUT_FILES = 1024
MAX_SEQUENCE_ITEMS = 100_000
MAX_WARNINGS = 32
MAX_WARNING_CHARS = 128
MAX_USER_MESSAGE_CHARS = 512
MAX_TECHNICAL_CODE_CHARS = 128

WorkerAction = Literal["structural_job", "page_count", "inspect_document"]

_REQUEST_ID_RE = re.compile(r"[0-9a-f]{32}")
_SAFE_CODE_RE = re.compile(r"[a-z0-9_.:-]+")
_UNIX_ABSOLUTE_PATH_RE = re.compile(r"(?<![\w.-])/(?:[^\s:/]+/)*[^\s:/]+")
_WINDOWS_ABSOLUTE_PATH_RE = re.compile(r"(?<![\w.-])[A-Za-z]:\\[^\s]+")
_SECRET_RE = re.compile(r"(?i)\b(password|passphrase|pwd|mot de passe)\s*[:=]\s*[^\s;]+")


class ProtocolError(ValueError):
    """Raised when a worker frame does not satisfy the bounded protocol."""


@dataclass(frozen=True)
class WorkerRequest:
    request_id: str
    action: WorkerAction
    payload: JobRequest | Path


@dataclass(frozen=True)
class PageCountResponse:
    success: bool
    page_count: int | None
    user_message: str
    technical_code: str


@dataclass(frozen=True)
class InspectionResponse:
    inspection: DocumentInspection


type WorkerResponse = JobResult | PageCountResponse | InspectionResponse


def encode_job_request(request_id: str, job: JobRequest) -> bytes:
    _validate_request_id(request_id)
    payload: dict[str, object] = {
        "operation": job.operation.value,
        "input_files": [_path_text(path) for path in job.input_files],
        "output_dir": _path_text(job.output_dir),
        "options": _encode_options(job.operation, job.options),
        "naming_strategy": job.naming_strategy,
        "job_id": request_id,
    }
    return _encode_request(request_id, "structural_job", payload)


def encode_path_request(request_id: str, action: WorkerAction, path: Path) -> bytes:
    if action not in {"page_count", "inspect_document"}:
        raise ProtocolError("path requests support only document actions")
    _validate_request_id(request_id)
    return _encode_request(request_id, action, {"path": _path_text(path)})


def decode_request(frame: bytes) -> WorkerRequest:
    envelope = _decode_object(frame, MAX_REQUEST_BYTES)
    _require_exact_keys(
        envelope,
        {"protocol", "version", "type", "request_id", "action", "payload"},
    )
    _require_protocol_header(envelope, expected_type="request")
    request_id = _required_string(envelope, "request_id", 32)
    _validate_request_id(request_id)
    action = _worker_action(envelope.get("action"))
    payload = _required_object(envelope, "payload")

    if action == "structural_job":
        return WorkerRequest(request_id, action, _decode_job(payload, request_id))

    _require_exact_keys(payload, {"path"})
    path = Path(_required_path(payload, "path"))
    return WorkerRequest(request_id, action, path)


def encode_job_response(request_id: str, result: JobResult) -> bytes:
    response = {
        "success": result.success,
        "output_files": [_path_text(path) for path in result.output_files],
        "warnings": [_safe_code(warning, "worker_warning") for warning in result.warnings],
        "user_message": _bounded_user_message(result.user_message),
        "technical_code": _safe_code(result.technical_detail, "pdf_error")
        if not result.success
        else "",
        "duration_ms": result.duration_ms,
    }
    return _encode_response(request_id, "structural_job", response)


def encode_page_count_response(
    request_id: str,
    *,
    success: bool,
    page_count: int | None,
    user_message: str,
    technical_code: str = "",
) -> bytes:
    if success:
        if not _is_bounded_positive_int(page_count):
            raise ProtocolError("successful page counts require a positive integer")
        clean_code = ""
    else:
        if page_count is not None:
            raise ProtocolError("failed page counts cannot include a count")
        clean_code = _safe_code(technical_code, "pdf_error")
    response = {
        "success": success,
        "page_count": page_count,
        "user_message": _bounded_user_message(user_message),
        "technical_code": clean_code,
    }
    return _encode_response(request_id, "page_count", response)


def encode_inspection_response(request_id: str, inspection: DocumentInspection) -> bytes:
    response = {
        "page_count": inspection.page_count,
        "size_bytes": inspection.size_bytes,
        "is_encrypted": inspection.is_encrypted,
        "can_open": inspection.can_open,
        "has_extractable_text": inspection.has_extractable_text,
        "scan_likelihood": inspection.scan_likelihood,
        "ocr_recommended": inspection.ocr_recommended,
        "warnings": [_safe_code(warning, "analysis_warning") for warning in inspection.warnings],
    }
    return _encode_response(request_id, "inspect_document", response)


def decode_response(
    frame: bytes,
    *,
    expected_request_id: str,
    expected_action: WorkerAction,
) -> WorkerResponse:
    envelope = _decode_object(frame, MAX_RESPONSE_BYTES)
    _require_exact_keys(
        envelope,
        {"protocol", "version", "type", "request_id", "action", "result"},
    )
    _require_protocol_header(envelope, expected_type="response")
    request_id = _required_string(envelope, "request_id", 32)
    if request_id != expected_request_id:
        raise ProtocolError("response request id does not match")
    action = _worker_action(envelope.get("action"))
    if action != expected_action:
        raise ProtocolError("response action does not match")
    result = _required_object(envelope, "result")

    if action == "structural_job":
        return _decode_job_response(result)
    if action == "page_count":
        return _decode_page_count_response(result)
    return _decode_inspection_response(result)


def _encode_request(
    request_id: str,
    action: WorkerAction,
    payload: dict[str, object],
) -> bytes:
    return _encode_object(
        {
            "protocol": PROTOCOL_NAME,
            "version": PROTOCOL_VERSION,
            "type": "request",
            "request_id": request_id,
            "action": action,
            "payload": payload,
        },
        MAX_REQUEST_BYTES,
    )


def _encode_response(
    request_id: str,
    action: WorkerAction,
    result: dict[str, object],
) -> bytes:
    _validate_request_id(request_id)
    return _encode_object(
        {
            "protocol": PROTOCOL_NAME,
            "version": PROTOCOL_VERSION,
            "type": "response",
            "request_id": request_id,
            "action": action,
            "result": result,
        },
        MAX_RESPONSE_BYTES,
    )


def _encode_object(value: dict[str, object], byte_limit: int) -> bytes:
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise ProtocolError("message is not JSON serializable") from exc
    if len(encoded) + 1 > byte_limit:
        raise ProtocolError("message exceeds byte limit")
    return encoded + b"\n"


def _decode_object(frame: bytes, byte_limit: int) -> dict[str, object]:
    if not isinstance(frame, bytes):
        raise ProtocolError("message must be bytes")
    if len(frame) > byte_limit:
        raise ProtocolError("message exceeds byte limit")
    try:
        text = frame.decode("utf-8", errors="strict")
        value = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_non_finite_number,
        )
    except (UnicodeError, json.JSONDecodeError, ProtocolError) as exc:
        raise ProtocolError("invalid JSON message") from exc
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ProtocolError("message root must be an object")
    return cast(dict[str, object], value)


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ProtocolError("duplicate JSON key")
        result[key] = value
    return result


def _reject_non_finite_number(value: str) -> object:
    raise ProtocolError(f"non-finite number is forbidden: {value}")


def _require_protocol_header(envelope: dict[str, object], *, expected_type: str) -> None:
    if envelope.get("protocol") != PROTOCOL_NAME:
        raise ProtocolError("unknown protocol")
    version = envelope.get("version")
    if not isinstance(version, int) or isinstance(version, bool) or version != PROTOCOL_VERSION:
        raise ProtocolError("unsupported protocol version")
    if envelope.get("type") != expected_type:
        raise ProtocolError("unexpected message type")


def _worker_action(value: object) -> WorkerAction:
    if value == "structural_job":
        return "structural_job"
    if value == "page_count":
        return "page_count"
    if value == "inspect_document":
        return "inspect_document"
    raise ProtocolError("unsupported worker action")


def _decode_job(payload: dict[str, object], request_id: str) -> JobRequest:
    _require_exact_keys(
        payload,
        {"operation", "input_files", "output_dir", "options", "naming_strategy", "job_id"},
    )
    operation_text = _required_string(payload, "operation", 64)
    try:
        operation = OperationType(operation_text)
    except ValueError as exc:
        raise ProtocolError("unsupported operation") from exc

    input_values = _required_list(payload, "input_files", MAX_INPUT_FILES)
    if not input_values:
        raise ProtocolError("at least one input path is required")
    input_files = tuple(Path(_path_value(value)) for value in input_values)
    output_dir = Path(_required_path(payload, "output_dir"))
    options = _decode_options(operation, _required_object(payload, "options"))
    naming_strategy = _required_string(payload, "naming_strategy", 32)
    if naming_strategy != "explicit":
        raise ProtocolError("unsupported naming strategy")
    if _required_string(payload, "job_id", 32) != request_id:
        raise ProtocolError("job id does not match request id")
    try:
        return JobRequest(
            operation=operation,
            input_files=input_files,
            output_dir=output_dir,
            options=options,
            naming_strategy="explicit",
            job_id=request_id,
        )
    except (TypeError, ValueError) as exc:
        raise ProtocolError("invalid job request") from exc


def _encode_options(
    operation: OperationType,
    options: OperationOptions,
) -> dict[str, object]:
    allowed = allowed_option_keys(operation)
    if not all(isinstance(key, str) and key in allowed for key in options):
        raise ProtocolError("job contains unsupported options")

    encoded: dict[str, object] = {}
    for key, value in options.items():
        if key == "output_path":
            if not isinstance(value, Path):
                raise ProtocolError("output_path must be a Path")
            encoded[key] = _path_text(value)
        elif key in {"page_numbers", "page_order"}:
            encoded[key] = _encode_int_sequence(value)
        elif key == "page_groups":
            encoded[key] = _encode_page_groups(value)
        elif key == "ranges":
            encoded[key] = _encode_page_ranges(value)
        elif key == "angle":
            encoded[key] = _bounded_int(value, minimum=0, maximum=360)
        elif key == "insert_after_page":
            encoded[key] = _bounded_int(value, minimum=0, maximum=10_000_000)
        elif key in {"width_mm", "height_mm"}:
            encoded[key] = _bounded_real(value)
        elif key == "base_name":
            if not isinstance(value, str) or not value or len(value) > 255:
                raise ProtocolError("base_name must be a bounded string")
            encoded[key] = value
        else:
            raise ProtocolError("unsupported job option")
    return encoded


def _decode_options(
    operation: OperationType,
    options: dict[str, object],
) -> dict[str, object]:
    allowed = allowed_option_keys(operation)
    if not all(key in allowed for key in options):
        raise ProtocolError("job contains unsupported options")
    decoded: dict[str, object] = {}
    for key, value in options.items():
        if key == "output_path":
            decoded[key] = Path(_path_value(value))
        elif key in {"page_numbers", "page_order"}:
            decoded[key] = tuple(_decode_int_list(value))
        elif key == "page_groups":
            groups = _list_value(value, MAX_SEQUENCE_ITEMS)
            decoded[key] = tuple(tuple(_decode_int_list(group)) for group in groups)
        elif key == "ranges":
            decoded[key] = tuple(_decode_page_range(item) for item in _list_value(value))
        elif key == "angle":
            decoded[key] = _bounded_int(value, minimum=0, maximum=360)
        elif key == "insert_after_page":
            decoded[key] = _bounded_int(value, minimum=0, maximum=10_000_000)
        elif key in {"width_mm", "height_mm"}:
            decoded[key] = _bounded_real(value)
        elif key == "base_name":
            if not isinstance(value, str) or not value or len(value) > 255:
                raise ProtocolError("base_name must be a bounded string")
            decoded[key] = value
        else:
            raise ProtocolError("unsupported job option")
    return decoded


def _encode_int_sequence(value: object) -> list[int]:
    if not isinstance(value, (tuple, list)):
        raise ProtocolError("page sequence must be a list or tuple")
    if len(value) > MAX_SEQUENCE_ITEMS:
        raise ProtocolError("page sequence is too large")
    return [_bounded_int(item, minimum=1, maximum=10_000_000) for item in value]


def _encode_page_groups(value: object) -> list[list[int]]:
    if not isinstance(value, (tuple, list)) or len(value) > MAX_SEQUENCE_ITEMS:
        raise ProtocolError("page groups must be bounded")
    return [_encode_int_sequence(group) for group in value]


def _encode_page_ranges(value: object) -> list[dict[str, object]]:
    if not isinstance(value, (tuple, list)) or len(value) > MAX_SEQUENCE_ITEMS:
        raise ProtocolError("page ranges must be bounded")
    encoded: list[dict[str, object]] = []
    for item in value:
        if not isinstance(item, PageRange):
            raise ProtocolError("ranges must contain PageRange values")
        encoded.append(
            {
                "start": item.start,
                "end": item.end,
                "pages": _encode_int_sequence(item.pages),
            }
        )
    return encoded


def _decode_page_range(value: object) -> PageRange:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ProtocolError("page range must be an object")
    item = cast(dict[str, object], value)
    _require_exact_keys(item, {"start", "end", "pages"})
    try:
        return PageRange(
            start=_bounded_int(item.get("start"), minimum=1, maximum=10_000_000),
            end=_bounded_int(item.get("end"), minimum=1, maximum=10_000_000),
            pages=tuple(_decode_int_list(item.get("pages"))),
        )
    except ValueError as exc:
        raise ProtocolError("invalid page range") from exc


def _decode_int_list(value: object) -> list[int]:
    return [
        _bounded_int(item, minimum=1, maximum=10_000_000)
        for item in _list_value(value, MAX_SEQUENCE_ITEMS)
    ]


def _bounded_real(value: object) -> float:
    try:
        number = validate_page_dimension_mm(value)
    except (TypeError, ValueError) as exc:
        raise ProtocolError("number is outside allowed bounds") from exc
    if not MIN_PDF_PAGE_MM <= number <= MAX_PDF_PAGE_MM:
        raise ProtocolError("number is outside allowed bounds")
    return number


def _decode_job_response(result: dict[str, object]) -> JobResult:
    _require_exact_keys(
        result,
        {
            "success",
            "output_files",
            "warnings",
            "user_message",
            "technical_code",
            "duration_ms",
        },
    )
    success = _required_bool(result, "success")
    output_values = _required_list(result, "output_files", MAX_OUTPUT_FILES)
    output_files = tuple(Path(_path_value(value)) for value in output_values)
    warning_values = _required_list(result, "warnings", MAX_WARNINGS)
    warnings = tuple(_safe_response_code(value) for value in warning_values)
    user_message = _required_string(result, "user_message", MAX_USER_MESSAGE_CHARS)
    technical_code = _required_string(
        result,
        "technical_code",
        MAX_TECHNICAL_CODE_CHARS,
        allow_empty=True,
    )
    if technical_code and not _SAFE_CODE_RE.fullmatch(technical_code):
        raise ProtocolError("invalid technical code")
    duration_ms = _bounded_int(result.get("duration_ms"), minimum=0, maximum=86_400_000)
    try:
        return JobResult(
            success=success,
            output_files=output_files,
            warnings=warnings,
            user_message=user_message,
            technical_detail=technical_code,
            duration_ms=duration_ms,
        )
    except (TypeError, ValueError) as exc:
        raise ProtocolError("incoherent job result") from exc


def _decode_page_count_response(result: dict[str, object]) -> PageCountResponse:
    _require_exact_keys(
        result,
        {"success", "page_count", "user_message", "technical_code"},
    )
    success = _required_bool(result, "success")
    page_count_value = result.get("page_count")
    page_count = (
        None
        if page_count_value is None
        else _bounded_int(page_count_value, minimum=1, maximum=10_000_000)
    )
    user_message = _required_string(result, "user_message", MAX_USER_MESSAGE_CHARS)
    technical_code = _required_string(
        result,
        "technical_code",
        MAX_TECHNICAL_CODE_CHARS,
        allow_empty=True,
    )
    if technical_code and not _SAFE_CODE_RE.fullmatch(technical_code):
        raise ProtocolError("invalid technical code")
    if success != (page_count is not None) or (success and technical_code):
        raise ProtocolError("incoherent page count result")
    if not success and not technical_code:
        raise ProtocolError("failed page count requires a technical code")
    return PageCountResponse(success, page_count, user_message, technical_code)


def _decode_inspection_response(result: dict[str, object]) -> InspectionResponse:
    _require_exact_keys(
        result,
        {
            "page_count",
            "size_bytes",
            "is_encrypted",
            "can_open",
            "has_extractable_text",
            "scan_likelihood",
            "ocr_recommended",
            "warnings",
        },
    )
    page_count_value = result.get("page_count")
    page_count = (
        None
        if page_count_value is None
        else _bounded_int(page_count_value, minimum=0, maximum=10_000_000)
    )
    scan_likelihood = result.get("scan_likelihood")
    if scan_likelihood not in {"unknown", "low", "medium", "high"}:
        raise ProtocolError("invalid scan likelihood")
    warnings = tuple(
        _safe_response_code(value) for value in _required_list(result, "warnings", MAX_WARNINGS)
    )
    inspection = DocumentInspection(
        page_count=page_count,
        size_bytes=_bounded_int(result.get("size_bytes"), minimum=0, maximum=2**63 - 1),
        is_encrypted=_required_bool(result, "is_encrypted"),
        can_open=_required_bool(result, "can_open"),
        has_extractable_text=_required_bool(result, "has_extractable_text"),
        scan_likelihood=cast(Literal["unknown", "low", "medium", "high"], scan_likelihood),
        ocr_recommended=_required_bool(result, "ocr_recommended"),
        warnings=warnings,
    )
    if inspection.can_open and inspection.page_count is None:
        raise ProtocolError("open inspection must include a page count")
    if not inspection.can_open and inspection.has_extractable_text:
        raise ProtocolError("closed inspection cannot expose text")
    return InspectionResponse(inspection)


def _required_object(mapping: dict[str, object], key: str) -> dict[str, object]:
    value = mapping.get(key)
    if not isinstance(value, dict) or not all(isinstance(item, str) for item in value):
        raise ProtocolError(f"{key} must be an object")
    return cast(dict[str, object], value)


def _required_list(
    mapping: dict[str, object],
    key: str,
    maximum: int = MAX_SEQUENCE_ITEMS,
) -> list[object]:
    return _list_value(mapping.get(key), maximum)


def _list_value(value: object, maximum: int = MAX_SEQUENCE_ITEMS) -> list[object]:
    if not isinstance(value, list) or len(value) > maximum:
        raise ProtocolError("value must be a bounded list")
    return cast(list[object], value)


def _required_string(
    mapping: dict[str, object],
    key: str,
    maximum: int,
    *,
    allow_empty: bool = False,
) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or len(value) > maximum or (not allow_empty and not value):
        raise ProtocolError(f"{key} must be a bounded string")
    if "\x00" in value or "\r" in value or "\n" in value:
        raise ProtocolError(f"{key} contains forbidden characters")
    return value


def _required_path(mapping: dict[str, object], key: str) -> str:
    return _path_value(mapping.get(key))


def _path_value(value: object) -> str:
    if not isinstance(value, str) or not value or len(value) > MAX_PATH_CHARS:
        raise ProtocolError("path must be a bounded string")
    if "\x00" in value or "\r" in value or "\n" in value:
        raise ProtocolError("path contains forbidden characters")
    return value


def _path_text(path: Path) -> str:
    if not isinstance(path, Path):
        raise ProtocolError("path value must be a Path")
    return _path_value(str(path))


def _required_bool(mapping: dict[str, object], key: str) -> bool:
    value = mapping.get(key)
    if not isinstance(value, bool):
        raise ProtocolError(f"{key} must be a boolean")
    return value


def _bounded_int(value: object, *, minimum: int, maximum: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum or value > maximum:
        raise ProtocolError("integer is outside allowed bounds")
    return value


def _is_bounded_positive_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 10_000_000


def _require_exact_keys(mapping: dict[str, object], expected: set[str]) -> None:
    if set(mapping) != expected:
        raise ProtocolError("object keys do not match schema")


def _validate_request_id(request_id: str) -> None:
    if not isinstance(request_id, str) or not _REQUEST_ID_RE.fullmatch(request_id):
        raise ProtocolError("request id must be 32 lowercase hexadecimal characters")


def _bounded_user_message(message: str) -> str:
    if not isinstance(message, str):
        raise ProtocolError("user message must be a string")
    clean = _UNIX_ABSOLUTE_PATH_RE.sub("[path]", message)
    clean = _WINDOWS_ABSOLUTE_PATH_RE.sub("[path]", clean)
    clean = _SECRET_RE.sub(r"\1=[redacted]", clean)
    clean = " ".join(clean.split())
    if not clean:
        return "L'operation PDF a echoue."
    return clean[:MAX_USER_MESSAGE_CHARS]


def _safe_code(value: str, fallback: str) -> str:
    if not isinstance(value, str):
        return fallback
    candidate = value.strip().split(maxsplit=1)[0] if value.strip() else ""
    if not candidate or len(candidate) > MAX_TECHNICAL_CODE_CHARS:
        return fallback
    return candidate if _SAFE_CODE_RE.fullmatch(candidate) else fallback


def _safe_response_code(value: object) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > MAX_WARNING_CHARS
        or not _SAFE_CODE_RE.fullmatch(value)
    ):
        raise ProtocolError("invalid warning code")
    return value
