from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import secrets
import shutil
import subprocess
import sys
import threading
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from pdfmod.app.beta_versions import (
    BetaVersion,
    current_beta_version,
    isolated_beta_environment,
)

DIAGNOSTIC_SESSION_ENV = "PRIVEOPDF_DIAGNOSTIC_SESSION_DIR"
DIAGNOSTIC_ACTIVE_ENV = "PRIVEOPDF_DIAGNOSTIC_ACTIVE"
REPORT_SCHEMA_VERSION = 1
REPORT_ARCHIVE_MEMBERS = (
    "manifest.json",
    "session.json",
    "runtime.log",
    "events.jsonl",
    "README.txt",
)
MAX_LOG_BYTES = 512 * 1024
MAX_EVENTS = 100
MAX_SESSIONS = 5
MAX_JSON_BYTES = 128 * 1024
_SESSION_NAME_RE = re.compile(r"^session-[0-9]{8}T[0-9]{6}Z-[0-9a-f]{8}$")
_QUOTED_ABSOLUTE_PATH_RE = re.compile(r"([\"'])(?:[A-Za-z]:\\|/).*?\1")
_ABSOLUTE_UNIX_PATH_RE = re.compile(r"(?m)(?<![\w>])/(?!/)[^\r\n]*")
_ABSOLUTE_WINDOWS_PATH_RE = re.compile(r"(?m)(?<![\w])[A-Za-z]:\\[^\r\n]*")
_DOCUMENT_NAME_RE = re.compile(r"(?i)(?<![\w.-])[^\s/\\\"']+\.pdf(?![\w.-])")
_SECRET_RE = re.compile(
    r"(?i)\b(password|passwd|passphrase|pwd|mot[\s_-]*de[\s_-]*passe|token|secret)"
    r"\s*[:=]\s*[^\r\n]*"
)
_event_lock = threading.Lock()


class DiagnosticError(RuntimeError):
    """Raised when a private beta diagnostic cannot be created or exported."""


@dataclass(frozen=True)
class DiagnosticSession:
    path: Path
    started_at: datetime
    status: str
    exit_code: int | None

    @property
    def is_abnormal(self) -> bool:
        return self.status in {"crashed", "interrupted", "launch_failed"}


def _utc_now() -> datetime:
    return datetime.now(tz=UTC)


def _timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _private_directory(path: Path) -> None:
    if path.is_symlink():
        raise DiagnosticError("diagnostic directory cannot be a symbolic link")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink() or not path.is_dir():
        raise DiagnosticError("diagnostic directory is invalid")
    try:
        path.chmod(0o700)
    except OSError as error:
        raise DiagnosticError("diagnostic directory permissions unavailable") from error


def _write_private_json(path: Path, payload: object) -> None:
    _private_directory(path.parent)
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(4)}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
        path.chmod(0o600)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _read_json(path: Path) -> dict[str, object]:
    try:
        if path.stat().st_size > MAX_JSON_BYTES:
            raise DiagnosticError("diagnostic metadata is too large")
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DiagnosticError("diagnostic metadata is unavailable") from error
    if not isinstance(payload, dict):
        raise DiagnosticError("diagnostic metadata is invalid")
    return payload


def _diagnostics_root(version: BetaVersion) -> Path:
    return version.path / ".xdg" / "state" / "priveopdf" / "diagnostics"


def _validated_session_path(value: str, version: BetaVersion) -> Path:
    try:
        session_path = Path(value).resolve(strict=True)
        root = _diagnostics_root(version).resolve(strict=True)
    except OSError as error:
        raise DiagnosticError("diagnostic session is unavailable") from error
    if session_path.parent != root or not _SESSION_NAME_RE.fullmatch(session_path.name):
        raise DiagnosticError("diagnostic session path is invalid")
    return session_path


