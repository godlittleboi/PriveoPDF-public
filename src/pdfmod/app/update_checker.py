from __future__ import annotations

import base64
import binascii
import configparser
import hashlib
import hmac
import ipaddress
import json
import math
import re
import socket
import time
import tomllib
import urllib.error
import urllib.request
from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass
from importlib import import_module, metadata
from pathlib import Path
from typing import Any, Literal, cast
from urllib.parse import urlsplit

from packaging.version import InvalidVersion, Version

from pdfmod.app.app_info import (
    APP_ID,
    PROJECT_DISTRIBUTION,
    PROJECT_ROOT,
    PYPROJECT_PATH,
    ProductChannel,
    get_app_channel,
    get_app_version,
)

UpdateStatus = Literal[
    "up_to_date",
    "update_available",
    "not_verified",
    "disabled",
    "not_configured",
]
UpdateSource = Literal["manifest", "github_releases"]
PayloadFetcher = Callable[[str], Any]
SignatureVerifier = Callable[[bytes, bytes, bytes], None]
Resolver = Callable[..., list[tuple[Any, ...]]]

DEFAULT_MANIFEST_URL = ""
DEFAULT_ALLOWED_UPDATE_HOSTS = frozenset(
    {
        "api.github.com",
        "github.com",
        "github-releases.githubusercontent.com",
        "objects.githubusercontent.com",
        "updates.priveopdf.app",
    }
)
DEFAULT_TRUSTED_PUBLIC_KEYS: Mapping[str, bytes | str] = {}
MAX_RESPONSE_BYTES = 128 * 1024
MAX_URL_CHARS = 2048
MAX_NOTES_CHARS = 4096
MAX_JSON_DEPTH = 12
MAX_JSON_NODES = 512
MAX_JSON_COLLECTION_ITEMS = 100
MAX_JSON_STRING_CHARS = 8192
MANIFEST_SCHEMA_VERSION = 1

GITHUB_REPO_RE = re.compile(
    r"(?:https://github\.com/|git@github\.com:)(?P<owner>[A-Za-z0-9_.-]+)/"
    r"(?P<repo>[A-Za-z0-9_.-]+?)(?:\.git)?/?$"
)
SHA256_RE = re.compile(r"[0-9a-fA-F]{64}\Z")


class UpdateCheckError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class GitHubRepository:
    owner: str
    name: str

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.name}"

    @property
    def latest_release_api_url(self) -> str:
        return f"https://api.github.com/repos/{self.full_name}/releases/latest"

    @property
    def releases_api_url(self) -> str:
        return f"https://api.github.com/repos/{self.full_name}/releases"

    @property
    def releases_url(self) -> str:
        return f"https://github.com/{self.full_name}/releases"


@dataclass(frozen=True)
class VersionManifest:
    product: str
    channel: ProductChannel
    latest_version: str
    minimum_supported_version: str
    release_url: str
    download_url: str
    sha256: str
    notes: str
    key_id: str


@dataclass(frozen=True)
class UpdateCheckResult:
    status: UpdateStatus
    installed_version: str
    latest_version: str = ""
    release_url: str = ""
    release_notes: str = ""
    download_url: str = ""
    artifact_sha256: str = ""
    signing_key_id: str = ""
    checked_at: float = 0.0
    error_code: str = ""
    repo_full_name: str = ""
    source: str = ""
    channel: ProductChannel = "beta"


