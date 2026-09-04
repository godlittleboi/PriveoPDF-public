#!/usr/bin/env python3
"""Verify a built PriveoPDF official freeware distribution and its sidecars."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import IO, Any

if __package__:
    from .build_third_party_sources_bundle import BundleError, verify_bundle
else:
    from build_third_party_sources_bundle import BundleError, verify_bundle

BUFFER_SIZE = 1024 * 1024
FULL_SHA = re.compile(r"[0-9a-f]{40}")
HEX_SHA256 = re.compile(r"[0-9a-f]{64}")
SAFE_ARTIFACT = re.compile(r"PriveoPDF-official-freeware-[0-9A-Za-z._-]+-[a-z0-9._-]+")
REQUIRED_FILES = {
    "LICENSE.txt",
    "NETWORK_ACTIVITY.md",
    "PRIVACY.md",
    "PROVENANCE.json",
    "QT_LIBRARY_REPLACEMENT.md",
    "QT_RUNTIME_INVENTORY.json",
    "SBOM.cdx.json",
    "SECURITY.md",
    "SHA256SUMS",
    "SUPPORT.md",
    "THIRD_PARTY_NOTICES.md",
    "licenses/GPL-3.0.txt",
    "licenses/LGPL-3.0.txt",
    "licenses/PriveoPDF-Freeware-License-EN.txt",
    "licenses/PriveoPDF-Freeware-License-FR.txt",
    "licenses/QT-NOTICE.txt",
}
FORBIDDEN_DISTRIBUTION_SUFFIXES = {
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
SENSITIVE_BYTES = (
    re.compile(rb"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----"),
    re.compile(rb"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{16,}\b", re.IGNORECASE),
    re.compile(rb"\bgithub_pat_[A-Za-z0-9_]{16,}\b", re.IGNORECASE),
    re.compile(rb"/(?:home|Users)/[A-Za-z0-9._-]+/"),
    re.compile(rb"[A-Z]:\\Users\\[A-Za-z0-9._ -]+", re.IGNORECASE),
    re.compile(rb"github\.com/godlittleboi/PriveoPDF", re.IGNORECASE),
)


class DistributionContractError(RuntimeError):
    """Raised when a freeware distribution is incomplete or unsafe."""


def _regular(path: Path, *, label: str) -> Path:
    if path.is_symlink():
        raise DistributionContractError(f"{label} must be a regular non-symlink file")
    try:
        resolved = path.resolve(strict=True)
    except OSError as error:
        raise DistributionContractError(f"cannot access {label}: {error}") from error
    if not resolved.is_file():
        raise DistributionContractError(f"{label} must be a regular non-symlink file")
    return resolved


def _safe_path(value: str) -> str:
    if not value or value.startswith("/") or "\\" in value or re.match(r"^[A-Za-z]:", value):
        raise DistributionContractError(f"unsafe distribution path: {value!r}")
    path = PurePosixPath(value)
    if any(part in {"", ".", "..", ".git"} for part in path.parts):
        raise DistributionContractError(f"distribution path traversal or Git metadata: {value!r}")
    return path.as_posix()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(BUFFER_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _scan_and_hash(stream: IO[bytes], *, label: str) -> str:
    digest = hashlib.sha256()
    overlap = b""
    for chunk in iter(lambda: stream.read(BUFFER_SIZE), b""):
        digest.update(chunk)
        sample = overlap + chunk
        for pattern in SENSITIVE_BYTES:
            if pattern.search(sample):
                raise DistributionContractError(f"sensitive content found in {label}")
        overlap = sample[-512:]
    return digest.hexdigest()


def _json_bytes(raw: bytes, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise DistributionContractError(f"invalid JSON in {label}: {error}") from error
    if not isinstance(value, dict):
        raise DistributionContractError(f"JSON root is not an object: {label}")
    return value


def _checksums(raw: bytes) -> dict[str, str]:
    try:
        lines = raw.decode("ascii").splitlines()
    except UnicodeDecodeError as error:
        raise DistributionContractError("SHA256SUMS is not ASCII") from error
    result: dict[str, str] = {}
    for line in lines:
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if match is None:
            raise DistributionContractError(f"invalid SHA256SUMS line: {line!r}")
        path = _safe_path(match.group(2))
        if path in result or path == "SHA256SUMS":
            raise DistributionContractError(f"duplicate or self checksum: {path}")
        result[path] = match.group(1)
    return result


def _properties(document: dict[str, Any]) -> dict[str, str]:
    raw = document.get("properties")
    if not isinstance(raw, list):
        raise DistributionContractError("SBOM properties is not an array")
    result: dict[str, str] = {}
    for item in raw:
        if not isinstance(item, dict):
            raise DistributionContractError("SBOM property is not an object")
        name, value = item.get("name"), item.get("value")
        if not isinstance(name, str) or not isinstance(value, str) or name in result:
            raise DistributionContractError("SBOM property is malformed or duplicated")
        result[name] = value
    return result


def _validate_sbom(document: dict[str, Any], provenance: dict[str, Any]) -> None:
    if document.get("bomFormat") != "CycloneDX" or not isinstance(document.get("components"), list):
        raise DistributionContractError("SBOM is not a CycloneDX component inventory")
    metadata = document.get("metadata")
    component = metadata.get("component") if isinstance(metadata, dict) else None
    if not isinstance(component, dict) or component.get("name") != "PriveoPDF":
        raise DistributionContractError("SBOM application component is missing")
    if component.get("version") != provenance.get("version"):
        raise DistributionContractError("SBOM and provenance versions differ")
    expected = {
        "priveopdf:artifact-license": "LicenseRef-PriveoPDF-Freeware",
        "priveopdf:internal-project-license-ref": "LicenseRef-PriveoPDF-Source-Available-1.0",
        "priveopdf:source-code-license": "LicenseRef-PriveoPDF-Source-Available-1.0",
    }
    properties = _properties(document)
    if any(properties.get(name) != value for name, value in expected.items()):
        raise DistributionContractError("SBOM license separation properties are incomplete")
    serialized = json.dumps(document, ensure_ascii=False)
    if re.search(r"/(?:home|Users)/[A-Za-z0-9._-]+/", serialized):
        raise DistributionContractError("SBOM contains a personal path")
    if re.search(r"[A-Z]:\\Users\\[A-Za-z0-9._ -]+", serialized, re.IGNORECASE):
        raise DistributionContractError("SBOM contains a Windows personal path")


def _validate_inventory(document: dict[str, Any], provenance: dict[str, Any]) -> None:
    if document.get("schema_version") != 1:
        raise DistributionContractError("Qt runtime inventory schema is unsupported")
    if document.get("platform") != provenance.get("platform"):
        raise DistributionContractError("Qt inventory and provenance platforms differ")
    if document.get("linkage") != "dynamic":
        raise DistributionContractError("Qt linkage is not declared dynamic")
    if document.get("replacement_supported") is not True:
        raise DistributionContractError("Qt library replacement is not supported")
    replacement = document.get("replacement_test")
    if not isinstance(replacement, dict) or replacement.get("performed") is not True:
        raise DistributionContractError("Qt replacement test was not performed")
    if replacement.get("result") != "pass":
        raise DistributionContractError("Qt replacement test did not pass")
    if document.get("gpl_only_modules") != []:
        raise DistributionContractError("distribution contains a GPL-only Qt module")
    if document.get("upstream_modifications") != []:
        raise DistributionContractError("upstream modifications are not covered by this bundle")
    libraries = document.get("bundled_libraries")
    if not isinstance(libraries, list) or not libraries:
        raise DistributionContractError("Qt bundled-library inventory is empty")


def _validate_provenance(
    document: dict[str, Any],
    *,
    archive: Path,
    names: set[str],
    hashes: dict[str, str],
    sizes: dict[str, int],
) -> None:
    artifact = document.get("artifact")
    if not isinstance(artifact, str) or SAFE_ARTIFACT.fullmatch(artifact) is None:
        raise DistributionContractError("provenance artifact name is invalid")
    if archive.name != f"{artifact}.zip":
        raise DistributionContractError("archive filename and provenance artifact differ")
    if document.get("license") != "LicenseRef-PriveoPDF-Freeware":
        raise DistributionContractError("official archive is not under the freeware license")
    if document.get("source_code_license") != "LicenseRef-PriveoPDF-Source-Available-1.0":
        raise DistributionContractError("source-code license reference is missing")
    source_commit = document.get("source_commit")
    if not isinstance(source_commit, str) or FULL_SHA.fullmatch(source_commit) is None:
        raise DistributionContractError("source provenance SHA is invalid")
    entrypoint = document.get("entrypoint")
    if not isinstance(entrypoint, str) or _safe_path(entrypoint) not in names:
        raise DistributionContractError("provenance entrypoint is missing from the archive")

    raw_records = document.get("files")
    if not isinstance(raw_records, list):
        raise DistributionContractError("provenance files is not an array")
    records: dict[str, dict[str, Any]] = {}
    for item in raw_records:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise DistributionContractError("provenance has a malformed file record")
        path = _safe_path(item["path"])
        if path in records:
            raise DistributionContractError(f"duplicate provenance record: {path}")
        records[path] = item
    expected = names - {"PROVENANCE.json", "SHA256SUMS"}
    if set(records) != expected:
        raise DistributionContractError("provenance file set differs from the archive")
    for path, item in records.items():
        if item.get("sha256") != hashes[path] or item.get("bytes") != sizes[path]:
            raise DistributionContractError(f"provenance hash or size differs: {path}")


def check_distribution(
    *,
    archive: Path,
    checksum_sidecar: Path,
    provenance_sidecar: Path,
    sbom_sidecar: Path,
    project_root: Path,
    source_lock_path: Path,
) -> dict[str, Any]:
    archive = _regular(archive, label="distribution archive")
    checksum_sidecar = _regular(checksum_sidecar, label="checksum sidecar")
    provenance_sidecar = _regular(provenance_sidecar, label="provenance sidecar")
    sbom_sidecar = _regular(sbom_sidecar, label="SBOM sidecar")
    try:
        project_root = project_root.resolve(strict=True)
    except OSError as error:
        raise DistributionContractError(f"cannot access project root: {error}") from error
    source_lock_path = _regular(source_lock_path, label="third-party source lock")
    if not project_root.is_dir():
        raise DistributionContractError("project root is not a directory")
    try:
        source_lock_path.relative_to(project_root)
    except ValueError as error:
        raise DistributionContractError(
            "third-party source lock is outside project root"
        ) from error

    names: list[str] = []
    hashes: dict[str, str] = {}
    sizes: dict[str, int] = {}
    metadata: dict[str, bytes] = {}
    nested_source: str | None = None
    try:
        with zipfile.ZipFile(archive) as bundle:
            seen: set[str] = set()
            for info in bundle.infolist():
                path = _safe_path(info.filename)
                if path in seen or info.is_dir():
                    raise DistributionContractError(f"duplicate or directory ZIP entry: {path}")
                seen.add(path)
                unix_mode = info.external_attr >> 16
                file_type = stat.S_IFMT(unix_mode)
                if file_type not in {0, stat.S_IFREG}:
                    raise DistributionContractError(f"non-regular ZIP entry: {path}")
                suffix = PurePosixPath(path).suffix.casefold()
                if suffix in FORBIDDEN_DISTRIBUTION_SUFFIXES:
                    raise DistributionContractError(
                        f"source or sensitive file in distribution: {path}"
                    )
                names.append(path)
                sizes[path] = info.file_size
                with bundle.open(info) as stream:
                    hashes[path] = _scan_and_hash(stream, label=path)
                if path in {
                    "LICENSE.txt",
                    "licenses/PriveoPDF-Freeware-License-FR.txt",
                    "PROVENANCE.json",
                    "QT_RUNTIME_INVENTORY.json",
                    "SBOM.cdx.json",
                    "SHA256SUMS",
                }:
                    if info.file_size > 16 * 1024 * 1024:
                        raise DistributionContractError(
                            f"metadata file is unexpectedly large: {path}"
                        )
                    metadata[path] = bundle.read(info)
            if names != sorted(names):
                raise DistributionContractError("ZIP entries are not deterministically ordered")
            name_set = set(names)
            missing = sorted(REQUIRED_FILES - name_set)
            if missing:
                raise DistributionContractError(
                    f"required distribution files are missing: {missing}"
                )
            if not any(path.startswith("app/") for path in names):
                raise DistributionContractError("application payload is empty")
            source_names = [path for path in names if path.startswith("third-party-sources/")]
            if len(source_names) != 1:
                raise DistributionContractError("exactly one third-party source bundle is required")
            nested_source = source_names[0]
    except (OSError, zipfile.BadZipFile) as error:
        raise DistributionContractError(f"cannot read distribution ZIP: {error}") from error

    name_set = set(names)
    provenance = _json_bytes(metadata["PROVENANCE.json"], label="PROVENANCE.json")
    _validate_provenance(
        provenance,
        archive=archive,
        names=name_set,
        hashes=hashes,
        sizes=sizes,
    )
    inventory = _json_bytes(
        metadata["QT_RUNTIME_INVENTORY.json"], label="QT_RUNTIME_INVENTORY.json"
    )
    _validate_inventory(inventory, provenance)
    sbom = _json_bytes(metadata["SBOM.cdx.json"], label="SBOM.cdx.json")
    _validate_sbom(sbom, provenance)

    if metadata["LICENSE.txt"] != metadata["licenses/PriveoPDF-Freeware-License-FR.txt"]:
        raise DistributionContractError("LICENSE.txt is not the canonical French freeware license")
    if b"PolyForm" in metadata["LICENSE.txt"]:
        raise DistributionContractError("PolyForm is incorrectly presented as the binary license")

    checksums = _checksums(metadata["SHA256SUMS"])
    if set(checksums) != name_set - {"SHA256SUMS"}:
        raise DistributionContractError("embedded SHA256SUMS file set differs from the archive")
    if any(checksums[path] != hashes[path] for path in checksums):
        raise DistributionContractError("embedded SHA256SUMS contains a mismatch")

    if provenance_sidecar.read_bytes() != metadata["PROVENANCE.json"]:
        raise DistributionContractError("external and embedded provenance differ")
    if sbom_sidecar.read_bytes() != metadata["SBOM.cdx.json"]:
        raise DistributionContractError("external and embedded SBOM differ")
    archive_digest = _sha256_file(archive)
    expected_sidecar = f"{archive_digest}  {archive.name}\n".encode("ascii")
    if checksum_sidecar.read_bytes() != expected_sidecar:
        raise DistributionContractError("external archive checksum differs")

    source_metadata = provenance.get("qt_source_bundle")
    if not isinstance(source_metadata, dict) or nested_source is None:
        raise DistributionContractError("Qt source provenance is missing")
    source_path = nested_source
    if source_metadata.get("filename") != PurePosixPath(source_path).name:
        raise DistributionContractError("Qt source bundle filename differs from provenance")
    source_hash = source_metadata.get("sha256")
    if not isinstance(source_hash, str) or HEX_SHA256.fullmatch(source_hash) is None:
        raise DistributionContractError("Qt source bundle provenance hash is invalid")
    if hashes[source_path] != source_hash:
        raise DistributionContractError("Qt source bundle hash differs from provenance")

    with tempfile.TemporaryDirectory(prefix="priveopdf-distribution-gate-") as raw_temp:
        temporary_source = Path(raw_temp) / PurePosixPath(source_path).name
        with (
            zipfile.ZipFile(archive) as bundle,
            bundle.open(source_path) as source,
            temporary_source.open("xb") as target,
        ):
            shutil.copyfileobj(source, target, length=BUFFER_SIZE)
        try:
            verify_bundle(
                archive=temporary_source,
                project_root=project_root,
                lock_path=source_lock_path,
            )
        except BundleError as error:
            raise DistributionContractError(
                f"third-party source bundle verification failed: {error}"
            ) from error

    return {
        "archive": archive.name,
        "file_count": len(names),
        "sha256": archive_digest,
        "source_commit": provenance.get("source_commit"),
        "status": "approved",
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--checksum", type=Path, required=True)
    parser.add_argument("--provenance", type=Path, required=True)
    parser.add_argument("--sbom", type=Path, required=True)
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--source-lock",
        type=Path,
        default=Path("compliance/third_party_sources.lock.json"),
    )
    return parser


def main() -> int:
    arguments = _parser().parse_args()
    project_root = arguments.project_root.resolve()
    source_lock = arguments.source_lock
    if not source_lock.is_absolute():
        source_lock = project_root / source_lock
    try:
        result = check_distribution(
            archive=arguments.archive,
            checksum_sidecar=arguments.checksum,
            provenance_sidecar=arguments.provenance,
            sbom_sidecar=arguments.sbom,
            project_root=project_root,
            source_lock_path=source_lock,
        )
    except DistributionContractError as error:
        print(f"Public distribution contract failed: {error}")
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
