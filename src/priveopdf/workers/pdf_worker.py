from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    parser.add_argument("--render-memory", action="store_true")
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

    memory_limit = arguments.memory_bytes
    if arguments.render_memory:
        from priveopdf.workers.render_memory import VIRTUAL_RENDER_BYTES, verify_render_budget

        verify_render_budget(arguments.memory_bytes)
        memory_limit = VIRTUAL_RENDER_BYTES
    _set_limit(resource.RLIMIT_AS, memory_limit)
    _set_limit(resource.RLIMIT_CPU, arguments.cpu_seconds)
    _set_limit(resource.RLIMIT_FSIZE, arguments.file_size_bytes)
    _set_limit(resource.RLIMIT_NOFILE, arguments.open_files)
    if hasattr(resource, "RLIMIT_NPROC") and not arguments.render_memory:
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


def _progress(done: int, total: int) -> None:
    sys.stdout.buffer.write(f"PRIVEO_PROGRESS {done} {total}\n".encode("ascii"))
    sys.stdout.buffer.flush()


def _execute(frame: bytes) -> bytes:
    from pathlib import Path

    from priveopdf.domain.errors import InternalPdfEngineError, PdfModError
    from priveopdf.domain.jobs import JobRequest
    from priveopdf.engine.document_inspection import DocumentInspectionService
    from priveopdf.engine.pdf_structural import page_summary, run_structural_job
    from priveopdf.workers.pdf_protocol import (
        ProtocolError,
        decode_request,
        encode_inspection_response,
        encode_job_response,
        encode_page_count_response,
        encode_share_response,
    )

    request = decode_request(frame)
    if request.action == "structural_job":
        if not isinstance(request.payload, JobRequest):
            raise ProtocolError("job payload has an invalid type")
        return encode_job_response(
            request.request_id, run_structural_job(request.payload, _progress)
        )

    if not isinstance(request.payload, Path):
        raise ProtocolError("document payload has an invalid type")
    if request.action == "inspect_share":
        from priveopdf.engine.share_inspection import inspect_share

        return encode_share_response(request.request_id, inspect_share(request.payload))
    if request.action == "inspect_document":
        inspection = DocumentInspectionService().inspect(request.payload)
        return encode_inspection_response(request.request_id, inspection)

    try:
        page_count, signed = page_summary(request.payload)
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
        signed=signed,
    )


def main(argv: Sequence[str] | None = None) -> int:
    os.umask(0o077)
    try:
        from priveopdf.workers.local_confinement import PROFILE_ENV, apply_worker_profile

        arguments = _parser().parse_args(argv)
        try:
            if arguments.render_memory and PROFILE_ENV in os.environ:
                from priveopdf.workers.render_memory import request_render_budget

                request_render_budget(arguments.memory_bytes)
            # Verify the readonly kernel budget before Landlock hides cgroups,
            # then close IPC and file access before any native PDF/Qt import.
            _apply_resource_limits(arguments)
        except (OSError, ValueError):
            return 79 if arguments.render_memory else 65
        try:
            apply_worker_profile()
        except (OSError, ValueError):
            return 78
        from priveopdf.workers.pdf_protocol import MAX_REQUEST_BYTES

        frame = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
        if len(frame) > MAX_REQUEST_BYTES:
            return 65
        response = _execute(frame)
        sys.stdout.buffer.write(response)
        sys.stdout.buffer.flush()
        return 0
    except (OSError, ValueError):
        return 65
    except BaseException:
        return 70


if __name__ == "__main__":
    raise SystemExit(main())
