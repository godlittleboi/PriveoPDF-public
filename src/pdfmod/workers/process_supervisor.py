"""Fail-closed local PDF process isolation for the qualified Linux path."""

from __future__ import annotations

import os
import selectors
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from collections.abc import Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pdfmod.domain.errors import UserCancelledError
from pdfmod.domain.jobs import JobRequest, JobResult
from pdfmod.engine.document_inspection import DocumentInspection
from pdfmod.workers.pdf_protocol import (
    MAX_RESPONSE_BYTES,
    InspectionResponse,
    PageCountResponse,
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

IsolationMode = Literal["process", "bubblewrap", "document_namespace"]


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
        if use_bubblewrap not in {True, False, None}:
            raise TypeError("use_bubblewrap must be true, false, or None")

        command = tuple(worker_command) if worker_command is not None else None
        if command is not None and (
            not command
            or any(not isinstance(part, str) or not part or "\x00" in part for part in command)
        ):
            raise ValueError("worker command must contain bounded argument strings")

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

    def run_job(self, job: JobRequest) -> JobResult:
        started = time.monotonic()
        request_id = uuid.uuid4().hex
        try:
            frame = encode_job_request(request_id, job)
            response = self._exchange(
                frame,
                action="structural_job",
                request_id=request_id,
                access=_access_for_job(job),
            )
            if not isinstance(response, JobResult):
                raise ProcessSupervisorError(
                    "worker_protocol_error",
                    "Le traitement PDF a renvoye un resultat invalide.",
                )
            return response
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

    def _exchange(
        self,
        frame: bytes,
        *,
        action: WorkerAction,
        request_id: str,
        access: _SandboxAccess,
    ) -> JobResult | PageCountResponse | InspectionResponse:
        if not self._run_lock.acquire(blocking=False):
            raise RuntimeError("this process supervisor is already running")
        try:
            if self._cancel_event.is_set():
                raise ProcessSupervisorError(
                    "user_cancelled",
                    UserCancelledError.user_message,
                )
            with tempfile.TemporaryDirectory(prefix="priveopdf-worker-") as temp_name:
                temp_dir = Path(temp_name)
                temp_dir.chmod(0o700)
                document_namespace = _document_namespace_verified()
                use_bwrap = False if document_namespace else self._bubblewrap_enabled()
                # /tmp is the deliberate in-sandbox mount point; the host path is
                # the freshly-created private directory above.
                visible_temp = Path("/tmp") if use_bwrap else temp_dir  # noqa: S108
                environment = _minimal_environment(visible_temp)
                command = self._base_command()
                if use_bwrap:
                    command = _bubblewrap_command(
                        command,
                        environment=environment,
                        access=access,
                        private_temp=temp_dir,
                    )
                with self._state_lock:
                    self._last_isolation_mode = (
                        "document_namespace"
                        if document_namespace
                        else "bubblewrap"
                        if use_bwrap
                        else "process"
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
            if return_code != 0:
                raise ProcessSupervisorError(
                    "worker_crashed",
                    "Le traitement PDF isole s'est interrompu.",
                )
            if not output:
                raise ProcessSupervisorError(
                    "worker_protocol_error",
                    "Le traitement PDF a renvoye un resultat invalide.",
                )
            try:
                return decode_response(
                    output,
                    expected_request_id=request_id,
                    expected_action=action,
                )
            except ProtocolError as exc:
                raise ProcessSupervisorError(
                    "worker_protocol_error",
                    "Le traitement PDF a renvoye un resultat invalide.",
                ) from exc
        finally:
            self._cancel_event.clear()
            self._run_lock.release()

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
                        if len(output) + len(chunk) > MAX_RESPONSE_BYTES:
                            self._terminate_process_group(process)
                            raise ProcessSupervisorError(
                                "worker_response_too_large",
                                "Le traitement PDF a renvoye trop de donnees.",
                            )
                        output.extend(chunk)
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
                    if len(output) + len(chunk) > MAX_RESPONSE_BYTES:
                        overflow.set()
                        return
                    output.extend(chunk)
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

    def _base_command(self) -> tuple[str, ...]:
        if self._worker_command is not None:
            return self._worker_command
        return (
            sys.executable,
            "-P",
            "-m",
            "pdfmod.workers.pdf_worker",
            *self._limits.command_arguments(),
        )

    def _bubblewrap_enabled(self) -> bool:
        if self._use_bubblewrap is False:
            return False
        if self._use_bubblewrap is None and _unsandboxed_development_allowed():
            return False
        if self._worker_command is not None:
            if self._use_bubblewrap is True or sys.platform.startswith("linux"):
                raise _network_isolation_unavailable()
            return False
        executable = shutil.which("bwrap")
        available = executable is not None and _bubblewrap_works(executable)
        if available:
            return True
        if self._use_bubblewrap is True or sys.platform.startswith("linux"):
            raise _network_isolation_unavailable()
        return False


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


def _access_for_path(path: Path) -> _SandboxAccess:
    return _SandboxAccess(read_paths=(path,), write_dirs=())


def _minimal_environment(temp_dir: Path) -> dict[str, str]:
    return {
        "HOME": str(temp_dir),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
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
) -> tuple[str, ...]:
    resolved_executable = executable or shutil.which("bwrap")
    if resolved_executable is None:
        raise _network_isolation_unavailable()

    arguments: list[str] = [
        resolved_executable,
        "--die-with-parent",
        "--unshare-net",
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
    arguments.append("--")
    arguments.extend(command)
    return tuple(arguments)


def _network_isolation_unavailable() -> ProcessSupervisorError:
    return ProcessSupervisorError(
        "network_isolation_unavailable",
        "L'isolation réseau obligatoire est indisponible. Aucun document n'a été traité.",
    )


def _document_namespace_verified() -> bool:
    if os.environ.get("PRIVEOPDF_DOCUMENT_SANDBOX") != "1":
        return False
    if not sys.platform.startswith("linux"):
        return False
    try:
        lines = _PROC_NET_DEV.read_text(encoding="utf-8").splitlines()
    except OSError:
        return False
    interfaces: set[str] = set()
    for line in lines[2:]:
        if not line.strip():
            continue
        name, separator, _statistics = line.partition(":")
        interface = name.strip()
        if not separator or not interface:
            return False
        interfaces.add(interface)
    return bool(interfaces) and interfaces <= {"lo"}


def _unsandboxed_development_allowed() -> bool:
    return os.environ.get("PRIVEOPDF_ALLOW_UNSANDBOXED_DEV") == "1"


def _runtime_read_roots() -> tuple[Path, ...]:
    candidates = {
        _SOURCE_ROOT,
        Path(sys.base_prefix).resolve(),
        Path(sys.prefix).resolve(),
        Path(sys.executable).resolve().parent,
    }
    for path_text in ("/usr", "/lib", "/lib64", "/bin"):
        path = Path(path_text)
        if path.exists():
            candidates.add(path.absolute())
    return _remove_nested_paths(candidates)


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


def _remove_nested_paths(paths: set[Path]) -> tuple[Path, ...]:
    ordered = sorted(paths, key=lambda path: (len(path.parts), str(path)))
    result: list[Path] = []
    for path in ordered:
        if any(path == parent or parent in path.parents for parent in result):
            continue
        result.append(path)
    return tuple(result)


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
