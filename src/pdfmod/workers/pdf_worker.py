from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    parser.add_argument("--memory-bytes", required=True, type=int)
    parser.add_argument("--cpu-seconds", required=True, type=int)
    parser.add_argument("--file-size-bytes", required=True, type=int)
    parser.add_argument("--open-files", required=True, type=int)
    parser.add_argument("--processes", required=True, type=int)
    return parser


def _apply_resource_limits(arguments: argparse.Namespace) -> None:
    if not sys.platform.startswith("linux"):
        return
    import resource

    _set_limit(resource.RLIMIT_AS, arguments.memory_bytes)
    _set_limit(resource.RLIMIT_CPU, arguments.cpu_seconds)
    _set_limit(resource.RLIMIT_FSIZE, arguments.file_size_bytes)
    _set_limit(resource.RLIMIT_NOFILE, arguments.open_files)
    if hasattr(resource, "RLIMIT_NPROC"):
        _set_limit(resource.RLIMIT_NPROC, arguments.processes)
    if hasattr(resource, "RLIMIT_CORE"):
        _set_limit(resource.RLIMIT_CORE, 0)


def _set_limit(resource_kind: int, requested: int) -> None:
    import resource

    if not isinstance(requested, int) or isinstance(requested, bool) or requested < 0:
        raise ValueError("invalid resource limit")
    _soft, current_hard = resource.getrlimit(resource_kind)
    effective = requested
    if current_hard != resource.RLIM_INFINITY:
        effective = min(effective, current_hard)
    resource.setrlimit(resource_kind, (effective, effective))


def _execute(frame: bytes) -> bytes:
    from pathlib import Path

    from pdfmod.domain.errors import InternalPdfEngineError, PdfModError
    from pdfmod.domain.jobs import JobRequest
    from pdfmod.engine.document_inspection import DocumentInspectionService
    from pdfmod.engine.pdf_structural import get_page_count, run_structural_job
    from pdfmod.workers.pdf_protocol import (
        ProtocolError,
        decode_request,
        encode_inspection_response,
        encode_job_response,
        encode_page_count_response,
    )

    request = decode_request(frame)
    if request.action == "structural_job":
        if not isinstance(request.payload, JobRequest):
            raise ProtocolError("job payload has an invalid type")
        return encode_job_response(request.request_id, run_structural_job(request.payload))

    if not isinstance(request.payload, Path):
        raise ProtocolError("document payload has an invalid type")
    if request.action == "inspect_document":
        inspection = DocumentInspectionService().inspect(request.payload)
        return encode_inspection_response(request.request_id, inspection)

    try:
        page_count = get_page_count(request.payload)
    except PdfModError as exc:
        return encode_page_count_response(
            request.request_id,
            success=False,
            page_count=None,
            user_message=exc.user_message,
            technical_code=exc.technical_code,
        )
    except Exception:
        return encode_page_count_response(
            request.request_id,
            success=False,
            page_count=None,
            user_message=InternalPdfEngineError.user_message,
            technical_code=InternalPdfEngineError.technical_code,
        )
    return encode_page_count_response(
        request.request_id,
        success=True,
        page_count=page_count,
        user_message=f"{page_count} page(s) detectee(s).",
    )


def main(argv: Sequence[str] | None = None) -> int:
    os.umask(0o077)
    try:
        arguments = _parser().parse_args(argv)
        _apply_resource_limits(arguments)
        from pdfmod.workers.pdf_protocol import MAX_REQUEST_BYTES, ProtocolError

        frame = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
        if len(frame) > MAX_REQUEST_BYTES:
            return 65
        response = _execute(frame)
        sys.stdout.buffer.write(response)
        sys.stdout.buffer.flush()
        return 0
    except (OSError, ValueError, ProtocolError):
        return 65
    except BaseException:
        return 70


if __name__ == "__main__":
    raise SystemExit(main())