def _provenance(version: BetaVersion) -> dict[str, object]:
    metadata = _read_json(version.path / "PR_TEST_ARTIFACT.json")
    allowed = (
        "repository",
        "pull_request",
        "head_sha",
        "built_sha",
        "workflow",
        "workflow_path",
        "run_id",
        "run_attempt",
        "artifact_name",
        "archive_sha256",
    )
    return {key: metadata[key] for key in allowed if key in metadata}


def _dependency_versions() -> dict[str, str]:
    packages = {
        "priveopdf": "pdf-modificator",
        "python": None,
        "pyside6": "PySide6",
        "pikepdf": "pikepdf",
        "pillow": "Pillow",
        "cryptography": "cryptography",
    }
    versions = {"python": platform.python_version()}
    for label, distribution in packages.items():
        if distribution is None:
            continue
        try:
            versions[label] = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            versions[label] = "unavailable"
    return versions


def _os_release() -> str:
    path = Path("/etc/os-release")
    try:
        values = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition("=")
            if separator:
                values[key] = value.strip().strip('"')
        return values.get("PRETTY_NAME", "Linux")
    except OSError:
        return platform.system() or "unknown"


def _environment_snapshot(version: BetaVersion) -> dict[str, object]:
    session_type = os.environ.get("XDG_SESSION_TYPE", "").casefold()
    if session_type not in {"wayland", "x11", "tty"}:
        session_type = "unknown"
    return {
        "operating_system": _os_release(),
        "kernel": platform.release(),
        "machine": platform.machine(),
        "session_type": session_type,
        "versions": _dependency_versions(),
        "checks": {
            "beta_metadata_valid": bool(_provenance(version)),
            "beta_executable_present": version.executable.is_file(),
            "state_directory_writable": os.access(_diagnostics_root(version), os.W_OK),
        },
    }


def redact_text(text: str, *, version: BetaVersion | None = None) -> str:
    cleaned = text.replace("\x00", "<nul>")
    if version is not None:
        cleaned = cleaned.replace(str(version.path), "<beta>")
    home = str(Path.home())
    if home:
        cleaned = re.sub(
            re.escape(home) + r"[^\r\n\"']*",
            "<redacted-home-path>",
            cleaned,
        )
    cleaned = _SECRET_RE.sub(lambda match: f"{match.group(1)}=<redacted>", cleaned)
    cleaned = _QUOTED_ABSOLUTE_PATH_RE.sub(
        lambda match: f"{match.group(1)}<redacted-path>{match.group(1)}",
        cleaned,
    )
    cleaned = _DOCUMENT_NAME_RE.sub("<redacted-document>", cleaned)
    cleaned = _ABSOLUTE_WINDOWS_PATH_RE.sub("<redacted-path>", cleaned)
    cleaned = _ABSOLUTE_UNIX_PATH_RE.sub("<redacted-path>", cleaned)
    return cleaned


def _sanitize_event_value(value: object, version: BetaVersion) -> object:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, Path):
        return "<redacted-path>"
    if isinstance(value, str):
        return redact_text(value[:240], version=version)
    return f"<{type(value).__name__}>"


def record_diagnostic_event(event: str, **values: object) -> None:
    session_value = os.environ.get(DIAGNOSTIC_SESSION_ENV, "")
    if os.environ.get(DIAGNOSTIC_ACTIVE_ENV) != "1" or not session_value:
        return
    version = current_beta_version()
    if version is None:
        return
    try:
        session_path = _validated_session_path(session_value, version)
    except DiagnosticError:
        return
    payload = {
        "at": _timestamp(_utc_now()),
        "event": re.sub(r"[^a-z0-9_.-]", "_", event.casefold())[:80],
        "data": {
            key: _sanitize_event_value(value, version)
            for key, value in sorted(values.items())
            if isinstance(key, str)
        },
    }
    line = json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n"
    events_path = session_path / "events.jsonl"
    try:
        with _event_lock:
            descriptor = os.open(
                events_path,
                os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0),
                0o600,
            )
            with os.fdopen(descriptor, "a", encoding="utf-8") as stream:
                stream.write(line)
            lines = events_path.read_text(encoding="utf-8").splitlines()
            if len(lines) > MAX_EVENTS:
                descriptor = os.open(
                    events_path,
                    os.O_WRONLY | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0),
                    0o600,
                )
                with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                    stream.write("\n".join(lines[-MAX_EVENTS:]) + "\n")
            events_path.chmod(0o600)
    except OSError:
        return


