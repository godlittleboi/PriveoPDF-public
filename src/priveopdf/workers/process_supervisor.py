"""Fail-closed local PDF process isolation for the qualified Linux path."""

from __future__ import annotations

import json
import os
import re
import selectors
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass, replace
from pathlib import Path
from typing import BinaryIO, Literal

from priveopdf.domain.document_inspection import DocumentInspection
from priveopdf.domain.errors import (
    DangerousOutputError,
    InputPathError,
    OutputWriteError,
    PdfModError,
    UserCancelledError,
)
from priveopdf.domain.jobs import (
    OCR_MAX_DOCUMENT_PAGES,
    OCR_MAX_SCANNED_PAGES,
    OCR_STATE_PREFIXES,
    RENDERING_OPERATIONS,
    STAGED_OUTPUT_OPERATIONS,
    CompressionOptions,
    JobRequest,
    JobResult,
    OcrOptions,
    OperationType,
    PhotocopyOptions,
    ProtectOptions,
    RedactOptions,
    RemoveMetadataOptions,
    SplitOptions,
    UnlockOptions,
    WatermarkOptions,
)
from priveopdf.domain.page_plans import split_group_file_names, split_range_file_names
from priveopdf.domain.share_inspection import ShareInspection
from priveopdf.utils.secure_paths import (
    atomic_replace_source,
    atomic_write_no_replace_tracked,
    portable_filename_stem,
    snapshot_replacement_source,
)
from priveopdf.utils.validation import prepare_pdf_output_path
from priveopdf.workers.local_confinement import PROFILE_ENV, _runtime_read_roots
from priveopdf.workers.network_isolation import document_namespace_verified
from priveopdf.workers.pdf_protocol import (
    MAX_RESPONSE_BYTES,
    InspectionResponse,
    PageCountResponse,
    ProgressFrames,
    ProtocolError,
    WorkerAction,
    decode_response,
    encode_job_request,
    encode_path_request,
)

DEFAULT_TIMEOUT_SECONDS = 120.0
_SOURCE_ROOT = Path(__file__).resolve().parents[2]
_PROC_NET_DEV = Path("/proc/net/dev")
_BWRAP_PROBE_LOCK = threading.Lock()
_BWRAP_PROBE_CACHE: dict[str, bool] = {}

IsolationMode = Literal["process", "bubblewrap", "document_namespace", "landlock"]


@dataclass(frozen=True)
class ResourceLimits:
    memory_bytes: int = 1536 * 1024 * 1024
    cpu_seconds: int = 120
    file_size_bytes: int = 2 * 1024 * 1024 * 1024
    open_files: int = 64
    processes: int = 16

    def __post_init__(self) -> None:
        limits = {
            "memory_bytes": (self.memory_bytes, 32 * 1024 * 1024, 16 * 1024**3),
            "cpu_seconds": (self.cpu_seconds, 1, 3600),
            "file_size_bytes": (self.file_size_bytes, 1024, 64 * 1024**3),
            "open_files": (self.open_files, 16, 4096),
            "processes": (self.processes, 1, 1024),
        }
        for name, (value, minimum, maximum) in limits.items():
            if (
                not isinstance(value, int)
                or isinstance(value, bool)
                or value < minimum
                or value > maximum
            ):
                raise ValueError(f"{name} is outside the supported range")

    def command_arguments(self) -> tuple[str, ...]:
        return (
            "--memory-bytes",
            str(self.memory_bytes),
            "--cpu-seconds",
            str(self.cpu_seconds),
            "--file-size-bytes",
            str(self.file_size_bytes),
            "--open-files",
            str(self.open_files),
            "--processes",
            str(self.processes),
        )


class ProcessSupervisorError(RuntimeError):
    def __init__(self, code: str, user_message: str) -> None:
        super().__init__(code)
        self.code = code
        self.user_message = user_message


@dataclass(frozen=True)
class _SandboxAccess:
    read_paths: tuple[Path, ...]
    write_dirs: tuple[Path, ...]


