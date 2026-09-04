"""Bounded Unix-socket boundary between the offline GUI and update network code."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import signal
import socket
import struct
import subprocess
import sys
import uuid
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal, cast

from pdfmod.app.app_info import ProductChannel, get_app_channel, get_app_version
from pdfmod.app.source_update import (
    SOURCE_UPDATE_KIND,
    SourceUpdateCheckResult,
    check_source_update,
    is_valid_source_revision,
    source_checkout_available,
)
from pdfmod.app.update_checker import (
    DEFAULT_ALLOWED_UPDATE_HOSTS,
    UpdateCheckError,
    UpdateCheckResult,
    check_for_updates,
    validate_https_url,
)

PROTOCOL_VERSION = 1
MAX_MESSAGE_BYTES = 32 * 1024
MAX_URL_CHARS = 2048
MAX_NOTES_CHARS = 4096
SOURCE_INSTALL_REQUEST = "source-install.request"
REQUEST_ID_RE = re.compile(r"[0-9a-f]{32}\Z")
BrokerAction = Literal["ping", "check", "install_source", "open_release"]

_RESULT_KEYS = {
    "artifact_sha256",
    "channel",
    "checked_at",
    "download_url",
    "error_code",
    "installed_version",
    "latest_version",
    "release_notes",
    "release_url",
    "repo_full_name",
    "signing_key_id",
    "source",
    "status",
    "target_revision",
}
_ERROR_CODES = frozenset(
    {
        "",
        "artifact_unavailable",
        "broker_protocol_error",
        "broker_unavailable",
        "checksum_mismatch",
        "credentials_not_allowed",
        "disabled",
        "downgrade_refused",
        "host_not_allowed",
        "https_required",
        "invalid_address",
        "invalid_checksum",
        "invalid_content_type",
        "invalid_payload",
        "invalid_signature",
        "invalid_signing_key",
        "invalid_url",
        "no_release",
        "not_configured",
        "offline",
        "port_not_allowed",
        "private_address",
        "private_or_not_found",
        "rate_limited",
        "redirect_not_allowed",
        "response_too_large",
        "signature_verifier_unavailable",
        "source_check_timeout",
        "source_checkout_dirty",
        "source_checkout_diverged",
        "source_checkout_invalid",
        "source_checkout_wrong_branch",
        "source_checkout_wrong_remote",
        "source_fetch_failed",
        "source_updater_unavailable",
        "unknown_signing_key",
        "unsupported_manifest_schema",
    }
)


class BrokerProtocolError(ValueError):
    pass


def request_update_check(
    *,
    allow_source_checkout: bool,
    socket_path: Path | None = None,
    timeout_seconds: float = 65.0,
) -> UpdateCheckResult:
    path = socket_path or _configured_socket_path()
    if path is None:
        return _broker_failure("broker_unavailable")
    request_id = uuid.uuid4().hex
    response = _request(
        path,
        {
            "action": "check",
            "allow_source_checkout": bool(allow_source_checkout),
            "request_id": request_id,
            "schema_version": PROTOCOL_VERSION,
        },
        timeout_seconds=timeout_seconds,
    )
    return _decode_check_response(response, request_id)


def request_source_install(
    parent_pid: int,
    target_revision: str,
    *,
    socket_path: Path | None = None,
) -> bool:
    if parent_pid <= 0 or not is_valid_source_revision(target_revision):
        return False
    path = socket_path or _configured_socket_path()
    if path is None:
        return False
    request_id = uuid.uuid4().hex
    try:
        response = _request(
            path,
            {
                "action": "install_source",
                "parent_pid": parent_pid,
                "request_id": request_id,
                "schema_version": PROTOCOL_VERSION,
                "target_revision": target_revision.lower(),
            },
            timeout_seconds=3.0,
        )
        return _decode_ack(response, request_id)
    except (BrokerProtocolError, OSError):
        return False


def request_open_release(*, socket_path: Path | None = None) -> bool:
    path = socket_path or _configured_socket_path()
    if path is None:
        return False
    request_id = uuid.uuid4().hex
    try:
        response = _request(
            path,
            {
                "action": "open_release",
                "request_id": request_id,
                "schema_version": PROTOCOL_VERSION,
            },
            timeout_seconds=3.0,
        )
        return _decode_ack(response, request_id)
    except (BrokerProtocolError, OSError):
        return False


def serve(socket_path: Path, project_root: Path) -> int:
    path = socket_path.resolve(strict=False)
    root = project_root.resolve(strict=True)
    if not root.is_dir() or path.parent == root or root in path.parents:
        raise BrokerProtocolError("invalid broker paths")
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    try:
        path.unlink(missing_ok=True)
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
            listener.bind(str(path))
            path.chmod(0o600)
            listener.listen(4)
            listener.settimeout(1.0)
            stopping = False
            state = {"release_url": ""}

            def stop(_signum: int, _frame: object) -> None:
                nonlocal stopping
                stopping = True

            signal.signal(signal.SIGTERM, stop)
            signal.signal(signal.SIGINT, stop)
            while not stopping:
                try:
                    connection, _address = listener.accept()
                except TimeoutError:
                    continue
                with connection:
                    connection.settimeout(70.0)
                    response = _handle_connection(connection, root, path.parent, state)
                    connection.sendall(_encode_message(response))
    finally:
        path.unlink(missing_ok=True)
    return 0


def _handle_connection(
    connection: socket.socket,
    project_root: Path,
    runtime_dir: Path,
    state: dict[str, str],
) -> dict[str, Any]:
    try:
        _require_same_user(connection)
        request = _decode_message(_read_message(connection))
        request_id, action = _validate_request(request)
        if action == "ping":
            return _ack(request_id, True)
        if action == "check":
            result = _perform_check(request, project_root)
            state["release_url"] = _verified_release_url(result)
            return {
                "request_id": request_id,
                "result": _result_payload(result),
                "schema_version": PROTOCOL_VERSION,
                "status": "ok",
            }
        if action == "install_source":
            return _ack(request_id, _queue_source_helper(request, runtime_dir))
        if action == "open_release":
            return _ack(request_id, _open_release(request, state))
        raise BrokerProtocolError("unknown action")
    except (BrokerProtocolError, OSError, ValueError):
        return {
            "error_code": "broker_protocol_error",
            "request_id": _safe_request_id(locals().get("request")),
            "schema_version": PROTOCOL_VERSION,
            "status": "error",
        }


def _perform_check(request: Mapping[str, Any], project_root: Path) -> UpdateCheckResult:
    expected = {
        "action",
        "allow_source_checkout",
        "request_id",
        "schema_version",
    }
    if set(request) != expected or type(request["allow_source_checkout"]) is not bool:
        raise BrokerProtocolError("invalid check request")
    if request["allow_source_checkout"] and source_checkout_available(project_root):
        return check_source_update(project_root=project_root)
    return check_for_updates()


def _queue_source_helper(request: Mapping[str, Any], runtime_dir: Path) -> bool:
    expected = {
        "action",
        "parent_pid",
        "request_id",
        "schema_version",
        "target_revision",
    }
    if set(request) != expected or type(request["parent_pid"]) is not int:
        raise BrokerProtocolError("invalid install request")
    parent_pid = request["parent_pid"]
    target_revision = _bounded_string(request["target_revision"], 40).lower()
    if not 0 < parent_pid <= 2_147_483_647 or not is_valid_source_revision(target_revision):
        raise BrokerProtocolError("invalid install request")
    request_path = runtime_dir / SOURCE_INSTALL_REQUEST
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(request_path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="ascii", newline="\n") as request_file:
            request_file.write(f"{parent_pid}\n{target_revision}\n")
            request_file.flush()
            os.fsync(request_file.fileno())
    except BaseException:
        request_path.unlink(missing_ok=True)
        raise
    return True


def _verified_release_url(result: UpdateCheckResult) -> str:
    if result.status != "update_available" or not result.release_url:
        return ""
    try:
        validate_https_url(result.release_url, allowed_hosts=DEFAULT_ALLOWED_UPDATE_HOSTS)
    except UpdateCheckError:
        return ""
    return result.release_url


def _open_release(request: Mapping[str, Any], state: Mapping[str, str]) -> bool:
    if set(request) != {"action", "request_id", "schema_version"}:
        raise BrokerProtocolError("invalid URL request")
    url = _bounded_string(state.get("release_url"), MAX_URL_CHARS)
    if not url:
        return False
    validate_https_url(url, allowed_hosts=DEFAULT_ALLOWED_UPDATE_HOSTS)
    opener = shutil.which("xdg-open")
    if opener is None:
        return False
    process = subprocess.Popen(  # noqa: S603
        (opener, url),
        env=_child_environment(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        start_new_session=True,
    )
    return process.pid > 0


def _child_environment() -> dict[str, str]:
    allowed = {
        "DISPLAY",
        "LANG",
        "LC_ALL",
        "PATH",
        "QT_QPA_PLATFORM",
        "QT_SCALE_FACTOR",
        "WAYLAND_DISPLAY",
        "XAUTHORITY",
        "XDG_CACHE_HOME",
        "XDG_CONFIG_HOME",
        "XDG_DATA_HOME",
        "XDG_RUNTIME_DIR",
        "XDG_STATE_HOME",
    }
    result = {key: value for key, value in os.environ.items() if key in allowed and value}
    result.setdefault("LANG", "C.UTF-8")
    result.setdefault("LC_ALL", "C.UTF-8")
    result.setdefault("PATH", os.defpath)
    result["PYTHONPATH"] = str(Path(__file__).resolve().parents[2])
    result["PRIVEOPDF_UPDATE_HELPER"] = "1"
    return result


def _result_payload(result: UpdateCheckResult) -> dict[str, Any]:
    return {
        "artifact_sha256": result.artifact_sha256,
        "channel": result.channel,
        "checked_at": result.checked_at,
        "download_url": result.download_url,
        "error_code": result.error_code if result.error_code in _ERROR_CODES else "invalid_payload",
        "installed_version": result.installed_version,
        "latest_version": result.latest_version,
        "release_notes": result.release_notes[:MAX_NOTES_CHARS],
        "release_url": result.release_url,
        "repo_full_name": result.repo_full_name,
        "signing_key_id": result.signing_key_id,
        "source": result.source,
        "status": result.status,
        "target_revision": (
            result.target_revision if isinstance(result, SourceUpdateCheckResult) else ""
        ),
    }


def _decode_check_response(response: Mapping[str, Any], request_id: str) -> UpdateCheckResult:
    if (
        response.get("schema_version") != PROTOCOL_VERSION
        or response.get("request_id") != request_id
    ):
        raise BrokerProtocolError("mismatched broker response")
    if response.get("status") == "error":
        if set(response) != {"error_code", "request_id", "schema_version", "status"}:
            raise BrokerProtocolError("invalid broker error response")
        error = response.get("error_code")
        return _broker_failure(
            error if isinstance(error, str) and error in _ERROR_CODES else "invalid_payload"
        )
    if set(response) != {"request_id", "result", "schema_version", "status"}:
        raise BrokerProtocolError("invalid broker response")
    payload = response["result"]
    if not isinstance(payload, dict) or set(payload) != _RESULT_KEYS:
        raise BrokerProtocolError("invalid result payload")
    status = _bounded_string(payload["status"], 32)
    if status not in {
        "up_to_date",
        "update_available",
        "not_verified",
        "disabled",
        "not_configured",
    }:
        raise BrokerProtocolError("invalid result status")
    channel = _bounded_string(payload["channel"], 16)
    if channel not in {"beta", "stable"}:
        raise BrokerProtocolError("invalid result channel")
    checked_at = payload["checked_at"]
    if (
        not isinstance(checked_at, (int, float))
        or isinstance(checked_at, bool)
        or not math.isfinite(checked_at)
    ):
        raise BrokerProtocolError("invalid result timestamp")
    values = {
        key: _bounded_string(
            payload[key],
            MAX_NOTES_CHARS if key == "release_notes" else MAX_URL_CHARS,
        )
        for key in _RESULT_KEYS - {"checked_at"}
    }
    error_code = values["error_code"]
    if error_code not in _ERROR_CODES:
        raise BrokerProtocolError("invalid error code")
    common = {
        "status": status,
        "installed_version": values["installed_version"],
        "latest_version": values["latest_version"],
        "release_url": values["release_url"],
        "release_notes": values["release_notes"],
        "download_url": values["download_url"],
        "artifact_sha256": values["artifact_sha256"],
        "signing_key_id": values["signing_key_id"],
        "checked_at": float(checked_at),
        "error_code": error_code,
        "repo_full_name": values["repo_full_name"],
        "source": values["source"],
        "channel": cast(ProductChannel, channel),
    }
    if values["source"] == SOURCE_UPDATE_KIND:
        target = values["target_revision"]
        if target and not is_valid_source_revision(target):
            raise BrokerProtocolError("invalid target revision")
        return SourceUpdateCheckResult(**common, target_revision=target)
    if values["target_revision"]:
        raise BrokerProtocolError("unexpected target revision")
    return UpdateCheckResult(**common)


def _request(
    socket_path: Path,
    payload: Mapping[str, Any],
    *,
    timeout_seconds: float,
) -> dict[str, Any]:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(timeout_seconds)
        client.connect(str(socket_path))
        client.sendall(_encode_message(payload))
        client.shutdown(socket.SHUT_WR)
        return _decode_message(_read_message(client))


def _read_message(connection: socket.socket) -> bytes:
    chunks = bytearray()
    while True:
        chunk = connection.recv(min(4096, MAX_MESSAGE_BYTES + 1 - len(chunks)))
        if not chunk:
            break
        chunks.extend(chunk)
        if len(chunks) > MAX_MESSAGE_BYTES:
            raise BrokerProtocolError("message too large")
    return bytes(chunks)


def _encode_message(payload: Mapping[str, Any]) -> bytes:
    encoded = json.dumps(payload, allow_nan=False, separators=(",", ":"), sort_keys=True).encode()
    if not encoded or len(encoded) > MAX_MESSAGE_BYTES:
        raise BrokerProtocolError("message too large")
    return encoded


def _decode_message(data: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as error:
        raise BrokerProtocolError("invalid JSON") from error
    if not isinstance(payload, dict):
        raise BrokerProtocolError("message must be an object")
    return payload


def _validate_request(request: Mapping[str, Any]) -> tuple[str, BrokerAction]:
    if request.get("schema_version") != PROTOCOL_VERSION:
        raise BrokerProtocolError("unsupported protocol")
    request_id = _bounded_string(request.get("request_id"), 32)
    if not REQUEST_ID_RE.fullmatch(request_id):
        raise BrokerProtocolError("invalid request id")
    action = _bounded_string(request.get("action"), 32)
    if action not in {"ping", "check", "install_source", "open_release"}:
        raise BrokerProtocolError("invalid action")
    if action == "ping" and set(request) != {"action", "request_id", "schema_version"}:
        raise BrokerProtocolError("invalid ping")
    return request_id, cast(BrokerAction, action)


def _decode_ack(response: Mapping[str, Any], request_id: str) -> bool:
    return (
        set(response) == {"accepted", "request_id", "schema_version", "status"}
        and response.get("schema_version") == PROTOCOL_VERSION
        and response.get("request_id") == request_id
        and response.get("status") == "ok"
        and response.get("accepted") is True
    )


def _ack(request_id: str, accepted: bool) -> dict[str, Any]:
    return {
        "accepted": bool(accepted),
        "request_id": request_id,
        "schema_version": PROTOCOL_VERSION,
        "status": "ok",
    }


def _broker_failure(code: str) -> UpdateCheckResult:
    return UpdateCheckResult(
        status="not_verified",
        installed_version=get_app_version(),
        checked_at=0.0,
        error_code=code if code in _ERROR_CODES else "broker_unavailable",
        channel=get_app_channel(),
    )


def _configured_socket_path() -> Path | None:
    value = os.environ.get("PRIVEOPDF_UPDATE_BROKER_SOCKET", "")
    if not value or "\x00" in value or len(value) > 4096:
        return None
    return Path(value)


def _bounded_string(value: object, maximum: int) -> str:
    if not isinstance(value, str) or "\x00" in value or len(value) > maximum:
        raise BrokerProtocolError("invalid string")
    return value


def _safe_request_id(request: object) -> str:
    if isinstance(request, Mapping):
        value = request.get("request_id")
        if isinstance(value, str) and REQUEST_ID_RE.fullmatch(value):
            return value
    return "0" * 32


def _require_same_user(connection: socket.socket) -> None:
    if not hasattr(socket, "SO_PEERCRED"):
        return
    credentials = connection.getsockopt(
        socket.SOL_SOCKET,
        socket.SO_PEERCRED,
        struct.calcsize("3i"),
    )
    _pid, uid, _gid = struct.unpack("3i", credentials)
    if uid != os.getuid():
        raise BrokerProtocolError("peer user mismatch")


def _parse_arguments(arguments: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("--socket", required=True, type=Path)
    parser.add_argument("--project-root", required=True, type=Path)
    return parser.parse_args(arguments)


def main(arguments: Sequence[str] | None = None) -> int:
    options = _parse_arguments(sys.argv[1:] if arguments is None else arguments)
    try:
        return serve(options.socket, options.project_root)
    except (BrokerProtocolError, OSError):
        return 78


if __name__ == "__main__":
    raise SystemExit(main())
