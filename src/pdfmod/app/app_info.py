from __future__ import annotations

import os
import tomllib
from importlib import metadata
from pathlib import Path
from typing import Literal

from pdfmod.ui.i18n import Locale

ProductChannel = Literal["alpha", "beta", "stable"]
ProductEdition = Literal["free", "paid"]

PROJECT_DISTRIBUTION = "pdf-modificator"
APP_ID = "priveopdf"
APP_DISPLAY_NAME = "PriveoPDF"
DEV_APP_DISPLAY_NAME = "PriveoPDF DEV"
BETA_APP_ID = "priveopdf-beta"
BETA_APP_DISPLAY_NAME = "PriveoPDF Bêta"
DEV_RUNTIME_ENV = "PRIVEOPDF_DEV"
BETA_RUNTIME_ENV = "PRIVEOPDF_BETA"
PROJECT_ROOT = Path(__file__).resolve().parents[3]
PYPROJECT_PATH = PROJECT_ROOT / "pyproject.toml"
DEV_RUNTIME_MARKER = PROJECT_ROOT / "docs" / "release" / "PUBLIC_SOURCE_OWNER_DECISIONS.md"


def is_beta_runtime() -> bool:
    return os.environ.get(BETA_RUNTIME_ENV) == "1"


def is_dev_runtime() -> bool:
    return (
        not is_beta_runtime()
        and os.environ.get(DEV_RUNTIME_ENV) == "1"
        and DEV_RUNTIME_MARKER.is_file()
    )


def get_runtime_app_id() -> str:
    return BETA_APP_ID if is_beta_runtime() else APP_ID


def get_runtime_display_name() -> str:
    if is_beta_runtime():
        return BETA_APP_DISPLAY_NAME
    if is_dev_runtime():
        return DEV_APP_DISPLAY_NAME
    return APP_DISPLAY_NAME


def get_app_version() -> str:
    package_version = _version_from_package_metadata(PROJECT_DISTRIBUTION)
    if package_version is not None:
        return package_version
    pyproject_version = _version_from_pyproject(PYPROJECT_PATH)
    if pyproject_version is not None:
        return pyproject_version
    return "0.0.0-dev"


def get_app_channel() -> ProductChannel:
    return "beta"


def get_app_edition() -> ProductEdition:
    return "free"


def get_display_version(locale: Locale) -> str:
    channel_labels = {
        "fr": {"alpha": "alpha", "beta": "beta", "stable": "stable"},
        "en": {"alpha": "alpha", "beta": "beta", "stable": "stable"},
    }
    channel = get_app_channel()
    return f"v{get_app_version()} {channel_labels[locale][channel]}"


def _version_from_package_metadata(distribution_name: str) -> str | None:
    try:
        return metadata.version(distribution_name)
    except metadata.PackageNotFoundError:
        return None


def _version_from_pyproject(path: Path) -> str | None:
    if not path.exists():
        return None
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError:
        return None
    version = data.get("project", {}).get("version")
    return version if isinstance(version, str) and version else None