class ProcessSupervisor:
    """One-job-at-a-time local subprocess supervisor with bounded JSON I/O."""

    def __init__(
        self,
        *,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        limits: ResourceLimits | None = None,
        use_bubblewrap: bool | None = None,
        worker_command: Sequence[str] | None = None,
        termination_grace_seconds: float = 0.5,
        progress: Callable[[int, int], None] | None = None,
        max_response_bytes: int = MAX_RESPONSE_BYTES,
    ) -> None:
        if (
            not isinstance(timeout_seconds, (int, float))
            or isinstance(timeout_seconds, bool)
            or timeout_seconds <= 0
            or timeout_seconds > 86_400
        ):
            raise ValueError("timeout_seconds must be between zero and one day")
        if (
            not isinstance(termination_grace_seconds, (int, float))
            or isinstance(termination_grace_seconds, bool)
            or termination_grace_seconds <= 0
            or termination_grace_seconds > 10
        ):
            raise ValueError("termination grace must be between zero and ten seconds")
        if (
            not isinstance(max_response_bytes, int)
            or isinstance(max_response_bytes, bool)
            or not 1 <= max_response_bytes <= 32 * 1024 * 1024
        ):
            raise ValueError("response limit must be between 1 byte and 32 MiB")
        self._max_response_bytes = max_response_bytes
        if use_bubblewrap not in {True, False, None}:
            raise TypeError("use_bubblewrap must be true, false, or None")

        command = tuple(worker_command) if worker_command is not None else None
        if command is not None and (
            not command
            or any(not isinstance(part, str) or not part or "\x00" in part for part in command)
        ):
            raise ValueError("worker command must contain bounded argument strings")

        self._progress = progress
        self._timeout_seconds = float(timeout_seconds)
        self._limits = limits or ResourceLimits()
        self._use_bubblewrap = use_bubblewrap
        self._worker_command = command
        self._termination_grace_seconds = float(termination_grace_seconds)
        self._run_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._cancel_event = threading.Event()
        self._active_process: subprocess.Popen[bytes] | None = None
        self._last_isolation_mode: IsolationMode = "process"

    @property
    def last_isolation_mode(self) -> IsolationMode:
        with self._state_lock:
            return self._last_isolation_mode

    def active_pid(self) -> int | None:
        with self._state_lock:
            process = self._active_process
            return None if process is None or process.poll() is not None else process.pid

    def cancel(self) -> bool:
        self._cancel_event.set()
        with self._state_lock:
            process = self._active_process
        if process is None or process.poll() is not None:
            return False
        self._terminate_process_group(process)
        return True

    def request_cancel(self) -> None:
        """Ask the exchange thread to stop; never wait from the GUI thread."""
        self._cancel_event.set()

    def run_job(self, job: JobRequest) -> JobResult:
        started = time.monotonic()
        request_id = uuid.uuid4().hex
        replacement_snapshot = None
        try:
            for path in (*job.input_files, job.output_dir):
                _require_encodable_path(path)
            job = _with_real_paths(job)
            if job.operation in STAGED_OUTPUT_OPERATIONS:
                options = job.options
                if not isinstance(
                    options,
                    (
                        CompressionOptions,
                        ProtectOptions,
                        UnlockOptions,
                        RemoveMetadataOptions,
                        PhotocopyOptions,
                        OcrOptions,
                        RedactOptions,
                        WatermarkOptions,
                    ),
                ):
                    raise ProtocolError("invalid staged output options")
                if (
                    isinstance(
                        options,
                        (ProtectOptions, UnlockOptions, RemoveMetadataOptions, PhotocopyOptions),
                    )
                    and options.replace_input
                ):
                    replacement_snapshot = snapshot_replacement_source(_replacement_target(job))
                else:
                    prepare_pdf_output_path(
                        options.output_path, job.input_files, allowed_dir=job.output_dir
                    )
            frame = encode_job_request(request_id, job)
            response = self._exchange(
                frame,
                action="structural_job",
                request_id=request_id,
                access=_access_for_job(job),
                staged_output_job=job if job.operation in STAGED_OUTPUT_OPERATIONS else None,
                staged_output_started=started,
                job_for_staging=job,
                replacement_snapshot=replacement_snapshot,
            )
            if not isinstance(response, JobResult):
                raise ProcessSupervisorError(
                    "worker_protocol_error",
                    "Le traitement PDF a renvoye un resultat invalide.",
                )
            if job.operation is not OperationType.COMPRESS_PDF and response.compression is not None:
                raise ProtocolError("unexpected compression metrics")
            return response
        except PdfModError as exc:
            return _job_failure(exc.technical_code, exc.user_message, started)
        except OSError:
            return _job_failure("output_write_error", OutputWriteError.user_message, started)
        except ProtocolError:
            return _job_failure(
                "worker_protocol_error",
                "La demande PDF locale est invalide.",
                started,
            )
        except ProcessSupervisorError as exc:
            return _job_failure(exc.code, exc.user_message, started)

    def get_page_count(self, pdf_path: Path) -> PageCountResponse:
        request_id = uuid.uuid4().hex
        _require_encodable_path(Path(pdf_path))
        try:
            frame = encode_path_request(request_id, "page_count", Path(pdf_path))
            response = self._exchange(
                frame,
                action="page_count",
                request_id=request_id,
                access=_access_for_path(Path(pdf_path)),
            )
        except ProtocolError as exc:
            raise ProcessSupervisorError(
                "worker_protocol_error",
                "Le comptage des pages a renvoye un resultat invalide.",
            ) from exc
        if not isinstance(response, PageCountResponse):
            raise ProcessSupervisorError(
                "worker_protocol_error",
                "Le comptage des pages a renvoye un resultat invalide.",
            )
        return response

    def inspect_document(self, pdf_path: Path) -> DocumentInspection:
        request_id = uuid.uuid4().hex
        _require_encodable_path(Path(pdf_path))
        try:
            frame = encode_path_request(request_id, "inspect_document", Path(pdf_path))
            response = self._exchange(
                frame,
                action="inspect_document",
                request_id=request_id,
                access=_access_for_path(Path(pdf_path)),
            )
        except ProtocolError as exc:
            raise ProcessSupervisorError(
                "worker_protocol_error",
                "L'inspection PDF a renvoye un resultat invalide.",
            ) from exc
        if not isinstance(response, InspectionResponse):
            raise ProcessSupervisorError(
                "worker_protocol_error",
                "L'inspection PDF a renvoye un resultat invalide.",
            )
        return response.inspection

    def inspect_share(self, pdf_path: Path) -> ShareInspection:
        request_id = uuid.uuid4().hex
        _require_encodable_path(pdf_path)
        try:
            response = self._exchange(
                encode_path_request(request_id, "inspect_share", pdf_path),
                action="inspect_share",
                request_id=request_id,
                access=_access_for_path(pdf_path),
            )
        except ProtocolError:
            raise ProcessSupervisorError("worker_protocol_error", "Analyse indisponible.") from None
        if not isinstance(response, ShareInspection):
            raise ProcessSupervisorError("worker_protocol_error", "Analyse indisponible.")
        return response

    def _exchange(
        self,
        frame: bytes,
        *,
        action: WorkerAction,
        request_id: str,
        access: _SandboxAccess,
        staged_output_job: JobRequest | None = None,
        staged_output_started: float = 0.0,
        job_for_staging: JobRequest | None = None,
        replacement_snapshot: os.stat_result | None = None,
    ) -> JobResult | PageCountResponse | InspectionResponse | ShareInspection:
        if not self._run_lock.acquire(blocking=False):
            raise RuntimeError("this process supervisor is already running")
        try:
            if self._cancel_event.is_set():
                raise ProcessSupervisorError(
                    "user_cancelled",
                    UserCancelledError.user_message,
                )
            # Landlock opens every input before confinement: without this check a
            # missing file made the worker exit 78, reported as missing isolation (#315).
            if any(not Path(path).is_file() for path in access.read_paths):
                raise ProcessSupervisorError("input_path_error", InputPathError.user_message)
            with tempfile.TemporaryDirectory(prefix="priveopdf-worker-") as temp_name:
                temp_dir = Path(temp_name)
                temp_dir.chmod(0o700)
                render_job = (
                    staged_output_job is not None
                    and staged_output_job.operation in RENDERING_OPERATIONS
                    and self._use_bubblewrap is not False
                )
                document_namespace = _document_namespace_verified()
                # AppArmor may prohibit nested namespaces. Ordinary workers in
                # the launcher restrict themselves with Landlock + seccomp.
                local_confinement = self._local_confinement_enabled()
                use_bwrap = self._bubblewrap_enabled()
                if render_job and not local_confinement:
                    # The memory scope needs the manager bus outside the worker.
                    # Bubblewrap hides that bus and confines files; its private
                    # /tmp replaces the host paths of the Landlock profile.
                    executable = shutil.which("bwrap")
                    if not executable or not _bubblewrap_works(executable):
                        raise _network_isolation_unavailable()
                    use_bwrap = True
                    local_confinement = False
                # /tmp is the deliberate in-sandbox mount point; the host path is
                # the freshly-created private directory above.
                visible_temp = Path("/tmp") if use_bwrap else temp_dir  # noqa: S108
                if staged_output_job is not None:
                    candidate_path = visible_temp / "candidate.pdf"
                    options = staged_output_job.options
                    if not isinstance(
                        options,
                        (
                            CompressionOptions,
                            ProtectOptions,
                            UnlockOptions,
                            RemoveMetadataOptions,
                            PhotocopyOptions,
                            OcrOptions,
                            RedactOptions,
                            WatermarkOptions,
                        ),
                    ):
                        raise ProtocolError("invalid staged output options")
                    staged_options = replace(options, output_path=candidate_path)
                    if isinstance(
                        staged_options,
                        (ProtectOptions, UnlockOptions, RemoveMetadataOptions, PhotocopyOptions),
                    ):
                        staged_options = replace(staged_options, replace_input=False)
                    staged_job = JobRequest(
                        staged_output_job.operation,
                        staged_output_job.input_files,
                        visible_temp,
                        staged_options,
                        password=staged_output_job.password,
                    )
                    frame = encode_job_request(request_id, staged_job)
                    access = _SandboxAccess(access.read_paths, ())
                # Every mode writes into the private directory and publishes only
                # after the worker exited: a cancelled split leaves no file behind.
                multi_staged = job_for_staging is not None and staged_output_job is None
                if multi_staged and job_for_staging is not None:
                    staged_options = dict(job_for_staging.options)
                    selected_output = staged_options.get("output_path")
                    if isinstance(selected_output, Path):
                        prepare_pdf_output_path(
                            selected_output,
                            job_for_staging.input_files,
                            allowed_dir=job_for_staging.output_dir,
                        )
                        staged_options["output_path"] = visible_temp / selected_output.name
                    staged_job = replace(
                        job_for_staging, output_dir=visible_temp, options=staged_options
                    )
                    frame = encode_job_request(request_id, staged_job)
                    access = _SandboxAccess(access.read_paths, ())
                environment = _minimal_environment(visible_temp)
                if local_confinement:
                    environment[PROFILE_ENV] = _local_profile(access, temp_dir)
                    if render_job:
                        from priveopdf.workers.render_memory_broker import BROKER_ENV

                        endpoint = os.environ.get(BROKER_ENV)
                        if not endpoint:
                            raise ProcessSupervisorError(
                                "render_memory_unavailable", "Protection memoire indisponible."
                            )
                        environment[BROKER_ENV] = endpoint
                if document_namespace or use_bwrap:
                    environment["PRIVEOPDF_DOCUMENT_SANDBOX"] = "1"
                command = self._base_command(
                    _output_files_of(job_for_staging) if job_for_staging is not None else 1
                )
                if render_job:
                    command = (*command, "--render-memory")
                if use_bwrap:
                    command = _bubblewrap_command(
                        command,
                        environment=environment,
                        access=access,
                        private_temp=temp_dir,
                        render_memory=render_job,
                    )
                if render_job and not local_confinement:
                    from priveopdf.workers.render_memory import scope_command

                    try:
                        command = scope_command(command, self._limits.memory_bytes)
                    except OSError:
                        raise ProcessSupervisorError(
                            "render_memory_unavailable",
                            "La protection memoire du rendu est indisponible.",
                        ) from None
                    runtime = f"/run/user/{os.getuid()}"
                    environment["XDG_RUNTIME_DIR"] = runtime
                    environment["DBUS_SESSION_BUS_ADDRESS"] = "unix:path=" + runtime + "/bus"
                with self._state_lock:
                    self._last_isolation_mode = (
                        "landlock"
                        if local_confinement
                        else ("bubblewrap" if use_bwrap else "process")
                    )
                output, return_code = self._run_process(
                    command,
                    frame,
                    environment=environment,
                    working_dir=temp_dir,
                )
                if self._cancel_event.is_set():
                    raise ProcessSupervisorError(
                        "user_cancelled",
                        UserCancelledError.user_message,
                    )
                if return_code == 78:
                    raise _network_isolation_unavailable()
                if return_code == 79 and render_job:
                    raise ProcessSupervisorError(
                        "render_memory_unavailable", "Protection memoire indisponible."
                    )
                if return_code != 0:
                    raise ProcessSupervisorError(
                        "render_memory_or_worker_failed" if render_job else "worker_crashed",
                        "Le traitement PDF isole s'est interrompu.",
                    )
                if not output:
                    raise ProcessSupervisorError(
                        "worker_protocol_error",
                        "Le traitement PDF a renvoye un resultat invalide.",
                    )
                try:
                    response = decode_response(
                        output,
                        expected_request_id=request_id,
                        expected_action=action,
                    )
                except ProtocolError as exc:
                    raise ProcessSupervisorError(
                        "worker_protocol_error",
                        "Le traitement PDF a renvoye un resultat invalide.",
                    ) from exc
                if staged_output_job is not None:
                    if not isinstance(response, JobResult):
                        raise ProtocolError("invalid staged output response")
                    return self._publish_staged_output(
                        staged_output_job,
                        response,
                        candidate_path,
                        temp_dir / "candidate.pdf",
                        staged_output_started,
                        replacement_snapshot,
                    )
                if multi_staged and job_for_staging is not None:
                    if not isinstance(response, JobResult):
                        raise ProtocolError("invalid staged response")
                    response = _host_outputs(response, visible_temp, temp_dir)
                    return self._publish_structural_outputs(
                        job_for_staging, response, temp_dir, staged_output_started
                    )
                return response
        finally:
            self._cancel_event.clear()
            self._run_lock.release()

    def _publish_structural_outputs(
        self, job: JobRequest, result: JobResult, private: Path, started: float
    ) -> JobResult:
        """Publish bounded new files after the restricted process has exited."""
        if not result.success:
            return result
        expected = 1
        if isinstance(job.options, SplitOptions):
            expected = len(job.options.ranges or job.options.page_groups or ())
        if len(result.output_files) != expected or result.warnings:
            raise ProtocolError("invalid staged output count")
        if len(set(result.output_files)) != expected:
            raise ProtocolError("duplicate staged outputs")
        if isinstance(job.options, SplitOptions):
            # F06: the worker writes exactly the names the domain announced;
            # anything else is refused before any file is published.
            # Same derivation as the engine (`facture: 2024 .pdf` -> `facture_ 2024`).
            base = job.options.base_name or portable_filename_stem(job.input_files[0].stem)
            wanted = (
                split_range_file_names(base, tuple(r.label for r in job.options.ranges))
                if job.options.ranges
                else split_group_file_names(base, len(job.options.page_groups or ()))
            )
            if tuple(candidate.name for candidate in result.output_files) != wanted:
                raise ProtocolError("unexpected output name")
        explicit = job.options.get("output_path")
        published = []
        total = 0
        try:
            for candidate in result.output_files:
                if candidate.parent != private or candidate.suffix.lower() != ".pdf":
                    raise ProtocolError("invalid staged output path")
                if isinstance(explicit, Path) and candidate.name != explicit.name:
                    raise ProtocolError("unexpected output name")
                target = explicit if isinstance(explicit, Path) else job.output_dir / candidate.name
                prepare_pdf_output_path(target, job.input_files, allowed_dir=job.output_dir)
                fd = os.open(candidate, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
                with os.fdopen(fd, "rb") as source:
                    info = os.fstat(source.fileno())
                    if (
                        not stat.S_ISREG(info.st_mode)
                        or info.st_nlink != 1
                        or not 0 < info.st_size <= self._limits.file_size_bytes
                    ):
                        raise ProtocolError("invalid staged output file")
                    total += info.st_size
                    if total > self._limits.file_size_bytes:
                        raise ProtocolError("staged outputs exceed size limit")

                    def copy(stream: BinaryIO, expected_size: int = info.st_size) -> None:
                        copied = 0
                        while chunk := source.read(1024 * 1024):
                            if self._cancel_event.is_set():
                                raise ProcessSupervisorError(
                                    "user_cancelled", UserCancelledError.user_message
                                )
                            if time.monotonic() - started >= self._timeout_seconds:
                                raise ProcessSupervisorError(
                                    "worker_timeout",
                                    "Le traitement PDF a depasse le temps autorise.",
                                )
                            copied += len(chunk)
                            if copied > expected_size:
                                raise ProtocolError("staged output changed")
                            stream.write(chunk)
                        if copied != expected_size:
                            raise ProtocolError("staged output changed")

                    published.append(
                        atomic_write_no_replace_tracked(
                            target, copy, job.input_files, required_suffix=".pdf"
                        )
                    )
            if self._cancel_event.is_set():
                raise ProcessSupervisorError("user_cancelled", UserCancelledError.user_message)
            return replace(
                result,
                output_files=tuple(p.path for p in published),
                duration_ms=int((time.monotonic() - started) * 1000),
            )
        except BaseException:
            for output in reversed(published):
                if output.matches_current_entry():
                    output.path.unlink(missing_ok=True)
            raise
        finally:
            for output in published:
                output.close()

    def _publish_staged_output(
        self,
        job: JobRequest,
        result: JobResult,
        visible_candidate: Path,
        candidate: Path,
        started: float,
        replacement_snapshot: os.stat_result | None = None,
    ) -> JobResult:
        if not result.success:
            return replace(result, duration_ms=int((time.monotonic() - started) * 1000))
        if (
            result.output_files != (visible_candidate,)
            or (job.operation is OperationType.COMPRESS_PDF and result.compression is None)
            or (job.operation is not OperationType.COMPRESS_PDF and result.compression is not None)
            or not _valid_staged_warnings(job, result.warnings)
        ):
            raise ProtocolError("invalid staged output candidate")
        options = job.options
        if not isinstance(
            options,
            (
                CompressionOptions,
                ProtectOptions,
                UnlockOptions,
                RemoveMetadataOptions,
                PhotocopyOptions,
                OcrOptions,
                RedactOptions,
                WatermarkOptions,
            ),
        ):
            raise ProtocolError("invalid staged output options")
        replacing = (
            isinstance(
                options, (ProtectOptions, UnlockOptions, RemoveMetadataOptions, PhotocopyOptions)
            )
            and options.replace_input
        )
        if replacing:
            if replacement_snapshot is None:
                raise ProtocolError("replacement source snapshot missing")
            target = _replacement_target(job)
        else:
            target = prepare_pdf_output_path(
                options.output_path, job.input_files, allowed_dir=job.output_dir
            )

        def check_cancel() -> None:
            if self._cancel_event.is_set():
                raise ProcessSupervisorError("user_cancelled", UserCancelledError.user_message)
            if time.monotonic() - started >= self._timeout_seconds:
                raise ProcessSupervisorError(
                    "worker_timeout", "Le traitement PDF a depasse le temps autorise."
                )

        check_cancel()
        fd = os.open(candidate, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as source:
            info = os.fstat(source.fileno())
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_nlink != 1
                or info.st_size <= 0
                or (
                    result.compression is not None
                    and info.st_size != result.compression.candidate_bytes
                )
                or info.st_size > self._limits.file_size_bytes
            ):
                raise ProtocolError("invalid staged output candidate size or type")

            def copy_candidate(stream: BinaryIO) -> None:
                copied = 0
                while chunk := source.read(1024 * 1024):
                    check_cancel()
                    copied += len(chunk)
                    if copied > info.st_size:
                        raise ProtocolError("staged output candidate changed")
                    stream.write(chunk)
                check_cancel()
                if copied != info.st_size:
                    raise ProtocolError("staged output candidate changed")

            if replacing:
                if replacement_snapshot is None:
                    raise ProtocolError("replacement source snapshot missing")
                atomic_replace_source(target, copy_candidate, replacement_snapshot, check_cancel)
                return replace(
                    result,
                    output_files=(target,),
                    duration_ms=int((time.monotonic() - started) * 1000),
                )
            published = atomic_write_no_replace_tracked(
                target, copy_candidate, job.input_files, required_suffix=".pdf"
            )
        try:
            check_cancel()
            return replace(
                result, output_files=(target,), duration_ms=int((time.monotonic() - started) * 1000)
            )
        except BaseException:
            if published.matches_current_entry():
                published.path.unlink(missing_ok=True)
            raise
        finally:
            published.close()

    def _run_process(
        self,
        command: Sequence[str],
        request: bytes,
        *,
        environment: Mapping[str, str],
        working_dir: Path,
    ) -> tuple[bytes, int]:
        try:
            # `command` is assembled exclusively from the fixed worker entry point
            # and the validated bubblewrap profile in this module.
            process = subprocess.Popen(  # noqa: S603
                tuple(command),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                cwd=working_dir,
                env=dict(environment),
                close_fds=True,
                start_new_session=True,
            )
        except OSError as exc:
            raise ProcessSupervisorError(
                "worker_spawn_failed",
                "Le traitement PDF local ne peut pas demarrer.",
            ) from exc

        with self._state_lock:
            self._active_process = process
        try:
            if self._cancel_event.is_set():
                self._terminate_process_group(process)
                raise ProcessSupervisorError(
                    "user_cancelled",
                    UserCancelledError.user_message,
                )
            output = self._bounded_communicate(process, request)
            return_code = process.wait(timeout=self._termination_grace_seconds)
            return output, return_code
        finally:
            if process.poll() is None:
                self._terminate_process_group(process)
            _close_pipe(process.stdin)
            _close_pipe(process.stdout)
            with self._state_lock:
                if self._active_process is process:
                    self._active_process = None

    def _bounded_communicate(
        self,
        process: subprocess.Popen[bytes],
        request: bytes,
    ) -> bytes:
        if process.stdin is None or process.stdout is None:
            raise ProcessSupervisorError(
                "worker_spawn_failed",
                "Le traitement PDF local ne peut pas demarrer.",
            )
        if os.name == "nt":
            return self._bounded_communicate_threaded(process, request)

        selector = selectors.DefaultSelector()
        stdin_fd = process.stdin.fileno()
        stdout_fd = process.stdout.fileno()
        os.set_blocking(stdin_fd, False)
        os.set_blocking(stdout_fd, False)
        selector.register(stdin_fd, selectors.EVENT_WRITE, "stdin")
        selector.register(stdout_fd, selectors.EVENT_READ, "stdout")
        request_view = memoryview(request)
        request_offset = 0
        output = bytearray()
        progress_frames = ProgressFrames(self._progress)
        stdout_open = True
        deadline = time.monotonic() + self._timeout_seconds

        try:
            while stdout_open or process.poll() is None:
                if self._cancel_event.is_set():
                    self._terminate_process_group(process)
                    raise ProcessSupervisorError(
                        "user_cancelled",
                        UserCancelledError.user_message,
                    )
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self._terminate_process_group(process)
                    raise ProcessSupervisorError(
                        "worker_timeout",
                        "Le traitement PDF a depasse le temps autorise.",
                    )

                if not selector.get_map():
                    time.sleep(min(0.02, remaining))
                    continue
                events = selector.select(timeout=min(0.05, remaining))
                for key, _mask in events:
                    if key.data == "stdin":
                        try:
                            written = os.write(stdin_fd, request_view[request_offset:])
                        except (BrokenPipeError, OSError):
                            written = 0
                            request_offset = len(request_view)
                        else:
                            request_offset += written
                        if request_offset >= len(request_view):
                            _selector_unregister(selector, stdin_fd)
                            _close_pipe(process.stdin)
                    else:
                        try:
                            chunk = os.read(stdout_fd, 64 * 1024)
                        except BlockingIOError:
                            continue
                        if not chunk:
                            stdout_open = False
                            _selector_unregister(selector, stdout_fd)
                            continue
                        if len(output) + len(chunk) > self._max_response_bytes:
                            self._terminate_process_group(process)
                            raise ProcessSupervisorError(
                                "worker_response_too_large",
                                "Le traitement PDF a renvoye trop de donnees.",
                            )
                        output.extend(chunk)
                        progress_frames.consume(output)
        finally:
            selector.close()
            request_view.release()
        return bytes(output)

    def _bounded_communicate_threaded(
        self,
        process: subprocess.Popen[bytes],
        request: bytes,
    ) -> bytes:
        """Bound pipe I/O where selectors cannot monitor subprocess pipes."""
        stdin = process.stdin
        stdout = process.stdout
        if stdin is None or stdout is None:
            raise ProcessSupervisorError(
                "worker_spawn_failed",
                "Le traitement PDF local ne peut pas demarrer.",
            )

        output = bytearray()
        progress_frames = ProgressFrames(self._progress)
        overflow = threading.Event()
        read_error: list[OSError] = []

        def write_request() -> None:
            try:
                stdin.write(request)
                stdin.flush()
            except (BrokenPipeError, OSError):
                pass
            finally:
                _close_pipe(stdin)

        def read_response() -> None:
            try:
                while True:
                    chunk = stdout.read(64 * 1024)
                    if not chunk:
                        return
                    if len(output) + len(chunk) > self._max_response_bytes:
                        overflow.set()
                        return
                    output.extend(chunk)
                    progress_frames.consume(output)
            except OSError as exc:
                read_error.append(exc)

        writer = threading.Thread(target=write_request, daemon=True)
        reader = threading.Thread(target=read_response, daemon=True)
        writer.start()
        reader.start()
        deadline = time.monotonic() + self._timeout_seconds

        while reader.is_alive() or process.poll() is None:
            if overflow.is_set():
                self._terminate_process_group(process)
                reader.join(timeout=self._termination_grace_seconds)
                raise ProcessSupervisorError(
                    "worker_response_too_large",
                    "Le traitement PDF a renvoye trop de donnees.",
                )
            if self._cancel_event.is_set():
                self._terminate_process_group(process)
                reader.join(timeout=self._termination_grace_seconds)
                raise ProcessSupervisorError(
                    "user_cancelled",
                    UserCancelledError.user_message,
                )
            if time.monotonic() >= deadline:
                self._terminate_process_group(process)
                reader.join(timeout=self._termination_grace_seconds)
                raise ProcessSupervisorError(
                    "worker_timeout",
                    "Le traitement PDF a depasse le temps autorise.",
                )
            time.sleep(0.01)

        writer.join(timeout=self._termination_grace_seconds)
        reader.join(timeout=self._termination_grace_seconds)
        if read_error and process.returncode == 0:
            raise ProcessSupervisorError(
                "worker_protocol_error",
                "Le traitement PDF a renvoye un resultat invalide.",
            )
        return bytes(output)

    def _terminate_process_group(self, process: subprocess.Popen[bytes]) -> None:
        if process.poll() is not None:
            return
        _signal_process_group(process, signal.SIGTERM)
        try:
            process.wait(timeout=self._termination_grace_seconds)
            return
        except subprocess.TimeoutExpired:
            pass
        if os.name == "posix":
            _signal_process_group(process, signal.SIGKILL)
        else:
            with suppress(OSError):
                process.kill()
        try:
            process.wait(timeout=self._termination_grace_seconds)
        except subprocess.TimeoutExpired:
            process.kill()
            with suppress(subprocess.TimeoutExpired):
                process.wait(timeout=self._termination_grace_seconds)

    def _base_command(self, output_files: int = 1) -> tuple[str, ...]:
        if self._worker_command is not None:
            return self._worker_command
        limits = self._limits
        # Each published output keeps one tracking descriptor until the job ends
        # (rollback by identity): a split into many files needs that many.
        if output_files > 1:
            limits = replace(limits, open_files=min(limits.open_files + output_files, 4096))
        if getattr(sys, "frozen", False):
            return (sys.executable, "--pdf-worker", *limits.command_arguments())
        return (
            sys.executable,
            "-P",
            "-m",
            "priveopdf.workers.pdf_worker",
            *limits.command_arguments(),
        )

    def _local_confinement_enabled(self) -> bool:
        return (
            self._use_bubblewrap is not False
            and self._worker_command is None
            and not _unsandboxed_development_allowed()
            and _document_namespace_verified()
        )

    def _bubblewrap_enabled(self) -> bool:
        if self._local_confinement_enabled():
            return False
        if self._use_bubblewrap is False:
            return False
        if self._use_bubblewrap is None and _unsandboxed_development_allowed():
            return False
        if self._worker_command is not None:
            raise _network_isolation_unavailable()
        executable = shutil.which("bwrap")
        available = executable is not None and _bubblewrap_works(executable)
        if available:
            return True
        # F02 / CA6: on every platform, no isolation means no processing; the
        # unisolated mode needs the explicit development choice checked above.
        raise _network_isolation_unavailable()


def run_structural_job(job: JobRequest) -> JobResult:
    """Drop-in isolated equivalent used by the existing Qt JobWorker contract."""

    return ProcessSupervisor().run_job(job)


def _job_failure(
    technical_code: str,
    user_message: str,
    started: float,
) -> JobResult:
    return JobResult(
        success=False,
        output_files=(),
        warnings=(),
        user_message=user_message,
        technical_detail=technical_code,
        duration_ms=max(0, int((time.monotonic() - started) * 1000)),
    )


def _access_for_job(job: JobRequest) -> _SandboxAccess:
    write_dirs = {job.output_dir}
    output_path = job.options.get("output_path")
    if isinstance(output_path, Path):
        write_dirs.add(output_path.parent)
    return _SandboxAccess(
        read_paths=job.input_files,
        write_dirs=tuple(sorted(write_dirs, key=str)),
    )


def _valid_staged_warnings(job: JobRequest, warnings: tuple[str, ...]) -> bool:
    """OCR announces exactly its three page counts, redaction its verified areas
    and pages, the watermark its marked pages; any other staged job announces none."""

    if isinstance(job.options, WatermarkOptions):
        return len(warnings) == 1 and bool(
            re.fullmatch(r"watermark_pages_([1-9][0-9]{0,2})", warnings[0])
        )
    if isinstance(job.options, RedactOptions):
        expected_pages = len({area[0] for area in job.options.areas})
        return warnings == (
            f"redaction_areas_{len(job.options.areas)}",
            f"redaction_pages_{expected_pages}",
        )
    if not isinstance(job.options, OcrOptions):
        return not warnings
    if len(warnings) != len(OCR_STATE_PREFIXES):
        return False
    counts: list[int] = []
    for prefix, warning in zip(OCR_STATE_PREFIXES, warnings, strict=True):
        match = re.fullmatch(rf"{prefix}(0|[1-9][0-9]{{0,3}})", warning)
        if match is None:
            return False
        counts.append(int(match.group(1)))
    recognized, _text_present, no_text = counts
    # With a page choice (OCR10), no more pages than chosen can have been touched.
    chosen = len(job.options.page_numbers) or OCR_MAX_DOCUMENT_PAGES
    return (
        1 <= recognized <= OCR_MAX_SCANNED_PAGES
        and recognized + no_text <= min(OCR_MAX_SCANNED_PAGES, chosen)
        and sum(counts) <= OCR_MAX_DOCUMENT_PAGES
    )


def _with_real_paths(job: JobRequest) -> JobRequest:
    """Symbolic links are followed before the worker sees the job: the engines open
    sources with O_NOFOLLOW and the sandbox mounts the real directory, so a link
    kept in the request would be refused (sources) or written into a tmpfs that
    vanishes with the sandbox (outputs). Identity checks run on the real paths."""

    try:
        input_files = tuple(path.resolve(strict=True) for path in job.input_files)
        output_dir = job.output_dir.resolve(strict=False)
        options = dict(job.options)
        output_path = options.get("output_path")
        if isinstance(output_path, Path):
            options["output_path"] = output_path.parent.resolve(strict=False) / output_path.name
    except OSError:
        raise ProcessSupervisorError("input_path_error", InputPathError.user_message) from None
    if (
        input_files == job.input_files
        and output_dir == job.output_dir
        and options == dict(job.options)
    ):
        return job
    return replace(job, input_files=input_files, output_dir=output_dir, options=options)


def _require_encodable_path(path: Path) -> None:
    """A name the protocol cannot carry (control characters, bytes outside UTF-8)
    is an unsupported file, reported as such rather than as a worker fault."""

    text = str(path)
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        raise ProcessSupervisorError("input_path_error", InputPathError.user_message) from None
    if any(character in text for character in "\x00\r\n"):
        raise ProcessSupervisorError("input_path_error", InputPathError.user_message)


def _access_for_path(path: Path) -> _SandboxAccess:
    return _SandboxAccess(read_paths=(path,), write_dirs=())


def _minimal_environment(temp_dir: Path) -> dict[str, str]:
    return {
        "HOME": str(temp_dir),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        # OpenMP in libtesseract: CPU time stays within twice the wall time.
        "OMP_THREAD_LIMIT": "2",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONPATH": str(_SOURCE_ROOT),
        "PYTHONUNBUFFERED": "1",
        "TMPDIR": str(temp_dir),
        "TEMP": str(temp_dir),
        "TMP": str(temp_dir),
        "XDG_CACHE_HOME": str(temp_dir / "cache"),
        "XDG_CONFIG_HOME": str(temp_dir / "config"),
        "XDG_DATA_HOME": str(temp_dir / "data"),
        "XDG_STATE_HOME": str(temp_dir / "state"),
    }


def _bubblewrap_works(executable: str) -> bool:
    with _BWRAP_PROBE_LOCK:
        cached = _BWRAP_PROBE_CACHE.get(executable)
        if cached is not None:
            return cached
        try:
            with tempfile.TemporaryDirectory(prefix="priveopdf-bwrap-probe-") as temp_name:
                private_temp = Path(temp_name)
                private_temp.chmod(0o700)
                environment = _minimal_environment(Path("/tmp"))  # noqa: S108
                command = _bubblewrap_command(
                    ("/bin/true",),
                    environment=environment,
                    access=_SandboxAccess((), ()),
                    private_temp=private_temp,
                    executable=executable,
                )
                # The executable comes from shutil.which("bwrap"); all remaining
                # arguments are assembled by the production sandbox profile.
                completed = subprocess.run(  # noqa: S603
                    command,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    cwd=private_temp,
                    env=environment,
                    close_fds=True,
                    start_new_session=True,
                    timeout=2,
                    check=False,
                )
            available = completed.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            available = False
        _BWRAP_PROBE_CACHE[executable] = available
        return available


def _bubblewrap_command(
    command: Sequence[str],
    *,
    environment: Mapping[str, str],
    access: _SandboxAccess,
    private_temp: Path,
    executable: str | None = None,
    render_memory: bool = False,
) -> tuple[str, ...]:
    resolved_executable = executable or shutil.which("bwrap")
    if resolved_executable is None:
        raise _network_isolation_unavailable()

    arguments: list[str] = [
        resolved_executable,
        "--die-with-parent",
        "--unshare-net",
        "--unshare-pid",
        "--unshare-ipc",
        "--unshare-uts",
        "--proc",
        "/proc",
        "--dev",
        "/dev",
        "--bind",
        str(private_temp),
        "/tmp",  # noqa: S108 - deliberate private mount point inside bubblewrap
        "--chdir",
        "/tmp",  # noqa: S108 - same private in-sandbox working directory
        "--clearenv",
    ]
    for key, value in sorted(environment.items()):
        arguments.extend(("--setenv", key, value))

    for path in _runtime_read_roots():
        arguments.extend(("--ro-bind", str(path), str(path)))
    for path in _existing_directories(access.write_dirs):
        arguments.extend(("--bind", str(path), str(path)))
    for path in _existing_files(access.read_paths):
        arguments.extend(("--ro-bind", str(path), str(path)))
    if render_memory:
        if Path("/etc/fonts").is_dir():
            arguments.extend(("--ro-bind", "/etc/fonts", "/etc/fonts"))
        arguments.extend(
            ("--unshare-pid", "--cap-drop", "ALL", "--ro-bind", "/sys/fs/cgroup", "/sys/fs/cgroup")
        )
    arguments.append("--")
    arguments.extend(command)
    return tuple(arguments)


def _host_outputs(result: JobResult, visible: Path, private: Path) -> JobResult:
    """Worker paths (`/tmp` under bubblewrap) as host paths of the private directory."""

    if visible == private or not result.success:
        return result
    for path in result.output_files:
        if path.parent != visible:
            raise ProtocolError("invalid staged output path")
    return replace(result, output_files=tuple(private / path.name for path in result.output_files))


def _output_files_of(job: JobRequest) -> int:
    """Files a job publishes: one, or one per split plan entry."""

    options = job.options
    if isinstance(options, SplitOptions):
        plan = options.ranges if options.ranges is not None else options.page_groups
        return len(plan or ())
    return 1


def _network_isolation_unavailable() -> ProcessSupervisorError:
    return ProcessSupervisorError(
        "network_isolation_unavailable",
        "L'isolation réseau obligatoire est indisponible. Aucun document n'a été traité.",
    )


def _document_namespace_verified() -> bool:
    return document_namespace_verified(_PROC_NET_DEV)


def _unsandboxed_development_allowed() -> bool:
    """The explicit development choice; never honoured by a frozen build (F03)."""
    if getattr(sys, "frozen", False):
        return False
    return os.environ.get("PRIVEOPDF_ALLOW_UNSANDBOXED_DEV") == "1"


def _existing_directories(paths: Sequence[Path]) -> tuple[Path, ...]:
    return tuple(
        sorted(
            {Path(path).resolve() for path in paths if Path(path).is_dir()},
            key=str,
        )
    )


def _existing_files(paths: Sequence[Path]) -> tuple[Path, ...]:
    return tuple(
        sorted(
            {Path(path).absolute() for path in paths if Path(path).is_file()},
            key=str,
        )
    )


def _selector_unregister(selector: selectors.BaseSelector, file_descriptor: int) -> None:
    with suppress(KeyError, ValueError):
        selector.unregister(file_descriptor)


def _close_pipe(pipe: object) -> None:
    if pipe is None:
        return
    close = getattr(pipe, "close", None)
    if not callable(close):
        return
    with suppress(OSError):
        close()


def _signal_process_group(process: subprocess.Popen[bytes], sig: int) -> None:
    if process.poll() is not None:
        return
    if os.name == "posix":
        try:
            os.killpg(process.pid, sig)
            return
        except (OSError, ProcessLookupError):
            pass
    try:
        force_signal = getattr(signal, "SIGKILL", None)
        if force_signal is not None and sig == force_signal:
            process.kill()
        else:
            process.terminate()
    except OSError:
        pass


def _replacement_target(job: JobRequest) -> Path:
    options = job.options
    if (
        not isinstance(
            options, (ProtectOptions, UnlockOptions, RemoveMetadataOptions, PhotocopyOptions)
        )
        or not options.replace_input
        or len(job.input_files) != 1
        or options.output_path.absolute() != job.input_files[0].absolute()
        or options.output_path.parent.resolve(strict=True) != job.output_dir.resolve(strict=True)
    ):
        raise DangerousOutputError()
    return options.output_path.parent.resolve(strict=True) / options.output_path.name


def _local_profile(access: _SandboxAccess, private: Path) -> str:
    if access.write_dirs:
        raise ValueError("Landlock workers must stage all outputs privately")
    return json.dumps(
        {"read": [str(p.absolute()) for p in access.read_paths], "private": str(private.absolute())}
    )
