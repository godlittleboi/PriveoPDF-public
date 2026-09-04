from __future__ import annotations

from importlib import metadata
from pathlib import Path

from pdfmod.app import app_info


def test_app_version_uses_package_metadata_first(monkeypatch, tmp_path: Path) -> None:  # noqa: ANN001
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nversion = "9.9.9"\n', encoding="utf-8")
    monkeypatch.setattr(app_info, "PYPROJECT_PATH", pyproject)
    monkeypatch.setattr(app_info.metadata, "version", lambda distribution: "1.2.3")

    assert app_info.get_app_version() == "1.2.3"


def test_app_version_falls_back_to_pyproject_in_dev(monkeypatch, tmp_path: Path) -> None:  # noqa: ANN001
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nversion = "2.0.0"\n', encoding="utf-8")
    monkeypatch.setattr(app_info, "PYPROJECT_PATH", pyproject)

    def raise_not_found(distribution: str) -> str:
        raise metadata.PackageNotFoundError(distribution)

    monkeypatch.setattr(app_info.metadata, "version", raise_not_found)

    assert app_info.get_app_version() == "2.0.0"


def test_runtime_identity_distinguishes_public_dev_and_beta(monkeypatch, tmp_path: Path) -> None:  # noqa: ANN001
    marker = tmp_path / "owner-decisions.md"
    monkeypatch.setattr(app_info, "DEV_RUNTIME_MARKER", marker)
    monkeypatch.delenv(app_info.DEV_RUNTIME_ENV, raising=False)
    monkeypatch.delenv(app_info.BETA_RUNTIME_ENV, raising=False)
    assert app_info.is_dev_runtime() is False
    assert app_info.is_beta_runtime() is False
    assert app_info.get_runtime_app_id() == app_info.APP_ID
    assert app_info.get_runtime_display_name() == app_info.APP_DISPLAY_NAME

    monkeypatch.setenv(app_info.DEV_RUNTIME_ENV, "1")
    assert app_info.is_dev_runtime() is False
    assert app_info.get_runtime_display_name() == app_info.APP_DISPLAY_NAME

    marker.write_text("private canonical marker\n", encoding="utf-8")
    assert app_info.is_dev_runtime() is True
    assert app_info.get_runtime_app_id() == app_info.APP_ID
    assert app_info.get_runtime_display_name() == app_info.DEV_APP_DISPLAY_NAME

    monkeypatch.setenv(app_info.BETA_RUNTIME_ENV, "1")
    assert app_info.is_beta_runtime() is True
    assert app_info.is_dev_runtime() is False
    assert app_info.get_runtime_app_id() == app_info.BETA_APP_ID
    assert app_info.get_runtime_display_name() == app_info.BETA_APP_DISPLAY_NAME


def test_display_version_keeps_installed_version_separate(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(app_info, "get_app_version", lambda: "0.1.0")

    assert app_info.get_display_version("en") == "v0.1.0 beta"