def check_for_updates(
    *,
    installed_version: str | None = None,
    channel: ProductChannel | None = None,
    enabled: bool = True,
    manifest_url: str | None = DEFAULT_MANIFEST_URL,
    repository: GitHubRepository | None = None,
    source: UpdateSource = "manifest",
    fetcher: PayloadFetcher | None = None,
    checked_at: float | None = None,
    allowed_hosts: Collection[str] | None = None,
    trusted_public_keys: Mapping[str, bytes | str] | None = None,
    signature_verifier: SignatureVerifier | None = None,
) -> UpdateCheckResult:
    checked = time.time() if checked_at is None else checked_at
    local_version = installed_version or get_app_version()
    update_channel = channel or get_app_channel()
    hosts = _normalized_allowed_hosts(allowed_hosts)
    if not enabled:
        return _not_verified(
            "disabled",
            local_version,
            checked,
            update_channel,
            status="disabled",
        )

    if source == "manifest":
        if not manifest_url:
            return _not_verified(
                "not_configured",
                local_version,
                checked,
                update_channel,
                status="not_configured",
                source="manifest",
            )
        try:
            validate_https_url(manifest_url, allowed_hosts=hosts)
            payload = (
                fetcher(manifest_url)
                if fetcher is not None
                else fetch_json_url(manifest_url, allowed_hosts=hosts)
            )
            manifest = parse_version_manifest(
                payload,
                expected_channel=update_channel,
                allowed_release_hosts=hosts,
                allowed_download_hosts=hosts,
                trusted_public_keys=(
                    DEFAULT_TRUSTED_PUBLIC_KEYS
                    if trusted_public_keys is None
                    else trusted_public_keys
                ),
                signature_verifier=signature_verifier,
            )
        except UpdateCheckError as error:
            return _not_verified(
                error.code,
                local_version,
                checked,
                update_channel,
                source="manifest",
            )
        except (OSError, ValueError, TypeError):
            return _not_verified(
                "offline",
                local_version,
                checked,
                update_channel,
                source="manifest",
            )
        return _result_from_versions(
            installed_version=local_version,
            latest_version=manifest.latest_version,
            release_url=manifest.release_url,
            release_notes=manifest.notes,
            download_url=manifest.download_url,
            artifact_sha256=manifest.sha256,
            signing_key_id=manifest.key_id,
            checked_at=checked,
            channel=update_channel,
            source="manifest",
        )

    if repository is None:
        return _not_verified(
            "not_configured",
            local_version,
            checked,
            update_channel,
            status="not_configured",
            source="github_releases",
        )
    return _check_github_releases(
        installed_version=local_version,
        repository=repository,
        channel=update_channel,
        fetcher=fetcher,
        checked_at=checked,
        allowed_hosts=hosts,
    )


