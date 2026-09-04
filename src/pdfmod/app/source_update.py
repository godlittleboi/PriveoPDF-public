from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass
from pathlib import Path

from pdfmod.app.app_info import PROJECT_ROOT, get_app_channel
from pdfmod.app.update_checker import UpdateCheckResult

SOURCE_UPDATE_KIND = "git_checkout"
SOURCE_UPDATE_REPOSITORY = ""
EXPECTED_ORIGIN_URLS: frozenset[str] = frozenset()


class SourceUpdateError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class SourceUpdateCheckResult(UpdateCheckResult):
    target_revision: str = ""


def is_valid_source_revision(value: str) -> bool:
    return len(value) == 40 and all(character in "0123456789abcdef" for character in value.lower())


def source_checkout_available(project_root: Path = PROJECT_ROOT) -> bool:
    del project_root
    return False


def check_source_update(
    *,
    project_root: Path = PROJECT_ROOT,
    allowed_origins: Collection[str] = EXPECTED_ORIGIN_URLS,
    git_executable: str | None = None,
    checked_at: float | None = None,
    environment: Mapping[str, str] | None = None,
) -> UpdateCheckResult:
    del project_root, allowed_origins, git_executable, environment
    return UpdateCheckResult(
        status="not_verified",
        installed_version="",
        checked_at=0.0 if checked_at is None else checked_at,
        error_code="source_updater_unavailable",
        repo_full_name="",
        source=SOURCE_UPDATE_KIND,
        channel=get_app_channel(),
    )


def remove_legacy_update_launcher(
    *,
    project_root: Path = PROJECT_ROOT,
    data_home: Path | None = None,
) -> bool:
    del project_root, data_home
    return False
