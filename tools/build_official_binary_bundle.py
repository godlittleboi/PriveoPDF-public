from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import IO, Any

if __package__:
    from .build_third_party_sources_bundle import (
        BundleError as SourceBundleError,
    )
    from .build_third_party_sources_bundle import load_lock, verify_bundle
else:
    from build_third_party_sources_bundle import (
        BundleError as SourceBundleError,
    )
    from build_third_party_sources_bundle import load_lock, verify_bundle

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_LOCK = Path("compliance/third_party_sources.lock.json")
BUFFER_SIZE = 1024 * 1024
FULL_SHA = re.compile(r"[0-9a-f]{40}")
SAFE_VERSION = re.compile(r"[0-9][0-9A-Za-z._-]{0,63}")
SAFE_PLATFORM = re.compile(r"[a-z0-9][a-z0-9._-]{1,63}")
HEX_SHA256 = re.compile(r"[0-9a-f]{64}")
FORBIDDEN_PARTS = {
    ".git",
    ".github",
    ".venv",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "build",
    "dist",
}
FORBIDDEN_SUFFIXES = {
    ".bat",
    ".c",
    ".cc",
    ".cmd",
    ".cpp",
    ".cxx",
    ".env",
    ".go",
    ".h",
    ".hpp",
    ".hxx",
    ".java",
    ".js",
    ".jsx",
    ".key",
    ".kt",
    ".kts",
    ".log",
    ".p12",
    ".pdf",
    ".pem",
    ".pfx",
    ".php",
    ".ps1",
    ".py",
    ".pyc",
    ".pyo",
    ".qml",
    ".rb",
    ".rs",
    ".sh",
    ".swift",
    ".ts",
    ".tsx",
    ".ui",
}
SENSITIVE_PATTERNS = (
    re.compile(r"/(?:home|Users)/[A-Za-z0-9._-]+/"),
    re.compile(r"[A-Z]:\\Users\\[A-Za-z0-9._ -]+", re.IGNORECASE),
    re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----"),
    re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{16,}\b", re.IGNORECASE),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{16,}\b", re.IGNORECASE),
    re.compile(r"github\.com/godlittleboi/PriveoPDF", re.IGNORECASE),
)
REQUIRED_LEGAL_FILES = (
    "licenses/PriveoPDF-Freeware-License-FR.txt",
    "licenses/PriveoPDF-Freeware-License-EN.txt",
    "licenses/LGPL-3.0.txt",
    "licenses/GPL-3.0.txt",
    "licenses/QT-NOTICE.txt",
    "THIRD_PARTY_NOTICES.md",
    "SECURITY.md",
    "SUPPORT.md",
    "docs/compliance/NETWORK_ACTIVITY.md",
    "docs/privacy.md",
    "docs/legal/QT_LIBRARY_REPLACEMENT.md",
)
PAYLOAD_METADATA = {"QT_RUNTIME_INVENTORY.json", "SBOM.cdx.json"}


class BinaryBundleError(RuntimeError):
    pass


@dataclass(frozen=True)
class ArchiveItem:
    content: bytes | None = None
    source: Path | None = None
    mode: int = 0o644
    stored: bool = False