def _session_from_path(path: Path, root: Path) -> DiagnosticSession | None:
    if not _SESSION_NAME_RE.fullmatch(path.name):
        return None
    try:
        if path.resolve(strict=True).parent != root.resolve(strict=True):
            return None
        payload = _read_json(path / "session.json")
        started_at = datetime.fromisoformat(str(payload["started_at"]).replace("Z", "+00:00"))
        status = str(payload["status"])
        exit_code_value = payload.get("exit_code")
        exit_code = exit_code_value if isinstance(exit_code_value, int) else None
    except (DiagnosticError, KeyError, OSError, ValueError, TypeError):
        return None
    if status not in {"running", "completed", "crashed", "interrupted", "launch_failed"}:
        return None
    return DiagnosticSession(path=path, started_at=started_at, status=status, exit_code=exit_code)


def latest_diagnostic_session() -> DiagnosticSession | None:
    version = current_beta_version()
    if version is None:
        return None
    root = _diagnostics_root(version)
    if not root.is_dir():
        return None
    sessions = [
        session
        for candidate in root.iterdir()
        if candidate.is_dir() and (session := _session_from_path(candidate, root)) is not None
    ]
    return max(sessions, key=lambda item: item.started_at, default=None)


def pending_abnormal_diagnostic() -> DiagnosticSession | None:
    session = latest_diagnostic_session()
    if session is None:
        return None
    active_session = os.environ.get(DIAGNOSTIC_SESSION_ENV, "")
    if session.status == "running":
        if os.environ.get(DIAGNOSTIC_ACTIVE_ENV) == "1" and active_session == str(session.path):
            return None
        try:
            _finalize_session(session.path, 1, "interrupted")
            root = session.path.parent
            recovered = _session_from_path(session.path, root)
        except DiagnosticError:
            return None
        if recovered is None:
            return None
        session = recovered
    if not session.is_abnormal:
        return None
    try:
        payload = _read_json(session.path / "session.json")
    except DiagnosticError:
        return None
    return None if payload.get("notice_seen") is True else session


def mark_diagnostic_notice_seen(session: DiagnosticSession) -> None:
    current = latest_diagnostic_session()
    if current is None or current.path != session.path:
        return
    payload = _read_json(session.path / "session.json")
    payload["notice_seen"] = True
    _write_private_json(session.path / "session.json", payload)


def _prune_sessions(root: Path) -> None:
    sessions = [
        session
        for candidate in root.iterdir()
        if candidate.is_dir() and (session := _session_from_path(candidate, root)) is not None
    ]
    sessions.sort(key=lambda item: item.started_at, reverse=True)
    retained_count = len(sessions)
    for session in reversed(sessions):
        if retained_count < MAX_SESSIONS:
            break
        if session.status == "running":
            continue
        try:
            resolved = session.path.resolve(strict=True)
            if resolved.parent == root.resolve(strict=True):
                shutil.rmtree(resolved)
                retained_count -= 1
        except OSError:  # noqa: PERF203, S112 - local retention is best effort
            continue


def create_diagnostic_session(version: BetaVersion | None = None) -> DiagnosticSession:
    version = version or current_beta_version()
    if version is None:
        raise DiagnosticError("beta provenance is unavailable")
    root = _diagnostics_root(version)
    _private_directory(root)
    _prune_sessions(root)
    started_at = _utc_now()
    name = f"session-{started_at:%Y%m%dT%H%M%SZ}-{secrets.token_hex(4)}"
    path = root / name
    _private_directory(path)
    payload = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "running",
        "started_at": _timestamp(started_at),
        "ended_at": None,
        "exit_code": None,
        "notice_seen": False,
        "provenance": _provenance(version),
        "environment": _environment_snapshot(version),
    }
    _write_private_json(path / "session.json", payload)
    return DiagnosticSession(path=path, started_at=started_at, status="running", exit_code=None)


