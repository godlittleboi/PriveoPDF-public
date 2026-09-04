from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import IO, Any
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOCK = Path("compliance/third_party_sources.lock.json")
HEX_SHA256 = re.compile(r"[0-9a-f]{64}")
SAFE_BUNDLE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{1,127}")
BUFFER_SIZE = 1024 * 1024


class BundleError(RuntimeError):
    pass


@dataclass(frozen=True)
class SourceEntry:
    component: str
    filename: str
    official_metadata_url: str
    official_source_url: str
    sha256: str
    size_bytes: int
    version: str
    license_context: tuple[str, ...]


@dataclass(frozen=True)
class LicenseEntry:
    path: str
    sha256: str


@dataclass(frozen=True)
class BundleLock:
    archive_timestamp_utc: str
    bundle_name: str
    license_files: tuple[LicenseEntry, ...]
    qt_import_modules: tuple[str, ...]
    runtime_packages: tuple[dict[str, str], ...]
    sources: tuple[SourceEntry, ...]
    raw: bytes


@dataclass(frozen=True)
class BundleResult:
    archive: Path
    checksum: Path
    sha256: str
    source_count: int


@dataclass(frozen=True)
class VerifiedBundle:
    archive: Path
    sha256: str
    source_count: int


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(BUFFER_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_relative_path(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise BundleError(f"{label} must be a non-empty string")
    candidate = PurePosixPath(value)
    if candidate.is_absolute() or ".." in candidate.parts or "." in candidate.parts:
        raise BundleError(f"{label} contains path traversal")
    if "\\" in value or candidate.as_posix() != value:
        raise BundleError(f"{label} is not a normalized POSIX path")
    return value


def _safe_url(value: object, *, filename: str, label: str) -> str:
    if not isinstance(value, str):
        raise BundleError(f"{label} must be a string")
    parsed = urlparse(value)
    if parsed.scheme != "https" or parsed.hostname != "download.qt.io":
        raise BundleError(f"{label} must use the official download.qt.io HTTPS host")
    if parsed.username or parsed.password or parsed.fragment:
        raise BundleError(f"{label} contains unsupported URL components")
    if label == "official_source_url" and not parsed.path.endswith(f"/{filename}"):
        raise BundleError(f"{label} does not end with the locked filename")
    return value


def _required_string(document: dict[str, Any], key: str) -> str:
    value = document.get(key)
    if not isinstance(value, str) or not value:
        raise BundleError(f"lock field {key} must be a non-empty string")
    return value


def _string_list(value: object, *, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise BundleError(f"{label} must be a non-empty list")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item:
            raise BundleError(f"{label} contains an invalid value")
        result.append(item)
    if len(result) != len(set(result)):
        raise BundleError(f"{label} contains duplicates")
    return tuple(result)


def _parse_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise BundleError("archive_timestamp_utc is not ISO-8601") from error
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise BundleError("archive_timestamp_utc must be UTC")
    parsed = parsed.astimezone(UTC)
    if parsed.year < 1980 or parsed.year > 2107:
        raise BundleError("archive timestamp is outside the ZIP range")
    return parsed


def load_lock(path: Path) -> BundleLock:
    if path.is_symlink() or not path.is_file():
        raise BundleError("third-party source lock must be a regular file")
    raw = path.read_bytes()
    try:
        document = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise BundleError("third-party source lock is not valid UTF-8 JSON") from error
    if not isinstance(document, dict) or document.get("schema_version") != 1:
        raise BundleError("unsupported third-party source lock schema")

    bundle_name = _required_string(document, "bundle_name")
    if SAFE_BUNDLE_NAME.fullmatch(bundle_name) is None:
        raise BundleError("bundle_name contains unsupported characters")
    archive_timestamp = _required_string(document, "archive_timestamp_utc")
    _parse_timestamp(archive_timestamp)

    raw_sources = document.get("sources")
    if not isinstance(raw_sources, list) or not raw_sources:
        raise BundleError("sources must be a non-empty list")
    sources: list[SourceEntry] = []
    seen_filenames: set[str] = set()
    for item in raw_sources:
        if not isinstance(item, dict):
            raise BundleError("sources contains a non-object entry")
        filename = _safe_relative_path(item.get("filename"), label="source filename")
        if "/" in filename:
            raise BundleError("source filename must not contain directories")
        if filename in seen_filenames:
            raise BundleError("sources contains a duplicate filename")
        seen_filenames.add(filename)
        sha256 = item.get("sha256")
        if not isinstance(sha256, str) or HEX_SHA256.fullmatch(sha256) is None:
            raise BundleError(f"invalid SHA-256 for {filename}")
        size_bytes = item.get("size_bytes")
        if not isinstance(size_bytes, int) or isinstance(size_bytes, bool) or size_bytes <= 0:
            raise BundleError(f"invalid byte size for {filename}")
        sources.append(
            SourceEntry(
                component=_required_string(item, "component"),
                filename=filename,
                official_metadata_url=_safe_url(
                    item.get("official_metadata_url"),
                    filename=filename,
                    label="official_metadata_url",
                ),
                official_source_url=_safe_url(
                    item.get("official_source_url"),
                    filename=filename,
                    label="official_source_url",
                ),
                sha256=sha256,
                size_bytes=size_bytes,
                version=_required_string(item, "version"),
                license_context=_string_list(
                    item.get("license_context"), label=f"license_context for {filename}"
                ),
            )
        )

    raw_licenses = document.get("license_files")
    if not isinstance(raw_licenses, list) or not raw_licenses:
        raise BundleError("license_files must be a non-empty list")
    license_files: list[LicenseEntry] = []
    for item in raw_licenses:
        if not isinstance(item, dict):
            raise BundleError("license_files contains a non-object entry")
        relative = _safe_relative_path(item.get("path"), label="license path")
        sha256 = item.get("sha256")
        if not isinstance(sha256, str) or HEX_SHA256.fullmatch(sha256) is None:
            raise BundleError(f"invalid license SHA-256 for {relative}")
        license_files.append(LicenseEntry(path=relative, sha256=sha256))
    if len({entry.path for entry in license_files}) != len(license_files):
        raise BundleError("license_files contains duplicate paths")

    modules = _string_list(document.get("qt_import_modules"), label="qt_import_modules")
    if any(not module.startswith("PySide6.Qt") for module in modules):
        raise BundleError("qt_import_modules contains a non-Qt-for-Python module")

    raw_packages = document.get("runtime_packages")
    if not isinstance(raw_packages, list) or not raw_packages:
        raise BundleError("runtime_packages must be a non-empty list")
    packages: list[dict[str, str]] = []
    seen_packages: set[str] = set()
    for item in raw_packages:
        if not isinstance(item, dict):
            raise BundleError("runtime_packages contains a non-object entry")
        name = _required_string(item, "name")
        version = _required_string(item, "version")
        if name.casefold() in seen_packages:
            raise BundleError("runtime_packages contains duplicate names")
        seen_packages.add(name.casefold())
        packages.append({"name": name, "version": version})

    return BundleLock(
        archive_timestamp_utc=archive_timestamp,
        bundle_name=bundle_name,
        license_files=tuple(license_files),
        qt_import_modules=modules,
        runtime_packages=tuple(packages),
        sources=tuple(sources),
        raw=raw,
    )


def _regular_file(path: Path, *, label: str) -> None:
    try:
        mode = path.lstat().st_mode
    except OSError as error:
        raise BundleError(f"missing {label}: {path.name}") from error
    if not stat.S_ISREG(mode) or path.is_symlink():
        raise BundleError(f"{label} must be a regular non-symlink file: {path.name}")


def _verify_inputs(
    *, project_root: Path, cache_dir: Path, lock: BundleLock
) -> tuple[dict[str, bytes], dict[str, Path]]:
    text_files: dict[str, bytes] = {}
    source_files: dict[str, Path] = {}
    for entry in lock.license_files:
        path = project_root.joinpath(*PurePosixPath(entry.path).parts)
        try:
            path.resolve().relative_to(project_root)
        except (OSError, ValueError) as error:
            raise BundleError(f"license escapes project root: {entry.path}") from error
        _regular_file(path, label="license file")
        content = path.read_bytes()
        if _sha256_bytes(content) != entry.sha256:
            raise BundleError(f"license hash mismatch: {entry.path}")
        text_files[entry.path] = content

    for entry in lock.sources:
        path = cache_dir / entry.filename
        _regular_file(path, label="cached source archive")
        actual_size = path.stat().st_size
        if actual_size != entry.size_bytes:
            raise BundleError(
                f"source size mismatch for {entry.filename}: {actual_size} != {entry.size_bytes}"
            )
        if _sha256_file(path) != entry.sha256:
            raise BundleError(f"source SHA-256 mismatch: {entry.filename}")
        source_files[f"sources/{entry.filename}"] = path
    return text_files, source_files


def _source_availability(lock: BundleLock) -> bytes:
    lines = [
        "PriveoPDF third-party corresponding sources",
        "============================================",
        "",
        "This bundle contains the complete, checksum-verified upstream archives",
        "locked for the Qt/PySide6/Shiboken baseline named below. It is separate",
        "from PriveoPDF's proprietary source and executable licenses.",
        "",
    ]
    for source in lock.sources:
        lines.extend(
            [
                f"- {source.component} {source.version}",
                f"  File: sources/{source.filename}",
                f"  SHA-256: {source.sha256}",
                f"  Official source: {source.official_source_url}",
                f"  Official metadata: {source.official_metadata_url}",
            ]
        )
    lines.extend(
        [
            "",
            "The license files inside each upstream archive remain authoritative.",
            "No PriveoPDF term limits rights granted by those third-party licenses.",
            "",
        ]
    )
    return "\n".join(lines).encode("utf-8")


def _manifest(lock: BundleLock, lock_sha256: str) -> bytes:
    document = {
        "archive_timestamp_utc": lock.archive_timestamp_utc,
        "artifact": lock.bundle_name,
        "license_files": [entry.__dict__ for entry in lock.license_files],
        "lock_sha256": lock_sha256,
        "qt_import_modules": list(lock.qt_import_modules),
        "runtime_packages": list(lock.runtime_packages),
        "schema_version": 1,
        "sources": [entry.__dict__ for entry in lock.sources],
    }
    return (json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def _zip_info(path: str, timestamp: datetime, *, mode: int = 0o644) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(path, date_time=timestamp.timetuple()[:6])
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = (mode & 0xFFFF) << 16
    return info


def _copy_into_zip(source: IO[bytes], target: IO[bytes]) -> None:
    shutil.copyfileobj(source, target, length=BUFFER_SIZE)


def _write_archive(
    *,
    path: Path,
    root_name: str,
    timestamp: datetime,
    text_files: dict[str, bytes],
    source_files: dict[str, Path],
) -> None:
    with path.open("w+b") as archive_stream:
        with zipfile.ZipFile(
            archive_stream,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
            allowZip64=True,
        ) as bundle:
            for relative, content in sorted(text_files.items()):
                member = f"{root_name}/{relative}"
                bundle.writestr(
                    _zip_info(member, timestamp),
                    content,
                    compress_type=zipfile.ZIP_DEFLATED,
                    compresslevel=9,
                )
            for relative, source_path in sorted(source_files.items()):
                member = f"{root_name}/{relative}"
                info = _zip_info(member, timestamp)
                info.compress_type = zipfile.ZIP_STORED
                info.file_size = source_path.stat().st_size
                with (
                    source_path.open("rb") as source,
                    bundle.open(info, "w", force_zip64=True) as target,
                ):
                    _copy_into_zip(source, target)
        archive_stream.flush()
        os.fsync(archive_stream.fileno())
    path.chmod(0o644)


def _atomic_write(path: Path, content: bytes) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    if temporary.exists():
        raise BundleError(f"temporary output already exists: {temporary.name}")
    try:
        with temporary.open("xb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.chmod(0o644)
        temporary.replace(path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def build_bundle(
    *, project_root: Path, lock_path: Path, cache_dir: Path, output_dir: Path
) -> BundleResult:
    project_root = project_root.resolve()
    lock_path = lock_path.resolve()
    cache_dir = cache_dir.resolve()
    output_dir = output_dir.resolve()
    if not project_root.is_dir() or project_root.is_symlink():
        raise BundleError("project root must be a regular directory")
    try:
        lock_path.relative_to(project_root)
    except ValueError as error:
        raise BundleError("lock file must be inside the project root") from error
    if not cache_dir.is_dir() or cache_dir.is_symlink():
        raise BundleError("cache directory must be a regular directory")
    try:
        output_dir.relative_to(project_root)
    except ValueError:
        pass
    else:
        raise BundleError("output directory must be outside the project root")
    if output_dir == cache_dir or cache_dir in output_dir.parents:
        raise BundleError("output directory must not be the source cache")

    lock = load_lock(lock_path)
    text_files, source_files = _verify_inputs(
        project_root=project_root, cache_dir=cache_dir, lock=lock
    )
    lock_sha256 = _sha256_bytes(lock.raw)
    text_files["SOURCE_AVAILABILITY.txt"] = _source_availability(lock)
    text_files["THIRD_PARTY_SOURCES_MANIFEST.json"] = _manifest(lock, lock_sha256)
    checksums = {
        **{path: _sha256_bytes(content) for path, content in text_files.items()},
        **{
            path: next(source.sha256 for source in lock.sources if source.filename == file.name)
            for path, file in source_files.items()
        },
    }
    text_files["SHA256SUMS"] = "".join(
        f"{digest}  {path}\n" for path, digest in sorted(checksums.items())
    ).encode("utf-8")

    output_dir.mkdir(mode=0o755, parents=True, exist_ok=True)
    archive = output_dir / f"{lock.bundle_name}.zip"
    checksum = archive.with_suffix(".zip.sha256")
    if archive.exists() or checksum.exists():
        raise BundleError("refusing to overwrite an existing source bundle")
    temporary_archive = archive.with_name(f".{archive.name}.tmp")
    if temporary_archive.exists():
        raise BundleError("temporary source bundle already exists")
    try:
        _write_archive(
            path=temporary_archive,
            root_name=lock.bundle_name,
            timestamp=_parse_timestamp(lock.archive_timestamp_utc),
            text_files=text_files,
            source_files=source_files,
        )
        temporary_archive.replace(archive)
    except Exception:
        temporary_archive.unlink(missing_ok=True)
        raise
    archive_digest = _sha256_file(archive)
    _atomic_write(checksum, f"{archive_digest}  {archive.name}\n".encode("ascii"))
    return BundleResult(
        archive=archive,
        checksum=checksum,
        sha256=archive_digest,
        source_count=len(source_files),
    )


def _safe_zip_members(bundle: zipfile.ZipFile, root_name: str) -> dict[str, zipfile.ZipInfo]:
    members: dict[str, zipfile.ZipInfo] = {}
    prefix = f"{root_name}/"
    for info in bundle.infolist():
        name = info.filename
        normalized = _safe_relative_path(name, label="ZIP member")
        if not normalized.startswith(prefix) or info.is_dir():
            raise BundleError("source bundle contains an unexpected root or directory member")
        if name in members:
            raise BundleError("source bundle contains a duplicate member")
        file_type = (info.external_attr >> 16) & 0o170000
        if file_type == stat.S_IFLNK:
            raise BundleError("source bundle contains a symbolic link")
        members[name] = info
    if list(members) != sorted(members):
        raise BundleError("source bundle members are not deterministically ordered")
    return members


def _zip_member_sha256(bundle: zipfile.ZipFile, info: zipfile.ZipInfo) -> str:
    digest = hashlib.sha256()
    with bundle.open(info) as stream:
        for chunk in iter(lambda: stream.read(BUFFER_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_bundle(*, archive: Path, project_root: Path, lock_path: Path) -> VerifiedBundle:
    archive = archive.resolve()
    project_root = project_root.resolve()
    lock_path = lock_path.resolve()
    _regular_file(archive, label="third-party source bundle")
    lock = load_lock(lock_path)
    if archive.name != f"{lock.bundle_name}.zip":
        raise BundleError("third-party source bundle filename does not match the lock")
    lock_sha256 = _sha256_bytes(lock.raw)
    expected_relative = {
        "SOURCE_AVAILABILITY.txt",
        "THIRD_PARTY_SOURCES_MANIFEST.json",
        "SHA256SUMS",
        *(entry.path for entry in lock.license_files),
        *(f"sources/{entry.filename}" for entry in lock.sources),
    }
    expected_members = {f"{lock.bundle_name}/{path}" for path in expected_relative}

    try:
        bundle_context = zipfile.ZipFile(archive)
    except (OSError, zipfile.BadZipFile) as error:
        raise BundleError("third-party source bundle is not a valid ZIP") from error
    with bundle_context as bundle:
        members = _safe_zip_members(bundle, lock.bundle_name)
        if set(members) != expected_members:
            raise BundleError("third-party source bundle content differs from the lock")
        prefix = f"{lock.bundle_name}/"
        manifest_name = f"{prefix}THIRD_PARTY_SOURCES_MANIFEST.json"
        availability_name = f"{prefix}SOURCE_AVAILABILITY.txt"
        checksum_name = f"{prefix}SHA256SUMS"
        if bundle.read(manifest_name) != _manifest(lock, lock_sha256):
            raise BundleError("third-party source manifest does not match the lock")
        if bundle.read(availability_name) != _source_availability(lock):
            raise BundleError("third-party source availability notice is inconsistent")
        try:
            checksum_lines = bundle.read(checksum_name).decode("ascii").splitlines()
        except UnicodeDecodeError as error:
            raise BundleError("third-party source checksums are not ASCII") from error
        checksums: dict[str, str] = {}
        for line in checksum_lines:
            digest, separator, relative = line.partition("  ")
            if (
                not separator
                or HEX_SHA256.fullmatch(digest) is None
                or relative in checksums
                or relative not in expected_relative - {"SHA256SUMS"}
            ):
                raise BundleError("third-party source checksums are malformed")
            checksums[relative] = digest
        if set(checksums) != expected_relative - {"SHA256SUMS"}:
            raise BundleError("third-party source checksums are incomplete")

        for relative, expected_digest in sorted(checksums.items()):
            info = members[f"{prefix}{relative}"]
            if _zip_member_sha256(bundle, info) != expected_digest:
                raise BundleError(f"third-party source member hash mismatch: {relative}")
        for entry in lock.sources:
            relative = f"sources/{entry.filename}"
            info = members[f"{prefix}{relative}"]
            if info.file_size != entry.size_bytes or checksums[relative] != entry.sha256:
                raise BundleError(f"third-party source member differs from lock: {entry.filename}")
        for entry in lock.license_files:
            if checksums[entry.path] != entry.sha256:
                raise BundleError(f"third-party license member differs from lock: {entry.path}")

    return VerifiedBundle(
        archive=archive,
        sha256=_sha256_file(archive),
        source_count=len(lock.sources),
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build an offline, deterministic Qt corresponding-source bundle."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--lock", type=Path, default=DEFAULT_LOCK)
    parser.add_argument("--cache-dir", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--verify-bundle", type=Path)
    return parser


def main() -> int:
    arguments = _parser().parse_args()
    project_root = arguments.project_root.resolve()
    lock_path = arguments.lock
    if not lock_path.is_absolute():
        lock_path = project_root / lock_path
    try:
        if arguments.verify_bundle is not None:
            if arguments.cache_dir is not None or arguments.output_dir is not None:
                raise BundleError("verification mode does not accept build directories")
            verified = verify_bundle(
                archive=arguments.verify_bundle,
                project_root=project_root,
                lock_path=lock_path,
            )
            print(
                json.dumps(
                    {
                        "archive": verified.archive.name,
                        "sha256": verified.sha256,
                        "source_count": verified.source_count,
                        "verified": True,
                    },
                    sort_keys=True,
                )
            )
            return 0
        if arguments.cache_dir is None or arguments.output_dir is None:
            raise BundleError("build mode requires --cache-dir and --output-dir")
        result = build_bundle(
            project_root=project_root,
            lock_path=lock_path,
            cache_dir=arguments.cache_dir,
            output_dir=arguments.output_dir,
        )
    except BundleError as error:
        raise SystemExit(f"third-party source bundle refused: {error}") from error
    print(
        json.dumps(
            {
                "archive": result.archive.name,
                "sha256": result.sha256,
                "source_count": result.source_count,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