@dataclass(frozen=True)
class BinaryBundleResult:
    archive: Path
    checksum: Path
    provenance: Path
    sbom: Path
    sha256: str
    file_count: int


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(BUFFER_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _item_sha256(item: ArchiveItem) -> str:
    if item.content is not None:
        return _sha256_bytes(item.content)
    if item.source is None:
        raise BinaryBundleError("archive item has no content")
    return _sha256_file(item.source)


def _item_size(item: ArchiveItem) -> int:
    if item.content is not None:
        return len(item.content)
    if item.source is None:
        raise BinaryBundleError("archive item has no content")
    return item.source.stat().st_size


def _safe_relative(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise BinaryBundleError(f"{label} must be a non-empty string")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise BinaryBundleError(f"{label} contains path traversal")
    if "\\" in value or path.as_posix() != value:
        raise BinaryBundleError(f"{label} must be a normalized POSIX path")
    return value


def _regular_file(path: Path, *, label: str) -> None:
    try:
        mode = path.lstat().st_mode
    except OSError as error:
        raise BinaryBundleError(f"missing {label}: {path}") from error
    if not stat.S_ISREG(mode) or path.is_symlink():
        raise BinaryBundleError(f"{label} must be a regular non-symlink file: {path}")


def _scan_text(label: str, content: bytes) -> None:
    if b"\0" in content:
        return
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        return
    for pattern in SENSITIVE_PATTERNS:
        if pattern.search(text):
            raise BinaryBundleError(f"sensitive or private value found in {label}")


def _scan_file(label: str, path: Path) -> None:
    carry = ""
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(BUFFER_SIZE), b""):
            candidate = carry + chunk.decode("latin-1")
            for pattern in SENSITIVE_PATTERNS:
                if pattern.search(candidate):
                    raise BinaryBundleError(f"sensitive or private value found in {label}")
            carry = candidate[-512:]


def _walk_json_strings(value: object) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from _walk_json_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_json_strings(item)


def _read_json(path: Path, *, label: str) -> tuple[dict[str, Any], bytes]:
    _regular_file(path, label=label)
    raw = path.read_bytes()
    _scan_text(label, raw)
    try:
        document = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise BinaryBundleError(f"{label} is not valid UTF-8 JSON") from error
    if not isinstance(document, dict):
        raise BinaryBundleError(f"{label} must contain a JSON object")
    for value in _walk_json_strings(document):
        _scan_text(label, value.encode("utf-8"))
    canonical = (json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )
    return document, canonical


def _package_versions(lock: Any) -> dict[str, str]:
    return {package["name"].casefold(): package["version"] for package in lock.runtime_packages}


def _validate_inventory(
    *, document: dict[str, Any], payload_dir: Path, source_lock: Any, platform: str
) -> None:
    if document.get("schema_version") != 1:
        raise BinaryBundleError("unsupported Qt runtime inventory schema")
    qt_versions = {entry.version for entry in source_lock.sources if entry.component == "Qt"}
    if len(qt_versions) != 1 or document.get("qt_version") not in qt_versions:
        raise BinaryBundleError("Qt runtime inventory version differs from the source lock")
    if document.get("platform") != platform:
        raise BinaryBundleError("Qt runtime inventory platform differs from the requested bundle")
    if document.get("linkage") != "dynamic" or document.get("replacement_supported") is not True:
        raise BinaryBundleError("Qt runtime must use replaceable dynamic libraries")
    if document.get("upstream_modifications") != []:
        raise BinaryBundleError("patched Qt sources are not covered by the current source lock")
    if document.get("gpl_only_modules") != []:
        raise BinaryBundleError("GPL-only Qt modules are not permitted in this distribution model")

    imports = document.get("imported_modules")
    if not isinstance(imports, list) or set(imports) != set(source_lock.qt_import_modules):
        raise BinaryBundleError("Qt runtime imports differ from the audited source inventory")
    packages = document.get("runtime_packages")
    if not isinstance(packages, list) or any(not isinstance(item, dict) for item in packages):
        raise BinaryBundleError("Qt runtime package inventory is invalid")
    actual_packages = {
        str(item.get("name", "")).casefold(): str(item.get("version", "")) for item in packages
    }
    if actual_packages != _package_versions(source_lock):
        raise BinaryBundleError("Qt runtime package versions differ from the source lock")

    libraries = document.get("bundled_libraries")
    if not isinstance(libraries, list) or not libraries:
        raise BinaryBundleError("Qt runtime inventory must list bundled libraries")
    seen_paths: set[str] = set()
    for item in libraries:
        if not isinstance(item, dict):
            raise BinaryBundleError("Qt bundled library inventory contains an invalid entry")
        relative = _safe_relative(item.get("path"), label="Qt library path")
        if relative in seen_paths:
            raise BinaryBundleError("Qt runtime inventory contains duplicate library paths")
        seen_paths.add(relative)
        library = payload_dir.joinpath(*PurePosixPath(relative).parts)
        _regular_file(library, label="inventoried Qt library")
        expression = item.get("license_expression")
        if not isinstance(expression, str) or "LGPL-3.0" not in expression:
            raise BinaryBundleError("Qt library lacks an LGPL-3.0 license expression")

    replacement = document.get("replacement_test")
    if not isinstance(replacement, dict):
        raise BinaryBundleError("Qt replacement test record is missing")
    if replacement.get("performed") is not True or replacement.get("result") != "pass":
        raise BinaryBundleError("Qt replacement test has not passed")
    tested_library = _safe_relative(
        replacement.get("tested_library"), label="replacement-tested Qt library"
    )
    if tested_library not in seen_paths:
        raise BinaryBundleError("replacement test does not reference an inventoried library")


def _component_versions(document: dict[str, Any]) -> dict[str, str]:
    components = document.get("components")
    if not isinstance(components, list):
        raise BinaryBundleError("SBOM components must be a list")
    result: dict[str, str] = {}
    for component in components:
        if not isinstance(component, dict):
            raise BinaryBundleError("SBOM contains an invalid component")
        name = component.get("name")
        version = component.get("version")
        if isinstance(name, str) and isinstance(version, str):
            result[name.casefold()] = version
    return result


def _validate_sbom(document: dict[str, Any], source_lock: Any) -> None:
    if document.get("bomFormat") != "CycloneDX":
        raise BinaryBundleError("binary SBOM must use CycloneDX")
    metadata = document.get("metadata")
    if not isinstance(metadata, dict) or not isinstance(metadata.get("component"), dict):
        raise BinaryBundleError("binary SBOM application component is missing")
    application = metadata["component"]
    if application.get("name") != "PriveoPDF":
        raise BinaryBundleError("binary SBOM application name is invalid")
    licenses = application.get("licenses")
    if not isinstance(licenses, list) or not any(
        isinstance(item, dict)
        and isinstance(item.get("license"), dict)
        and item["license"].get("name") == "LicenseRef-PriveoPDF-Freeware"
        for item in licenses
    ):
        raise BinaryBundleError("binary SBOM does not identify the freeware license")
    versions = _component_versions(document)
    for name, version in _package_versions(source_lock).items():
        if versions.get(name) != version:
            raise BinaryBundleError(f"binary SBOM is missing locked component {name} {version}")


def _augment_sbom(document: dict[str, Any]) -> bytes:
    required = {
        "priveopdf:artifact-license": "LicenseRef-PriveoPDF-Freeware",
        "priveopdf:internal-project-license-ref": "LicenseRef-PriveoPDF-Source-Available-1.0",
        "priveopdf:source-code-license": "LicenseRef-PriveoPDF-Source-Available-1.0",
    }
    raw_properties = document.setdefault("properties", [])
    if not isinstance(raw_properties, list) or any(
        not isinstance(item, dict) for item in raw_properties
    ):
        raise BinaryBundleError("binary SBOM properties must be a list of objects")
    properties: dict[str, str] = {}
    for item in raw_properties:
        name = item.get("name")
        value = item.get("value")
        if not isinstance(name, str) or not isinstance(value, str) or name in properties:
            raise BinaryBundleError("binary SBOM contains malformed or duplicate properties")
        properties[name] = value
    for name, value in required.items():
        if name in properties and properties[name] != value:
            raise BinaryBundleError(f"binary SBOM property conflicts with {name}")
        properties[name] = value
    document["properties"] = [
        {"name": name, "value": value} for name, value in sorted(properties.items())
    ]
    return (json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def _payload_items(payload_dir: Path) -> dict[str, ArchiveItem]:
    items: dict[str, ArchiveItem] = {}
    for path in sorted(payload_dir.rglob("*")):
        relative_path = path.relative_to(payload_dir)
        relative = relative_path.as_posix()
        if path.is_symlink():
            raise BinaryBundleError(f"payload contains a symbolic link: {relative}")
        if path.is_dir():
            continue
        _regular_file(path, label="payload file")
        if relative in PAYLOAD_METADATA:
            continue
        if set(relative_path.parts) & FORBIDDEN_PARTS:
            raise BinaryBundleError(f"payload contains private or generated state: {relative}")
        if path.suffix.casefold() in FORBIDDEN_SUFFIXES:
            raise BinaryBundleError(
                f"payload contains a forbidden source/sensitive file: {relative}"
            )
        _scan_file(relative, path)
        mode = stat.S_IMODE(path.stat().st_mode)
        items[f"app/{relative}"] = ArchiveItem(source=path, mode=mode)
    if not items:
        raise BinaryBundleError("binary payload is empty")
    return items


def _legal_items(project_root: Path) -> dict[str, ArchiveItem]:
    items: dict[str, ArchiveItem] = {}
    for relative in REQUIRED_LEGAL_FILES:
        source = project_root.joinpath(*PurePosixPath(relative).parts)
        _regular_file(source, label="distribution legal file")
        content = source.read_bytes()
        _scan_text(relative, content)
        target = {
            "docs/compliance/NETWORK_ACTIVITY.md": "NETWORK_ACTIVITY.md",
            "docs/privacy.md": "PRIVACY.md",
            "docs/legal/QT_LIBRARY_REPLACEMENT.md": "QT_LIBRARY_REPLACEMENT.md",
        }.get(relative, relative)
        items[target] = ArchiveItem(content=content)
    freeware = items["licenses/PriveoPDF-Freeware-License-FR.txt"].content
    if freeware is None:
        raise BinaryBundleError("canonical freeware license is unavailable")
    items["LICENSE.txt"] = ArchiveItem(content=freeware)
    return items


def _timestamp(epoch: int) -> datetime:
    try:
        value = datetime.fromtimestamp(epoch, tz=UTC)
    except (OverflowError, OSError, ValueError) as error:
        raise BinaryBundleError("source date epoch is invalid") from error
    if value.year < 1980 or value.year > 2107:
        raise BinaryBundleError("source date epoch is outside the ZIP range")
    return value


def _zip_info(path: str, timestamp: datetime, *, mode: int, stored: bool) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(path, date_time=timestamp.timetuple()[:6])
    info.compress_type = zipfile.ZIP_STORED if stored else zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = (mode & 0xFFFF) << 16
    return info


def _copy(source: IO[bytes], target: IO[bytes]) -> None:
    while chunk := source.read(BUFFER_SIZE):
        target.write(chunk)


def _write_zip(path: Path, items: dict[str, ArchiveItem], timestamp: datetime) -> None:
    with path.open("w+b") as archive_stream:
        with zipfile.ZipFile(
            archive_stream,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
            allowZip64=True,
        ) as bundle:
            for relative, item in sorted(items.items()):
                info = _zip_info(relative, timestamp, mode=item.mode, stored=item.stored)
                if item.content is not None:
                    bundle.writestr(
                        info,
                        item.content,
                        compress_type=info.compress_type,
                        compresslevel=None if item.stored else 9,
                    )
                    continue
                if item.source is None:
                    raise BinaryBundleError(f"archive item has no source: {relative}")
                info.file_size = item.source.stat().st_size
                with (
                    item.source.open("rb") as source,
                    bundle.open(info, "w", force_zip64=True) as target,
                ):
                    _copy(source, target)
        archive_stream.flush()
        os.fsync(archive_stream.fileno())
    path.chmod(0o644)


def _write_exclusive(path: Path, content: bytes) -> None:
    with path.open("xb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    path.chmod(0o644)


def build_binary_bundle(
    *,
    project_root: Path,
    payload_dir: Path,
    third_party_sources: Path,
    source_lock_path: Path,
    output_dir: Path,
    version: str,
    platform: str,
    entrypoint: str,
    source_commit: str,
    source_date_epoch: int,
) -> BinaryBundleResult:
    project_root = project_root.resolve()
    payload_dir = payload_dir.resolve()
    output_dir = output_dir.resolve()
    third_party_sources = third_party_sources.resolve()
    source_lock_path = source_lock_path.resolve()
    if not project_root.is_dir() or project_root.is_symlink():
        raise BinaryBundleError("project root must be a regular directory")
    try:
        source_lock_path.relative_to(project_root)
    except ValueError as error:
        raise BinaryBundleError("source lock must be inside the project root") from error
    if SAFE_VERSION.fullmatch(version) is None:
        raise BinaryBundleError("version contains unsupported characters")
    if SAFE_PLATFORM.fullmatch(platform) is None:
        raise BinaryBundleError("platform contains unsupported characters")
    if FULL_SHA.fullmatch(source_commit) is None:
        raise BinaryBundleError("source commit must be a full lowercase SHA-1")
    if not payload_dir.is_dir() or payload_dir.is_symlink():
        raise BinaryBundleError("payload directory must be a regular directory")
    try:
        payload_dir.relative_to(project_root)
    except ValueError:
        pass
    else:
        raise BinaryBundleError("binary payload must be staged outside the project root")
    try:
        third_party_sources.relative_to(project_root)
    except ValueError:
        pass
    else:
        raise BinaryBundleError("third-party source bundle must be outside the project root")
    try:
        output_dir.relative_to(project_root)
    except ValueError:
        pass
    else:
        raise BinaryBundleError("output directory must be outside the project root")
    if output_dir == payload_dir or payload_dir in output_dir.parents:
        raise BinaryBundleError("output directory must not be inside the payload")

    entrypoint = _safe_relative(entrypoint, label="entrypoint")
    entrypoint_path = payload_dir.joinpath(*PurePosixPath(entrypoint).parts)
    _regular_file(entrypoint_path, label="binary entrypoint")
    if platform.startswith("linux") and not (entrypoint_path.stat().st_mode & stat.S_IXUSR):
        raise BinaryBundleError("Linux entrypoint is not executable")
    if platform.startswith("windows") and entrypoint_path.suffix.casefold() != ".exe":
        raise BinaryBundleError("Windows entrypoint must be an .exe file")

    source_lock = load_lock(source_lock_path)
    try:
        verified_sources = verify_bundle(
            archive=third_party_sources,
            project_root=project_root,
            lock_path=source_lock_path,
        )
    except SourceBundleError as error:
        raise BinaryBundleError(
            f"third-party source bundle verification failed: {error}"
        ) from error

    inventory, inventory_bytes = _read_json(
        payload_dir / "QT_RUNTIME_INVENTORY.json", label="Qt runtime inventory"
    )
    _validate_inventory(
        document=inventory,
        payload_dir=payload_dir,
        source_lock=source_lock,
        platform=platform,
    )
    sbom, _sbom_input_bytes = _read_json(payload_dir / "SBOM.cdx.json", label="binary SBOM")
    _validate_sbom(sbom, source_lock)
    sbom_bytes = _augment_sbom(sbom)

    items = _payload_items(payload_dir)
    for path, item in _legal_items(project_root).items():
        if path in items:
            raise BinaryBundleError(f"duplicate distribution path: {path}")
        items[path] = item
    items["QT_RUNTIME_INVENTORY.json"] = ArchiveItem(content=inventory_bytes)
    items["SBOM.cdx.json"] = ArchiveItem(content=sbom_bytes)
    items[f"third-party-sources/{third_party_sources.name}"] = ArchiveItem(
        source=third_party_sources,
        stored=True,
    )

    base_records = [
        {
            "bytes": _item_size(item),
            "mode": f"{item.mode:04o}",
            "path": path,
            "sha256": _item_sha256(item),
        }
        for path, item in sorted(items.items())
    ]
    provenance_document = {
        "artifact": f"PriveoPDF-official-freeware-{version}-{platform}",
        "entrypoint": f"app/{entrypoint}",
        "files": base_records,
        "license": "LicenseRef-PriveoPDF-Freeware",
        "platform": platform,
        "qt_source_bundle": {
            "filename": third_party_sources.name,
            "sha256": verified_sources.sha256,
        },
        "schema_version": 1,
        "source_code_license": "LicenseRef-PriveoPDF-Source-Available-1.0",
        "source_commit": source_commit,
        "source_date_epoch": source_date_epoch,
        "version": version,
    }
    provenance_bytes = (
        json.dumps(provenance_document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    items["PROVENANCE.json"] = ArchiveItem(content=provenance_bytes)
    checksums = "".join(
        f"{_item_sha256(item)}  {path}\n" for path, item in sorted(items.items())
    ).encode("ascii")
    items["SHA256SUMS"] = ArchiveItem(content=checksums)

    output_dir.mkdir(mode=0o755, parents=True, exist_ok=True)
    artifact_name = provenance_document["artifact"]
    archive = output_dir / f"{artifact_name}.zip"
    checksum_path = archive.with_suffix(".zip.sha256")
    provenance_path = archive.with_suffix(".zip.provenance.json")
    sbom_path = archive.with_suffix(".zip.sbom.cdx.json")
    outputs = (archive, checksum_path, provenance_path, sbom_path)
    if any(path.exists() for path in outputs):
        raise BinaryBundleError("refusing to overwrite an existing binary distribution")
    temporary = archive.with_name(f".{archive.name}.tmp")
    if temporary.exists():
        raise BinaryBundleError("temporary binary distribution already exists")
    try:
        _write_zip(temporary, items, _timestamp(source_date_epoch))
        temporary.replace(archive)
        archive_sha256 = _sha256_file(archive)
        _write_exclusive(
            checksum_path,
            f"{archive_sha256}  {archive.name}\n".encode("ascii"),
        )
        _write_exclusive(provenance_path, provenance_bytes)
        _write_exclusive(sbom_path, sbom_bytes)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise

    return BinaryBundleResult(
        archive=archive,
        checksum=checksum_path,
        provenance=provenance_path,
        sbom=sbom_path,
        sha256=archive_sha256,
        file_count=len(items),
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a deterministic, compliance-gated PriveoPDF freeware bundle."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--payload-dir", type=Path, required=True)
    parser.add_argument("--third-party-sources", type=Path, required=True)
    parser.add_argument("--source-lock", type=Path, default=DEFAULT_SOURCE_LOCK)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--platform", required=True)
    parser.add_argument("--entrypoint", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--source-date-epoch", type=int, required=True)
    return parser


def main() -> int:
    arguments = _parser().parse_args()
    project_root = arguments.project_root.resolve()
    source_lock = arguments.source_lock
    if not source_lock.is_absolute():
        source_lock = project_root / source_lock
    try:
        result = build_binary_bundle(
            project_root=project_root,
            payload_dir=arguments.payload_dir,
            third_party_sources=arguments.third_party_sources,
            source_lock_path=source_lock,
            output_dir=arguments.output_dir,
            version=arguments.version,
            platform=arguments.platform,
            entrypoint=arguments.entrypoint,
            source_commit=arguments.source_commit,
            source_date_epoch=arguments.source_date_epoch,
        )
    except BinaryBundleError as error:
        raise SystemExit(f"official binary bundle refused: {error}") from error
    print(
        json.dumps(
            {
                "archive": result.archive.name,
                "file_count": result.file_count,
                "sha256": result.sha256,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