def _finalize_session(path: Path, exit_code: int, status: str | None = None) -> None:
    payload = _read_json(path / "session.json")
    if status is None:
        if exit_code == 0:
            status = "completed"
        elif exit_code < 0:
            status = "crashed"
        else:
            status = "interrupted"
    payload.update(
        {
            "status": status,
            "ended_at": _timestamp(_utc_now()),
            "exit_code": exit_code,
        }
    )
    _write_private_json(path / "session.json", payload)


def is_diagnostic_session() -> bool:
    return os.environ.get(DIAGNOSTIC_ACTIVE_ENV) == "1" and bool(
        os.environ.get(DIAGNOSTIC_SESSION_ENV)
    )


def start_diagnostic_session() -> int:
    if is_diagnostic_session():
        raise DiagnosticError("a diagnostic session is already active")
    version = current_beta_version()
    if version is None:
        raise DiagnosticError("beta provenance is unavailable")
    session = create_diagnostic_session(version)
    environment = isolated_beta_environment(version, version.path.parent.parent)
    environment.update(
        {
            DIAGNOSTIC_SESSION_ENV: str(session.path),
            "PYTHONUNBUFFERED": "1",
        }
    )
    try:
        process = subprocess.Popen(  # noqa: S603 - current verified beta interpreter
            [sys.executable, "-m", "pdfmod.app.beta_diagnostics", "--supervise"],
            cwd=version.path,
            env=environment,
            start_new_session=True,
            close_fds=True,
        )
    except OSError as error:
        _finalize_session(session.path, 1, "launch_failed")
        raise DiagnosticError("diagnostic supervisor could not be started") from error
    return process.pid


def _bounded_log_write(stream, text: str, written: int) -> int:  # noqa: ANN001
    encoded = text.encode("utf-8", errors="replace")
    remaining = MAX_LOG_BYTES - written
    if remaining <= 0:
        return written
    chunk = encoded[:remaining].decode("utf-8", errors="ignore")
    stream.write(chunk)
    stream.flush()
    written += len(chunk.encode("utf-8"))
    if len(encoded) > remaining:
        marker = "\n[diagnostic log truncated]\n"
        marker_bytes = marker.encode("utf-8")
        if written + len(marker_bytes) <= MAX_LOG_BYTES:
            stream.write(marker)
            stream.flush()
            written += len(marker_bytes)
    return written


