from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

BETA_REPOSITORY = ""
BETA_ROOT_ENV = "PRIVEOPDF_BETA_ROOT"
BETA_DIR_ENV = "PRIVEOPDF_BETA_DIR"
MAX_PREVIOUS_BETAS = 10


class BetaVersionError(RuntimeError):
    """Raised because private PR beta history is unavailable in this snapshot."""


@dataclass(frozen=True)
class BetaVersion:
    pull_request: int
    head_sha: str
    path: Path
    retained_at: datetime

    @property
    def executable(self) -> Path:
        return self.path / ".venv" / "bin" / "pdfmod"


def current_beta_version() -> BetaVersion | None:
    return None


def previous_beta_versions() -> tuple[BetaVersion, ...]:
    return ()


def isolated_beta_environment(version: BetaVersion, beta_root: Path) -> dict[str, str]:
    del version, beta_root
    return os.environ.copy()


def relaunch_beta_version(version: BetaVersion) -> int:
    del version
    raise BetaVersionError("private PR beta history is unavailable")
