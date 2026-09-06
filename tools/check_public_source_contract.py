#!/usr/bin/env python3
"""Apply publication gates to a cleaned PriveoPDF source snapshot."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

TOOLS_ROOT = Path(__file__).resolve().parent
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

SOURCE_LICENSE_SHA256 = (
    "0de0a67507065b4af08b64efe6295b4878ff708047a5c93dc9ad784435e601bd"  # pragma: allowlist secret
)
SOURCE_LICENSE = "LicenseRef-PriveoPDF-Source-Available-1.0"
BINARY_LICENSE = "LicenseRef-PriveoPDF-Freeware"
MANIFEST_NAME = "PUBLIC_SOURCE_MANIFEST.json"
CHECKSUMS_NAME = "SHA256SUMS"
OWNER_DECISIONS = "docs/release/PUBLIC_SOURCE_OWNER_DECISIONS.md"
REQUIRED_FILES = {
    ".github/ISSUE_TEMPLATE/bug.yml",
    ".github/ISSUE_TEMPLATE/config.yml",
    ".github/ISSUE_TEMPLATE/feature.yml",
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/workflows/ci.yml",
    "CODE_OF_CONDUCT.md",
    "CONTRIBUTING.md",
    "FEEDBACK.md",
    "GOVERNANCE.md",
    "LICENSE",
    MANIFEST_NAME,
    "README.md",
    "SECURITY.md",
    "SHA256SUMS",
    "SUPPORT.md",
    "THIRD_PARTY_NOTICES.md",
    "compliance/third_party_sources.lock.json",
    "docs/community/DISCUSSIONS_SETUP.md",
    "docs/community/DISCUSSIONS_WELCOME_EN.md",
    "docs/community/DISCUSSIONS_WELCOME_FR.md",
    "docs/community/MODERATION.md",
    "docs/compliance/NETWORK_ACTIVITY.md",
    "docs/legal/EXTERNAL_CONTRIBUTIONS_DECISION.md",
    "docs/legal/PUBLIC_HOSTING_IMPACT.md",
    "docs/legal/QT_LGPL_COMPLIANCE.md",
    "docs/legal/QT_LIBRARY_REPLACEMENT.md",
    "docs/privacy.md",
    "docs/security/CRA_REPORTING_PLAYBOOK.md",
    "docs/security/VULNERABILITY_REPORT_TEMPLATE.md",
    "docs/security/VULNERABILITY_TRIAGE.md",
    "licenses/GPL-3.0.txt",
    "licenses/LGPL-3.0.txt",
    "licenses/PriveoPDF-Freeware-License-EN.txt",
    "licenses/PriveoPDF-Freeware-License-FR.txt",
    "licenses/QT-NOTICE.txt",
    "tools/check_public_source_contract.py",
}
FORBIDDEN_PATH_PARTS = {".git", ".venv", "__pycache__", "build", "dist"}
FORBIDDEN_PATHS = {
    ".secrets.baseline",
    ".github/CODEOWNERS",
    ".github/dependabot.yml",
    "AGENT.md",
    "AGENTS.md",
    "PROMPT_SYSTEME_PROJET_CHATGPT.md",
}
FORBIDDEN_PREFIXES = (
    "docs/adr/",
    "docs/security/SECURITY_INCIDENT_TEMPLATE.md",
    "reports/",
    "tests/pdf_corpus/",
)
SENSITIVE_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----"),
    re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{16,}\b", re.IGNORECASE),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{16,}\b", re.IGNORECASE),
    re.compile(r"(?m)/(?:home|Users)/[A-Za-z0-9._-]+/"),
    re.compile(r"[A-Z]:\\Users\\[A-Za-z0-9._ -]+", re.IGNORECASE),
    re.compile(r"github\.com/godlittleboi/PriveoPDF", re.IGNORECASE),
    re.compile(
        r"\b(?:password|passwd|token|cookie)\s*[:=]\s*[\"'][^\"']{8,}[\"']",
        re.IGNORECASE,
    ),
)
PLACEHOLDERS = (
    "OWNER_" + "DECISION_REQUIRED",
    "SECURITY_CONTACT_" + "PLACEHOLDER",
    "LEGAL_ADDRESS_" + "PLACEHOLDER",
)
EXPECTED_DISCUSSION_CATEGORIES = (
    "Announcements",
    "General",
    "Ideas",
    "Polls",
    "Q&A",
    "Show and tell",
)


class SourceContractError(RuntimeError):
    """Raised when a snapshot is not ready for public publication."""


@dataclass(frozen=True)
class SnapshotContent:
    files: dict[str, bytes]
    modes: dict[str, int]
    artifact_name: str


def _safe_snapshot_path(value: str) -> str:
    if not value or value.startswith("/") or "\\" in value or re.match(r"^[A-Za-z]:", value):
        raise SourceContractError(f"unsafe snapshot path: {value!r}")
    path = PurePosixPath(value)
    if any(part in {"", ".", ".."} for part in path.parts):
        raise SourceContractError(f"snapshot path traversal: {value!r}")
    if ".git" in path.parts:
        raise SourceContractError(f"Git history or metadata found: {value}")
    return path.as_posix()


def _read_directory(root: Path, *, ignore_repository_metadata: bool = False) -> SnapshotContent:
    base = root.resolve(strict=True)
    if not base.is_dir() or root.is_symlink():
        raise SourceContractError("snapshot directory is not a regular directory")
    files: dict[str, bytes] = {}
    modes: dict[str, int] = {}
    for candidate in sorted(base.rglob("*")):
        metadata = candidate.lstat()
        raw_relative = candidate.relative_to(base).as_posix()
        if ignore_repository_metadata and PurePosixPath(raw_relative).parts[0] == ".git":
            continue
        relative = _safe_snapshot_path(raw_relative)
        if stat.S_ISLNK(metadata.st_mode):
            raise SourceContractError(f"symbolic link found in snapshot: {relative}")
        if stat.S_ISDIR(metadata.st_mode):
            continue
        if not stat.S_ISREG(metadata.st_mode):
            raise SourceContractError(f"non-regular snapshot entry: {relative}")
        files[relative] = candidate.read_bytes()
        modes[relative] = stat.S_IMODE(metadata.st_mode)
    return SnapshotContent(files=files, modes=modes, artifact_name=base.name)


def _read_zip(archive: Path) -> SnapshotContent:
    files: dict[str, bytes] = {}
    modes: dict[str, int] = {}
    roots: set[str] = set()
    try:
        with zipfile.ZipFile(archive) as bundle:
            seen: set[str] = set()
            for info in bundle.infolist():
                if info.filename in seen:
                    raise SourceContractError(f"duplicate ZIP entry: {info.filename}")
                seen.add(info.filename)
                if info.filename.startswith("/") or "\\" in info.filename:
                    raise SourceContractError(f"unsafe ZIP entry: {info.filename!r}")
                pure = PurePosixPath(info.filename.rstrip("/"))
                if len(pure.parts) < 1 or any(part in {"", ".", ".."} for part in pure.parts):
                    raise SourceContractError(f"ZIP path traversal: {info.filename!r}")
                roots.add(pure.parts[0])
                unix_mode = info.external_attr >> 16
                if stat.S_ISLNK(unix_mode):
                    raise SourceContractError(f"symbolic link found in ZIP: {info.filename}")
                if info.is_dir():
                    continue
                if len(pure.parts) < 2:
                    raise SourceContractError("ZIP files must live under one artifact root")
                relative = _safe_snapshot_path(PurePosixPath(*pure.parts[1:]).as_posix())
                if relative in files:
                    raise SourceContractError(f"duplicate normalized ZIP path: {relative}")
                files[relative] = bundle.read(info)
                modes[relative] = stat.S_IMODE(unix_mode) or 0o644
    except (OSError, zipfile.BadZipFile) as error:
        raise SourceContractError(f"cannot read snapshot ZIP: {error}") from error
    if len(roots) != 1:
        raise SourceContractError("ZIP must contain exactly one artifact root")
    return SnapshotContent(files=files, modes=modes, artifact_name=next(iter(roots)))


def read_snapshot(path: Path, *, ignore_repository_metadata: bool = False) -> SnapshotContent:
    if path.is_dir():
        return _read_directory(path, ignore_repository_metadata=ignore_repository_metadata)
    if path.is_file() and path.suffix.casefold() == ".zip":
        return _read_zip(path)
    raise SourceContractError("--snapshot must be a directory or .zip file")


def _text(content: SnapshotContent, path: str) -> str:
    try:
        return content.files[path].decode("utf-8")
    except KeyError as error:
        raise SourceContractError(f"required public file is missing: {path}") from error
    except UnicodeDecodeError as error:
        raise SourceContractError(f"required public file is not UTF-8: {path}") from error


def _json(content: SnapshotContent, path: str) -> dict[str, Any]:
    try:
        value = json.loads(_text(content, path))
    except json.JSONDecodeError as error:
        raise SourceContractError(f"invalid JSON in {path}: {error}") from error
    if not isinstance(value, dict):
        raise SourceContractError(f"JSON root is not an object: {path}")
    return value


def _checksums(raw: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in raw.splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if match is None:
            raise SourceContractError(f"invalid SHA256SUMS line: {line!r}")
        path = PurePosixPath(match.group(2))
        if path.is_absolute() or ".." in path.parts or path.as_posix() in result:
            raise SourceContractError(f"unsafe or duplicate checksum path: {path}")
        result[path.as_posix()] = match.group(1)
    return result


def _manifest_records(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw = document.get("files")
    if not isinstance(raw, list):
        raise SourceContractError("public manifest files is not an array")
    records: dict[str, dict[str, Any]] = {}
    for item in raw:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise SourceContractError("public manifest has a malformed file record")
        path = PurePosixPath(item["path"])
        if path.is_absolute() or ".." in path.parts or path.as_posix() in records:
            raise SourceContractError(f"unsafe or duplicate manifest path: {path}")
        records[path.as_posix()] = item
    return records


def _check_integrity(content: SnapshotContent) -> dict[str, Any]:
    missing = sorted(REQUIRED_FILES - set(content.files))
    if missing:
        raise SourceContractError(f"required publication files are missing: {missing}")
    if hashlib.sha256(content.files["LICENSE"]).hexdigest() != SOURCE_LICENSE_SHA256:
        raise SourceContractError("PriveoPDF source license text or locked hash differs")

    manifest = _json(content, MANIFEST_NAME)
    if manifest.get("source_license") != SOURCE_LICENSE:
        raise SourceContractError("manifest source license is not the PriveoPDF source license")
    if manifest.get("binary_license") != BINARY_LICENSE:
        raise SourceContractError("manifest binary license is not the freeware license")
    source_commit = manifest.get("private_source_commit")
    if not isinstance(source_commit, str) or re.fullmatch(r"[0-9a-f]{40}", source_commit) is None:
        raise SourceContractError("manifest source provenance SHA is missing or invalid")

    records = _manifest_records(manifest)
    expected_records = set(content.files) - {MANIFEST_NAME, CHECKSUMS_NAME}
    if set(records) != expected_records:
        raise SourceContractError("manifest file set does not match the snapshot")
    for path, record in records.items():
        data = content.files[path]
        if record.get("sha256") != hashlib.sha256(data).hexdigest():
            raise SourceContractError(f"manifest SHA-256 differs: {path}")
        if record.get("bytes") != len(data):
            raise SourceContractError(f"manifest size differs: {path}")
        expected_mode = record.get("mode")
        if expected_mode not in {"0644", "0755"}:
            raise SourceContractError(f"manifest mode is invalid: {path}")
        if int(expected_mode, 8) != content.modes[path]:
            raise SourceContractError(f"manifest mode differs: {path}")
        if not isinstance(record.get("license_expression"), str):
            raise SourceContractError(f"manifest license mapping is missing: {path}")

    checksums = _checksums(_text(content, CHECKSUMS_NAME))
    expected_checksums = set(content.files) - {CHECKSUMS_NAME}
    if set(checksums) != expected_checksums:
        raise SourceContractError("SHA256SUMS is incomplete or contains extra paths")
    for path, digest in checksums.items():
        if hashlib.sha256(content.files[path]).hexdigest() != digest:
            raise SourceContractError(f"SHA256SUMS differs: {path}")

    for path in (
        "THIRD_PARTY_NOTICES.md",
        "licenses/GPL-3.0.txt",
        "licenses/LGPL-3.0.txt",
        "licenses/QT-NOTICE.txt",
    ):
        if records[path].get("license_expression") == SOURCE_LICENSE:
            raise SourceContractError(
                f"third-party file is presented as proprietary source: {path}"
            )
    if content.files["LICENSE"] in {
        content.files["licenses/PriveoPDF-Freeware-License-FR.txt"],
        content.files["licenses/PriveoPDF-Freeware-License-EN.txt"],
    }:
        raise SourceContractError("source and executable licenses are confused")
    return manifest


def _positive_claim(line: str, positives: tuple[str, ...], negatives: tuple[str, ...]) -> bool:
    folded = line.casefold()
    return any(value in folded for value in positives) and not any(
        value in folded for value in negatives
    )


def _check_text_policy(content: SnapshotContent) -> None:
    for path, data in content.files.items():
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            continue
        for pattern in SENSITIVE_PATTERNS:
            if pattern.search(text):
                raise SourceContractError(f"sensitive content found in {path}")
        for placeholder in PLACEHOLDERS:
            if placeholder in text:
                raise SourceContractError(f"unresolved legal placeholder found in {path}")
        if path == "tools/check_public_source_contract.py":
            continue
        for line in text.splitlines():
            if _positive_claim(
                line,
                ("is open source", "est open source", "licensed as open source"),
                ("not open source", "n'est pas open source", "pas open source"),
            ):
                raise SourceContractError(f"active open-source claim found in {path}")
            if re.search(
                r"(?i)\b(?:target|cible|licen[cs]e retenue)\s*[:—-]\s*FSL(?:-1\.1-ALv2)?\b",
                line,
            ):
                raise SourceContractError(f"FSL remains an active target in {path}")
            if _positive_claim(
                line,
                (
                    "external code contributions are accepted",
                    "we accept pull requests",
                    "nous acceptons les pull requests",
                ),
                ("not accepted", "do not", "n'acceptons pas", "ne sont pas acceptées"),
            ):
                raise SourceContractError(f"external code is accepted by {path}")
            if _positive_claim(
                line,
                ("cla is active", "cla est actif", "cla actif"),
                ("no cla", "aucun cla", "n'est pas actif", "non actif"),
            ):
                raise SourceContractError(f"unapproved CLA is presented as active in {path}")
            if _positive_claim(
                line,
                (
                    "cra " + "compliant",
                    "conforme au cra",
                    "bears the ce marking",
                    "porte le marquage ce",
                ),
                ("not ", "ne ", "aucun", "no ", "sans "),
            ):
                raise SourceContractError(f"global compliance claim found in {path}")
            if re.search(
                r"(?i)\b(?:will be released on|sera (?:livré|disponible) le)\s+"
                r"(?:\d{4}-\d{2}-\d{2}|\d{1,2}[ /.-]\d{1,2}[ /.-]\d{4})",
                line,
            ):
                raise SourceContractError(f"future delivery date is guaranteed in {path}")


def _check_paths(content: SnapshotContent) -> None:
    for path in content.files:
        pure = PurePosixPath(path)
        if set(pure.parts) & FORBIDDEN_PATH_PARTS:
            raise SourceContractError(f"forbidden path part found: {path}")
        if path in FORBIDDEN_PATHS or any(path.startswith(prefix) for prefix in FORBIDDEN_PREFIXES):
            raise SourceContractError(f"forbidden public path found: {path}")


def _check_governance(content: SnapshotContent) -> None:
    contributing = _text(content, "CONTRIBUTING.md")
    normalized_contributing = " ".join(contributing.split())
    for phrase in (
        "aucune contribution de code externe",
        "external code contributions are not currently accepted",
        "Aucun CLA n’est actif",
        "No CLA is active",
    ):
        if phrase not in normalized_contributing:
            raise SourceContractError(f"CONTRIBUTING.md is missing the policy: {phrase}")

    pull_request = _text(content, ".github/PULL_REQUEST_TEMPLATE.md")
    if "Phase commentaires seulement" not in pull_request:
        raise SourceContractError("pull request template does not refuse external code")

    discussions = _text(content, "docs/community/DISCUSSIONS_SETUP.md")
    for category in EXPECTED_DISCUSSION_CATEGORIES:
        if category not in discussions:
            raise SourceContractError(f"Discussions category is missing: {category}")
    normalized_discussions = " ".join(discussions.split())
    for phrase in (
        "avant toute annonce de bêta",
        "Un utilisateur normal est donc dirigé uniquement vers Discussions",
        "La sécurité ne doit pas être une catégorie publique",
    ):
        if phrase not in normalized_discussions:
            raise SourceContractError(f"Discussions policy is missing: {phrase}")

    security = _text(content, "SECURITY.md")
    if "uniquement si" not in security or "publication publique doit" not in security:
        raise SourceContractError("security policy assumes an unverified confidential channel")
    network = _text(content, "docs/compliance/NETWORK_ACTIVITY.md")
    normalized_network = " ".join(network.split())
    for phrase in (
        "ne sont pas téléversés",
        "Aucune télémétrie n'est activée par défaut",
        "ni chemin de document",
        "L'installation des dépendances n'est pas hors ligne",
    ):
        if phrase not in normalized_network:
            raise SourceContractError(f"network inventory is missing the fact: {phrase}")

    cra = _text(content, "docs/security/CRA_REPORTING_PLAYBOOK.md")
    for phrase in ("11 septembre 2026", "24 h", "72 h", "plateforme unique"):
        if phrase not in cra:
            raise SourceContractError(f"CRA playbook is missing: {phrase}")

    workflow = _text(content, ".github/workflows/ci.yml")
    if (
        "permissions:\n  contents: read" not in workflow
        or "persist-credentials: false" not in workflow
    ):
        raise SourceContractError("public workflow permissions are not read-only")


def _check_owner_decisions(path: Path | None) -> None:
    if path is None:
        raise SourceContractError("--owner-decisions is required for publication approval")
    try:
        decisions = path.read_text(encoding="utf-8")
    except OSError as error:
        raise SourceContractError(f"cannot read owner decisions: {error}") from error
    unchecked = [line.strip() for line in decisions.splitlines() if re.match(r"^- \[ \] ", line)]
    if unchecked:
        raise SourceContractError(
            f"owner publication decisions remain unchecked ({len(unchecked)}): {unchecked[0]}"
        )
    if not re.search(
        r"(?m)^- \[[xX]\] La décision finale de publication est explicite et vise uniquement le$",
        decisions,
    ):
        raise SourceContractError("final owner publication decision is not recorded")


def check_source_contract(
    *,
    snapshot: Path,
    config_path: Path | None = None,
    expected_source: str | None = None,
    technical_only: bool = False,
    repository_checkout: bool = False,
    owner_decisions: Path | None = None,
) -> dict[str, Any]:
    if repository_checkout and not technical_only:
        raise SourceContractError(
            "repository-checkout mode is technical-only and cannot approve publication"
        )
    if config_path is not None:
        try:
            if __package__:
                from .check_public_source_snapshot import check_snapshot
            else:
                from check_public_source_snapshot import check_snapshot

            check_snapshot(
                snapshot=snapshot,
                config_path=config_path,
                expected_source=expected_source,
            )
        except (ImportError, RuntimeError) as error:
            raise SourceContractError(str(error)) from error
    content = read_snapshot(snapshot, ignore_repository_metadata=repository_checkout)
    _check_paths(content)
    manifest = _check_integrity(content)
    if expected_source is not None and manifest.get("private_source_commit") != expected_source:
        raise SourceContractError("snapshot source commit differs from expected source")
    _check_text_policy(content)
    _check_governance(content)
    if not technical_only:
        _check_owner_decisions(owner_decisions)
    return {
        "artifact": manifest.get("artifact"),
        "file_count": len(content.files),
        "source_commit": manifest.get("private_source_commit"),
        "status": "technically-valid" if technical_only else "approved",
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--expected-source")
    parser.add_argument(
        "--owner-decisions",
        type=Path,
        help="private owner-decision evidence file; required unless --technical-only",
    )
    parser.add_argument(
        "--technical-only",
        action="store_true",
        help="validate technical contracts without granting publication approval",
    )
    parser.add_argument(
        "--repository-checkout",
        action="store_true",
        help="ignore checkout .git metadata; requires --technical-only",
    )
    return parser


def main() -> int:
    arguments = _parser().parse_args()
    try:
        result = check_source_contract(
            snapshot=arguments.snapshot,
            config_path=arguments.config,
            expected_source=arguments.expected_source,
            technical_only=arguments.technical_only,
            repository_checkout=arguments.repository_checkout,
            owner_decisions=arguments.owner_decisions,
        )
    except SourceContractError as error:
        print(f"Public source contract failed: {error}")
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
