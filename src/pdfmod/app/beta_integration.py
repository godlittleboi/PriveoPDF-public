from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pdfmod.app.beta_versions import BETA_REPOSITORY

INTEGRATION_MANIFEST_ENV = "PRIVEOPDF_BETA_INTEGRATION_MANIFEST"
CHECKLIST_STATE_ENV = "PRIVEOPDF_BETA_CHECKLIST_STATE"
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
MANIFEST_ID_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class IntegrationChecklistItem:
    item_id: str
    text: str


@dataclass(frozen=True)
class IntegrationPullRequest:
    number: int
    title: str
    head_sha: str
    url: str
    summary: str
    checklist: tuple[IntegrationChecklistItem, ...]

    @property
    def state_key(self) -> str:
        return f"{self.number}:{self.head_sha}"


@dataclass(frozen=True)
class BetaIntegrationManifest:
    manifest_id: str
    repository: str
    base_sha: str
    pull_requests: tuple[IntegrationPullRequest, ...]


def integration_manifest_path() -> Path | None:
    value = os.environ.get(INTEGRATION_MANIFEST_ENV, "").strip()
    return Path(value) if value else None


def load_integration_manifest(path: Path | None = None) -> BetaIntegrationManifest | None:
    manifest_path = path or integration_manifest_path()
    if manifest_path is None:
        return None
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return _parse_manifest(raw)


def _parse_manifest(raw: Any) -> BetaIntegrationManifest | None:
    if not isinstance(raw, dict) or raw.get("schema_version") != 1:
        return None
    manifest_id = raw.get("manifest_id")
    repository = raw.get("repository")
    base_sha = raw.get("base_sha")
    pull_requests = raw.get("pull_requests")
    if (
        not isinstance(manifest_id, str)
        or MANIFEST_ID_RE.fullmatch(manifest_id) is None
        or repository != BETA_REPOSITORY
        or not isinstance(base_sha, str)
        or SHA_RE.fullmatch(base_sha) is None
        or not isinstance(pull_requests, list)
        or not pull_requests
    ):
        return None

    parsed: list[IntegrationPullRequest] = []
    seen_numbers: set[int] = set()
    for entry in pull_requests:
        pull_request = _parse_pull_request(entry)
        if pull_request is None or pull_request.number in seen_numbers:
            return None
        seen_numbers.add(pull_request.number)
        parsed.append(pull_request)
    return BetaIntegrationManifest(
        manifest_id=manifest_id,
        repository=repository,
        base_sha=base_sha,
        pull_requests=tuple(parsed),
    )


def _parse_pull_request(raw: Any) -> IntegrationPullRequest | None:
    if not isinstance(raw, dict):
        return None
    number = raw.get("number")
    title = raw.get("title")
    head_sha = raw.get("head_sha")
    url = raw.get("url")
    summary = raw.get("summary")
    checklist = raw.get("checklist")
    if (
        not isinstance(number, int)
        or number < 1
        or not isinstance(title, str)
        or not title.strip()
        or not isinstance(head_sha, str)
        or SHA_RE.fullmatch(head_sha) is None
        or not isinstance(url, str)
        or url != f"https://github.com/{BETA_REPOSITORY}/pull/{number}"
        or not isinstance(summary, str)
        or not isinstance(checklist, list)
        or not checklist
    ):
        return None
    items: list[IntegrationChecklistItem] = []
    seen_ids: set[str] = set()
    for item in checklist:
        if not isinstance(item, dict):
            return None
        item_id = item.get("id")
        text = item.get("text")
        if (
            not isinstance(item_id, str)
            or not item_id
            or item_id in seen_ids
            or not isinstance(text, str)
            or not text.strip()
        ):
            return None
        seen_ids.add(item_id)
        items.append(IntegrationChecklistItem(item_id=item_id, text=text.strip()))
    return IntegrationPullRequest(
        number=number,
        title=title.strip(),
        head_sha=head_sha,
        url=url,
        summary=summary.strip(),
        checklist=tuple(items),
    )


class IntegrationChecklistStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or _default_state_path()
        self._state = self._read()

    def checked(self, pull_request: IntegrationPullRequest, item_id: str) -> bool:
        values = self._state.get(pull_request.state_key, {})
        return values.get(item_id) is True

    def set_checked(
        self,
        pull_request: IntegrationPullRequest,
        item_id: str,
        checked: bool,
    ) -> None:
        values = self._state.setdefault(pull_request.state_key, {})
        values[item_id] = bool(checked)
        self._write()

    def completed_count(self, pull_request: IntegrationPullRequest) -> int:
        return sum(self.checked(pull_request, item.item_id) for item in pull_request.checklist)

    def _read(self) -> dict[str, dict[str, bool]]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        if not isinstance(raw, dict):
            return {}
        cleaned: dict[str, dict[str, bool]] = {}
        for state_key, values in raw.items():
            if not isinstance(state_key, str) or not isinstance(values, dict):
                continue
            cleaned[state_key] = {
                item_id: checked
                for item_id, checked in values.items()
                if isinstance(item_id, str) and isinstance(checked, bool)
            }
        return cleaned

    def _write(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(self._state, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.chmod(0o600)
        temporary.replace(self.path)


def _default_state_path() -> Path:
    explicit_path = os.environ.get(CHECKLIST_STATE_ENV, "").strip()
    if explicit_path:
        return Path(explicit_path)
    state_root = os.environ.get("XDG_STATE_HOME", "").strip()
    root = Path(state_root) if state_root else Path.home() / ".local" / "state"
    return root / "priveopdf" / "beta-integration-checklists.json"