def supervise() -> int:
    version = current_beta_version()
    session_value = os.environ.get(DIAGNOSTIC_SESSION_ENV, "")
    if version is None or not session_value:
        raise DiagnosticError("diagnostic supervisor provenance is unavailable")
    session_path = _validated_session_path(session_value, version)
    log_path = session_path / "runtime.log"
    descriptor = os.open(
        log_path,
        os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    environment = isolated_beta_environment(version, version.path.parent.parent)
    environment.update(
        {
            DIAGNOSTIC_SESSION_ENV: str(session_path),
            DIAGNOSTIC_ACTIVE_ENV: "1",
            "PYTHONFAULTHANDLER": "1",
            "PYTHONUNBUFFERED": "1",
        }
    )
    process: subprocess.Popen[str] | None = None
    exit_code = 1
    try:
        with os.fdopen(descriptor, "a", encoding="utf-8") as log_stream:
            process = subprocess.Popen(  # noqa: S603 - current verified beta interpreter
                [sys.executable, "-m", "pdfmod.app.main"],
                cwd=version.path,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                close_fds=True,
            )
            written = log_path.stat().st_size
            output_stream = process.stdout
            if output_stream is None:
                raise DiagnosticError("diagnostic output capture is unavailable")
            for line in output_stream:
                written = _bounded_log_write(
                    log_stream,
                    redact_text(line, version=version),
                    written,
                )
            exit_code = process.wait()
        _finalize_session(session_path, exit_code)
    except KeyboardInterrupt:
        if process is not None and process.poll() is None:
            process.terminate()
            exit_code = process.wait()
        _finalize_session(session_path, exit_code or 130, "interrupted")
    except BaseException:
        _finalize_session(session_path, exit_code, "launch_failed")
        raise
    if exit_code != 0:
        print(
            "PriveoPDF Beta diagnostic ended abnormally. "
            "Relaunch the same beta and export the report from Options.",
            file=sys.stderr,
        )
    return exit_code


def _safe_report_text(path: Path, version: BetaVersion) -> str:
    try:
        data = path.read_bytes()[:MAX_LOG_BYTES]
    except OSError:
        return ""
    return redact_text(data.decode("utf-8", errors="replace"), version=version)


def suggested_report_name() -> str:
    version = current_beta_version()
    if version is None:
        return "PriveoPDF-diagnostic.zip"
    return f"PriveoPDF-diagnostic-PR-{version.pull_request}-{version.head_sha[:12]}.zip"


def export_latest_report(destination: Path) -> Path:
    version = current_beta_version()
    session = latest_diagnostic_session()
    if version is None or session is None:
        raise DiagnosticError("no diagnostic session is available")
    if destination.suffix.casefold() != ".zip":
        destination = destination.with_suffix(".zip")
    if not destination.parent.is_dir():
        raise DiagnosticError("the selected report directory is unavailable")
    descriptor = -1
    try:
        descriptor = os.open(
            destination,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        files: dict[str, bytes] = {}
        session_text = _safe_report_text(session.path / "session.json", version)
        files["session.json"] = session_text.encode("utf-8")
        for name in ("runtime.log", "events.jsonl"):
            text = _safe_report_text(session.path / name, version)
            if text:
                files[name] = text.encode("utf-8")
        readme = (
            "PriveoPDF private beta diagnostic\n\n"
            "Review this archive before sharing it. It intentionally excludes PDF files, "
            "document contents, thumbnails, preferences and passwords. If a defect depends "
            "on a particular PDF, provide reproducible steps and use only an artificial, "
            "redistributable test PDF when necessary.\n"
        )
        files["README.txt"] = readme.encode("utf-8")
        session_payload = _read_json(session.path / "session.json")
        manifest = {
            "schema_version": REPORT_SCHEMA_VERSION,
            "created_at": _timestamp(_utc_now()),
            "status": session.status,
            "exit_code": session.exit_code,
            "provenance": session_payload.get("provenance", {}),
            "environment": session_payload.get("environment", {}),
            "files": {
                name: {
                    "bytes": len(content),
                    "sha256": hashlib.sha256(content).hexdigest(),
                }
                for name, content in sorted(files.items())
            },
            "privacy": {
                "network_upload": False,
                "documents_included": False,
                "document_names_or_paths_included": False,
                "preferences_included": False,
            },
        }
        files["manifest.json"] = (
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
        with os.fdopen(descriptor, "w+b") as output:
            descriptor = -1
            with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for name in REPORT_ARCHIVE_MEMBERS:
                    content = files.get(name)
                    if content is not None:
                        archive.writestr(name, content)
        destination.chmod(0o600)
    except FileExistsError as error:
        raise DiagnosticError("the selected report file already exists") from error
    except BaseException:
        if descriptor >= 0:
            os.close(descriptor)
        destination.unlink(missing_ok=True)
        raise
    return destination


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Private PriveoPDF beta diagnostics")
    parser.add_argument("--supervise", action="store_true")
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    if not arguments.supervise:
        raise DiagnosticError("no diagnostic action selected")
    return supervise()


if __name__ == "__main__":
    raise SystemExit(main())