def parse_version_manifest(
    payload: Any,
    *,
    expected_channel: ProductChannel,
    allowed_release_hosts: Collection[str] | None = None,
    allowed_download_hosts: Collection[str] | None = None,
    trusted_public_keys: Mapping[str, bytes | str] | None = None,
    signature_verifier: SignatureVerifier | None = None,
) -> VersionManifest:
    _validate_json_limits(payload)
    if not isinstance(payload, dict) or set(payload) != {
        "schema_version",
        "key_id",
        "signature",
        "signed",
    }:
        raise UpdateCheckError("invalid_payload")
    if type(payload["schema_version"]) is not int or payload["schema_version"] != 1:
        raise UpdateCheckError("unsupported_manifest_schema")
    key_id = _bounded_string(payload["key_id"], 64)
    signature_text = _bounded_string(payload["signature"], 128)
    signed = payload["signed"]
    if not isinstance(signed, dict):
        raise UpdateCheckError("invalid_payload")

    keys = DEFAULT_TRUSTED_PUBLIC_KEYS if trusted_public_keys is None else trusted_public_keys
    public_key_value = keys.get(key_id)
    if public_key_value is None:
        raise UpdateCheckError("unknown_signing_key")
    public_key = _decode_public_key(public_key_value)
    signature = _decode_signature(signature_text)
    verifier = signature_verifier or verify_ed25519_signature
    try:
        verifier(public_key, canonical_manifest_bytes(signed), signature)
    except UpdateCheckError:
        raise
    except Exception as error:
        raise UpdateCheckError("invalid_signature") from error

    required = {
        "product",
        "channel",
        "latest_version",
        "minimum_supported_version",
        "release_url",
        "download_url",
        "sha256",
        "notes",
    }
    if set(signed) != required:
        raise UpdateCheckError("invalid_payload")
    product = _bounded_string(signed["product"], 64).strip()
    channel = _bounded_string(signed["channel"], 16).strip()
    latest_version = _bounded_string(signed["latest_version"], 64).strip()
    minimum_supported_version = _bounded_string(signed["minimum_supported_version"], 64).strip()
    release_url = _bounded_string(signed["release_url"], MAX_URL_CHARS).strip()
    download_url = _bounded_string(signed["download_url"], MAX_URL_CHARS).strip()
    sha256 = _bounded_string(signed["sha256"], 64).strip().lower()
    notes = _bounded_string(signed["notes"], MAX_NOTES_CHARS).strip()
    if product != APP_ID or channel != expected_channel:
        raise UpdateCheckError("invalid_payload")
    if not SHA256_RE.fullmatch(sha256):
        raise UpdateCheckError("invalid_checksum")
    try:
        latest = Version(normalize_version_tag(latest_version))
        minimum = Version(normalize_version_tag(minimum_supported_version))
    except InvalidVersion as error:
        raise UpdateCheckError("invalid_payload") from error
    if minimum > latest:
        raise UpdateCheckError("invalid_payload")
    validate_https_url(
        release_url,
        allowed_hosts=_normalized_allowed_hosts(allowed_release_hosts),
    )
    validate_https_url(
        download_url,
        allowed_hosts=_normalized_allowed_hosts(allowed_download_hosts),
    )
    return VersionManifest(
        product=product,
        channel=cast(ProductChannel, channel),
        latest_version=str(latest),
        minimum_supported_version=str(minimum),
        release_url=release_url,
        download_url=download_url,
        sha256=sha256,
        notes=notes,
        key_id=key_id,
    )


