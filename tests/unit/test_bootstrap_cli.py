from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from priveopdf.app.bootstrap import (
    document_network_isolation_verified,
    parse_initial_file_paths,
)

ROOT = Path(__file__).resolve().parents[2]


def test_parse_initial_file_paths_preserves_invalid_arguments(tmp_path: Path) -> None:
    missing = tmp_path / "missing.pdf"
    notes = tmp_path / "notes.txt"

    assert parse_initial_file_paths(["priveopdf", str(missing), str(notes)]) == (missing, notes)


def test_initial_file_paths_are_absolute(monkeypatch, tmp_path: Path) -> None:
    """`priveopdf rapport.pdf`: the workers run elsewhere, a relative path was lost."""
    monkeypatch.chdir(tmp_path)
    assert parse_initial_file_paths(["priveopdf", "rapport.pdf"]) == (tmp_path / "rapport.pdf",)


def test_run_app_sets_runtime_desktop_identity() -> None:
    content = (ROOT / "src" / "priveopdf" / "app" / "bootstrap.py").read_text(encoding="utf-8")

    assert "runtime_app_id = get_runtime_app_id()" in content
    assert "app.setApplicationName(runtime_app_id)" in content
    assert "app.setApplicationDisplayName(get_runtime_display_name())" in content
    assert "app.setDesktopFileName(runtime_app_id)" in content


def test_linux_bootstrap_requires_verified_document_namespace(tmp_path: Path) -> None:
    devices = tmp_path / "net-dev"
    devices.write_text(
        "Inter-| Receive | Transmit\n"
        " face |bytes packets errs drop fifo frame compressed multicast|bytes\n"
        "    lo: 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0\n",
        encoding="ascii",
    )

    assert not document_network_isolation_verified(
        network_devices_path=devices,
        environment={},
        platform_name="linux",
    )
    assert document_network_isolation_verified(
        network_devices_path=devices,
        environment={"PRIVEOPDF_DOCUMENT_SANDBOX": "1"},
        platform_name="linux",
    )
    devices.write_text(
        devices.read_text(encoding="ascii") + "  eth0: 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0\n",
        encoding="ascii",
    )
    assert not document_network_isolation_verified(
        network_devices_path=devices,
        environment={"PRIVEOPDF_DOCUMENT_SANDBOX": "1"},
        platform_name="linux",
    )


def test_public_application_window_bootstraps(tmp_path: Path) -> None:
    # Qt application styles are process-wide; do not leak them into other tests.
    subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from PySide6.QtWidgets import QApplication; "
                "from priveopdf.ui.main_window import MainWindow; "
                "app = QApplication([]); window = MainWindow(initial_files=()); "
                "window.show(); assert window.isVisible(); window.close(); app.processEvents()"
            ),
        ],
        env={
            **os.environ,
            "QT_QPA_PLATFORM": "offscreen",
            "XDG_CONFIG_HOME": str(tmp_path / "config"),
            "XDG_STATE_HOME": str(tmp_path / "state"),
        },
        check=True,
        timeout=30,
    )
