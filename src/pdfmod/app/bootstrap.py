from __future__ import annotations

import faulthandler
import os
import sys
from collections.abc import Sequence
from contextlib import suppress
from pathlib import Path

from PySide6.QtWidgets import QApplication

from pdfmod.app.app_info import (
    APP_DISPLAY_NAME,
    PROJECT_ROOT,
    get_app_version,
    get_runtime_app_id,
    get_runtime_display_name,
)
from pdfmod.app.beta_diagnostics import is_diagnostic_session, record_diagnostic_event
from pdfmod.app.instance_lock import SourceApplicationLock
from pdfmod.app.source_update import remove_legacy_update_launcher
from pdfmod.ui.branding import build_app_icon
from pdfmod.ui.main_window import MainWindow


def run_app(argv: Sequence[str]) -> int:
    if not document_network_isolation_verified():
        print(
            "network_isolation_unavailable: utilisez le lanceur officiel PriveoPDF.",
            file=sys.stderr,
        )
        return 78
    application_lock = SourceApplicationLock(PROJECT_ROOT)
    if application_lock.path is not None:
        if not application_lock.try_acquire_shared():
            return 0
        if application_lock.unsafe_update_marker_exists():
            application_lock.release()
            return 0
    try:
        if is_diagnostic_session():
            with suppress(OSError, RuntimeError):
                faulthandler.enable(all_threads=True)
        remove_legacy_update_launcher()
        app = QApplication(list(argv))
        runtime_app_id = get_runtime_app_id()
        app.setApplicationName(runtime_app_id)
        app.setApplicationDisplayName(get_runtime_display_name())
        app.setOrganizationName(APP_DISPLAY_NAME)
        app.setApplicationVersion(get_app_version())
        app.setDesktopFileName(runtime_app_id)
        app.setWindowIcon(build_app_icon())

        window = MainWindow(initial_files=parse_initial_file_paths(argv))
        window.show()
        record_diagnostic_event("application_started", argument_count=max(0, len(argv) - 1))
        exit_code = app.exec()
        record_diagnostic_event("application_stopped", exit_code=exit_code)
        return exit_code
    finally:
        application_lock.release()


def parse_initial_pdf_paths(argv: Sequence[str]) -> tuple[Path, ...]:
    return tuple(
        path
        for path in parse_initial_file_paths(argv)
        if path.suffix.lower() == ".pdf" and path.exists() and path.is_file()
    )


def parse_initial_file_paths(argv: Sequence[str]) -> tuple[Path, ...]:
    return tuple(Path(value) for value in list(argv)[1:])


def document_network_isolation_verified(
    *,
    network_devices_path: Path = Path("/proc/net/dev"),
    environment: dict[str, str] | None = None,
    platform_name: str | None = None,
) -> bool:
    platform = sys.platform if platform_name is None else platform_name
    if not platform.startswith("linux"):
        return True
    values = os.environ if environment is None else environment
    if values.get("PRIVEOPDF_ALLOW_UNSANDBOXED_DEV") == "1":
        return True
    if values.get("PRIVEOPDF_DOCUMENT_SANDBOX") != "1":
        return False
    try:
        lines = network_devices_path.read_text(encoding="ascii").splitlines()
    except (OSError, UnicodeError):
        return False
    interfaces: set[str] = set()
    for line in lines:
        name, separator, _details = line.partition(":")
        if separator and name.strip():
            interfaces.add(name.strip())
    return bool(interfaces) and interfaces <= {"lo"}