def canonical_manifest_bytes(signed_payload: Mapping[str, Any]) -> bytes:
    try:
        canonical = json.dumps(
            signed_payload,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as error:
        raise UpdateCheckError("invalid_payload") from error
    return canonical.encode("utf-8")


def verify_ed25519_signature(public_key: bytes, message: bytes, signature: bytes) -> None:
    try:
        cryptography_exceptions = import_module("cryptography.exceptions")
        ed25519 = import_module("cryptography.hazmat.primitives.asymmetric.ed25519")
    except ImportError as error:
        raise UpdateCheckError("signature_verifier_unavailable") from error

    try:
        ed25519.Ed25519PublicKey.from_public_bytes(public_key).verify(signature, message)
    except Exception as error:
        if isinstance(error, cryptography_exceptions.InvalidSignature):
            raise UpdateCheckError("invalid_signature") from error
        if isinstance(error, ValueError):
            raise UpdateCheckError("invalid_signing_key") from error
        raise


def verify_artifact_sha256(artifact: bytes | bytearray | memoryview | Path, expected: str) -> None:
    expected_digest = expected.strip().lower()
    if not SHA256_RE.fullmatch(expected_digest):
        raise UpdateCheckError("invalid_checksum")
    digest = hashlib.sha256()
    if isinstance(artifact, Path):
        try:
            with artifact.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
        except OSError as error:
            raise UpdateCheckError("artifact_unavailable") from error
    else:
        digest.update(bytes(artifact))
    if not hmac.compare_digest(digest.hexdigest(), expected_digest):
        raise UpdateCheckError("checksum_mismatch")


def validate_https_url(
    url: str,
    *,
    allowed_hosts: Collection[str],
    resolve_dns: bool = False,
    resolver: Resolver | None = None,
    allow_private_addresses_for_tests: bool = False,
) -> str:
    if not isinstance(url, str) or not url or len(url) > MAX_URL_CHARS:
        raise UpdateCheckError("invalid_url")
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as error:
        raise UpdateCheckError("invalid_url") from error
    if parsed.scheme != "https":
        raise UpdateCheckError("https_required")
    if parsed.username is not None or parsed.password is not None:
        raise UpdateCheckError("credentials_not_allowed")
    if not parsed.hostname or port not in {None, 443}:
        raise UpdateCheckError("port_not_allowed" if parsed.hostname else "invalid_url")
    if parsed.fragment:
        raise UpdateCheckError("invalid_url")
    host = parsed.hostname.lower().rstrip(".")
    normalized_hosts = {allowed.lower().rstrip(".") for allowed in allowed_hosts}
    if host not in normalized_hosts:
        raise UpdateCheckError("host_not_allowed")
    if not allow_private_addresses_for_tests and (
        host == "localhost" or host.endswith(".localhost")
    ):
        raise UpdateCheckError("private_address")
    if not allow_private_addresses_for_tests:
        _reject_non_public_ip_literal(host)
    if resolve_dns and not allow_private_addresses_for_tests:
        _validate_resolved_addresses(host, resolver or socket.getaddrinfo)
    return url


def fetch_json_url(
    url: str,
    *,
    allowed_hosts: Collection[str] | None = None,
    connect_timeout: float = 3.0,
    read_timeout: float = 5.0,
    allow_private_addresses_for_tests: bool = False,
) -> Any:
    hosts = _normalized_allowed_hosts(allowed_hosts)
    validate_https_url(
        url,
        allowed_hosts=hosts,
        resolve_dns=True,
        allow_private_addresses_for_tests=allow_private_addresses_for_tests,
    )
    # The URL has just been restricted to HTTPS, an explicit host allowlist,
    # port 443, public DNS results, and no embedded credentials.
    request = urllib.request.Request(  # noqa: S310
        url,
        headers={
            "Accept": "application/json, application/vnd.github+json",
            "User-Agent": "PriveoPDF-update-check",
        },
    )
    # Do not inherit proxy settings from the environment, Windows registry, or
    # macOS system configuration. Proxy support, if ever added, must be an
    # explicit opt-in capability rather than an ambient transport rewrite.
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        _RejectRedirects(),
    )
    try:
        with opener.open(request, timeout=connect_timeout) as response:
            _set_response_read_timeout(response, read_timeout)
            content_type = _content_type(response)
            if content_type != "application/json" and not (
                content_type.startswith("application/") and content_type.endswith("+json")
            ):
                raise UpdateCheckError("invalid_content_type")
            content_length = _content_length(response)
            if content_length is not None and content_length > MAX_RESPONSE_BYTES:
                raise UpdateCheckError("response_too_large")
            payload = response.read(MAX_RESPONSE_BYTES + 1)
            if len(payload) > MAX_RESPONSE_BYTES:
                raise UpdateCheckError("response_too_large")
    except UpdateCheckError:
        raise
    except urllib.error.HTTPError as error:
        if 300 <= error.code < 400:
            raise UpdateCheckError("redirect_not_allowed") from error
        if error.code in {401, 404}:
            raise UpdateCheckError("private_or_not_found") from error
        if error.code in {403, 429}:
            raise UpdateCheckError("rate_limited") from error
        raise UpdateCheckError("offline") from error
    except (OSError, urllib.error.URLError) as error:
        raise UpdateCheckError("offline") from error
    try:
        decoded = payload.decode("utf-8")
        data = json.loads(
            decoded,
            object_pairs_hook=_unique_json_object,
            parse_constant=_reject_json_constant,
        )
        _validate_json_limits(data)
        return data
    except UpdateCheckError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError) as error:
        raise UpdateCheckError("invalid_payload") from error


class _RejectRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        del req, fp, code, msg, headers, newurl
        raise UpdateCheckError("redirect_not_allowed")


def fetch_latest_release(api_url: str) -> dict[str, Any]:
    data = fetch_json_url(api_url)
    if not isinstance(data, dict):
        raise ValueError("GitHub release payload is not an object")
    return data


def discover_github_repository(
    *,
    pyproject_path: Path = PYPROJECT_PATH,
    project_root: Path = PROJECT_ROOT,
    distribution_name: str = PROJECT_DISTRIBUTION,
) -> GitHubRepository | None:
    for url in (
        _repository_url_from_pyproject(pyproject_path),
        _repository_url_from_package_metadata(distribution_name),
        _repository_url_from_git_config(project_root),
    ):
        if not url:
            continue
        repo = parse_github_repository_url(url)
        if repo is not None:
            return repo
    return None


def parse_github_repository_url(url: str) -> GitHubRepository | None:
    match = GITHUB_REPO_RE.search(url.strip())
    if match is None:
        return None
    return GitHubRepository(match.group("owner"), match.group("repo"))


def normalize_version_tag(tag: str) -> str:
    value = tag.strip()
    return value[1:] if value.lower().startswith("v") else value


def _check_github_releases(
    *,
    installed_version: str,
    repository: GitHubRepository,
    channel: ProductChannel,
    fetcher: PayloadFetcher | None,
    checked_at: float,
    allowed_hosts: Collection[str],
) -> UpdateCheckResult:
    try:
        validate_https_url(repository.releases_api_url, allowed_hosts=allowed_hosts)
        payload = (
            fetcher(repository.releases_api_url)
            if fetcher is not None
            else fetch_json_url(repository.releases_api_url, allowed_hosts=allowed_hosts)
        )
        _validate_json_limits(payload)
        release = _select_github_release(payload, channel)
    except UpdateCheckError as error:
        return _not_verified(
            error.code,
            installed_version,
            checked_at,
            channel,
            repo_full_name=repository.full_name,
            source="github_releases",
        )
    except (OSError, ValueError, TypeError):
        return _not_verified(
            "offline",
            installed_version,
            checked_at,
            channel,
            repo_full_name=repository.full_name,
            source="github_releases",
        )

    tag_name = release.get("tag_name")
    if not isinstance(tag_name, str) or not tag_name.strip():
        return _not_verified(
            "invalid_payload",
            installed_version,
            checked_at,
            channel,
            repo_full_name=repository.full_name,
            source="github_releases",
        )
    release_url = release.get("html_url")
    release_notes = release.get("body")
    candidate_url = release_url if isinstance(release_url, str) else repository.releases_url
    try:
        validate_https_url(candidate_url, allowed_hosts=allowed_hosts)
    except UpdateCheckError as error:
        return _not_verified(
            error.code,
            installed_version,
            checked_at,
            channel,
            repo_full_name=repository.full_name,
            source="github_releases",
        )
    return _result_from_versions(
        installed_version=installed_version,
        latest_version=normalize_version_tag(tag_name),
        release_url=candidate_url,
        release_notes=release_notes if isinstance(release_notes, str) else "",
        checked_at=checked_at,
        channel=channel,
        repo_full_name=repository.full_name,
        source="github_releases",
    )


def _select_github_release(payload: Any, channel: ProductChannel) -> dict[str, Any]:
    releases = [payload] if isinstance(payload, dict) else payload
    if not isinstance(releases, list) or len(releases) > MAX_JSON_COLLECTION_ITEMS:
        raise UpdateCheckError("invalid_payload")
    for release in releases:
        if not isinstance(release, dict) or release.get("draft") is True:
            continue
        if channel == "stable" and release.get("prerelease") is True:
            continue
        tag_name = release.get("tag_name")
        if isinstance(tag_name, str) and 0 < len(tag_name.strip()) <= 64:
            return release
    raise UpdateCheckError("no_release")


def _result_from_versions(
    *,
    installed_version: str,
    latest_version: str,
    release_url: str,
    release_notes: str,
    download_url: str = "",
    artifact_sha256: str = "",
    signing_key_id: str = "",
    checked_at: float,
    channel: ProductChannel,
    repo_full_name: str = "",
    source: str,
) -> UpdateCheckResult:
    try:
        installed = Version(normalize_version_tag(installed_version))
        latest = Version(normalize_version_tag(latest_version))
    except InvalidVersion:
        return _not_verified(
            "invalid_payload",
            installed_version,
            checked_at,
            channel,
            latest_version=latest_version,
            repo_full_name=repo_full_name,
            source=source,
        )
    if latest < installed:
        return _not_verified(
            "downgrade_refused",
            installed_version,
            checked_at,
            channel,
            latest_version=str(latest),
            repo_full_name=repo_full_name,
            source=source,
        )
    return UpdateCheckResult(
        status="update_available" if installed < latest else "up_to_date",
        installed_version=installed_version,
        latest_version=str(latest),
        release_url=release_url,
        release_notes=_short_release_notes(release_notes),
        download_url=download_url,
        artifact_sha256=artifact_sha256,
        signing_key_id=signing_key_id,
        checked_at=checked_at,
        repo_full_name=repo_full_name,
        source=source,
        channel=channel,
    )


def _not_verified(
    error_code: str,
    installed_version: str,
    checked_at: float,
    channel: ProductChannel,
    *,
    status: UpdateStatus = "not_verified",
    latest_version: str = "",
    repo_full_name: str = "",
    source: str = "",
) -> UpdateCheckResult:
    return UpdateCheckResult(
        status=status,
        installed_version=installed_version,
        latest_version=latest_version,
        checked_at=checked_at,
        error_code=error_code,
        repo_full_name=repo_full_name,
        source=source,
        channel=channel,
    )


def _normalized_allowed_hosts(allowed_hosts: Collection[str] | None) -> frozenset[str]:
    source = DEFAULT_ALLOWED_UPDATE_HOSTS if allowed_hosts is None else allowed_hosts
    return frozenset(host.lower().rstrip(".") for host in source if host.strip())


def _reject_non_public_ip_literal(host: str) -> None:
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return
    if not address.is_global:
        raise UpdateCheckError("private_address")


def _validate_resolved_addresses(host: str, resolver: Resolver) -> None:
    try:
        records = resolver(host, 443, type=socket.SOCK_STREAM)
    except OSError as error:
        raise UpdateCheckError("offline") from error
    if not records:
        raise UpdateCheckError("offline")
    for record in records:
        try:
            address_text = record[4][0]
            address = ipaddress.ip_address(address_text)
        except (IndexError, TypeError, ValueError) as error:
            raise UpdateCheckError("invalid_address") from error
        if not address.is_global:
            raise UpdateCheckError("private_address")


def _decode_public_key(value: bytes | str) -> bytes:
    if isinstance(value, bytes):
        decoded = value
    elif isinstance(value, str):
        try:
            decoded = base64.b64decode(value, validate=True)
        except (ValueError, binascii.Error) as error:
            raise UpdateCheckError("invalid_signing_key") from error
    else:
        raise UpdateCheckError("invalid_signing_key")
    if len(decoded) != 32:
        raise UpdateCheckError("invalid_signing_key")
    return decoded


def _decode_signature(value: str) -> bytes:
    try:
        decoded = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as error:
        raise UpdateCheckError("invalid_signature") from error
    if len(decoded) != 64:
        raise UpdateCheckError("invalid_signature")
    return decoded


def _bounded_string(value: Any, max_chars: int) -> str:
    if not isinstance(value, str) or len(value) > max_chars or "\x00" in value:
        raise UpdateCheckError("invalid_payload")
    return value


def _content_type(response: Any) -> str:
    headers = getattr(response, "headers", None)
    if headers is None:
        raise UpdateCheckError("invalid_content_type")
    if hasattr(headers, "get_content_type"):
        return str(headers.get_content_type()).lower()
    raw = headers.get("Content-Type", "")
    return str(raw).partition(";")[0].strip().lower()


def _content_length(response: Any) -> int | None:
    headers = getattr(response, "headers", None)
    raw = headers.get("Content-Length") if headers is not None else None
    if raw is None or raw == "":
        return None
    if not isinstance(raw, str | int):
        raise UpdateCheckError("invalid_payload")
    try:
        value = int(raw)
    except (TypeError, ValueError) as error:
        raise UpdateCheckError("invalid_payload") from error
    if value < 0:
        raise UpdateCheckError("invalid_payload")
    return value


def _set_response_read_timeout(response: Any, timeout: float) -> None:
    try:
        response.fp.raw._sock.settimeout(timeout)
    except (AttributeError, OSError):
        # Some supported urllib handlers do not expose their socket; the connect timeout
        # remains active in those implementations.
        return


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise UpdateCheckError("invalid_payload")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    del value
    raise UpdateCheckError("invalid_payload")


def _validate_json_limits(value: Any) -> None:
    nodes = 0

    def visit(current: Any, depth: int) -> None:
        nonlocal nodes
        nodes += 1
        if nodes > MAX_JSON_NODES or depth > MAX_JSON_DEPTH:
            raise UpdateCheckError("invalid_payload")
        if isinstance(current, str):
            if len(current) > MAX_JSON_STRING_CHARS or "\x00" in current:
                raise UpdateCheckError("invalid_payload")
            return
        if isinstance(current, dict):
            if len(current) > MAX_JSON_COLLECTION_ITEMS:
                raise UpdateCheckError("invalid_payload")
            for key, item in current.items():
                if not isinstance(key, str) or len(key) > 128:
                    raise UpdateCheckError("invalid_payload")
                visit(item, depth + 1)
            return
        if isinstance(current, list):
            if len(current) > MAX_JSON_COLLECTION_ITEMS:
                raise UpdateCheckError("invalid_payload")
            for item in current:
                visit(item, depth + 1)
            return
        if isinstance(current, float) and not math.isfinite(current):
            raise UpdateCheckError("invalid_payload")
        if current is not None and not isinstance(current, bool | int | float):
            raise UpdateCheckError("invalid_payload")

    visit(value, 0)


def _repository_url_from_pyproject(path: Path) -> str | None:
    if not path.exists():
        return None
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError:
        return None
    urls = data.get("project", {}).get("urls", {})
    if not isinstance(urls, dict):
        return None
    repository = urls.get("Repository")
    return repository if isinstance(repository, str) and repository else None


def _repository_url_from_package_metadata(distribution_name: str) -> str | None:
    try:
        package_metadata = metadata.metadata(distribution_name)
    except metadata.PackageNotFoundError:
        return None
    project_urls = package_metadata.get_all("Project-URL") or []
    for project_url in project_urls:
        label, separator, url = project_url.partition(",")
        if separator and label.strip().lower() == "repository":
            return url.strip()
    return None


def _repository_url_from_git_config(project_root: Path) -> str | None:
    config_path = _git_config_path(project_root)
    if config_path is None or not config_path.exists():
        return None

    parser = configparser.ConfigParser()
    try:
        parser.read(config_path, encoding="utf-8")
    except configparser.Error:
        return None

    for section in ('remote "origin"', "remote.origin"):
        if parser.has_option(section, "url"):
            return parser.get(section, "url")
    return None


def _git_config_path(project_root: Path) -> Path | None:
    git_path = project_root / ".git"
    if git_path.is_dir():
        return git_path / "config"
    if not git_path.is_file():
        return None
    try:
        content = git_path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    prefix = "gitdir:"
    if not content.lower().startswith(prefix):
        return None
    git_dir = Path(content[len(prefix) :].strip())
    if not git_dir.is_absolute():
        git_dir = project_root / git_dir
    return git_dir / "config"


def _short_release_notes(notes: str, max_chars: int = MAX_NOTES_CHARS) -> str:
    cleaned = notes.replace("\x00", "").strip()
    if len(cleaned) <= max_chars:
        return cleaned
    return f"{cleaned[: max_chars - 3].rstrip()}..."
