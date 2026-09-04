from __future__ import annotations

from pathlib import Path

from pdfmod.app.bootstrap import (
    document_network_isolation_verified,
    parse_initial_file_paths,
    parse_initial_pdf_paths,
)

ROOT = Path(__file__).resolve().parents[2]


def test_parse_initial_pdf_paths_accepts_existing_pdf_arguments(tmp_path: Path) -> None:
    pdf = tmp_path / "document.pdf"
    other_pdf = tmp_path / "other.PDF"
    text = tmp_path / "notes.txt"
    pdf.write_bytes(b"%PDF-1.4\n")
    other_pdf.write_bytes(b"%PDF-1.4\n")
    text.write_text("not a pdf", encoding="utf-8")

    assert parse_initial_pdf_paths(["pdfmod", str(pdf), str(text), str(other_pdf)]) == (
        pdf,
        other_pdf,
    )


def test_parse_initial_pdf_paths_ignores_missing_files(tmp_path: Path) -> None:
    assert parse_initial_pdf_paths(["pdfmod", str(tmp_path / "missing.pdf")]) == ()


def test_parse_initial_file_paths_preserves_invalid_arguments(tmp_path: Path) -> None:
    missing = tmp_path / "missing.pdf"
    notes = tmp_path / "notes.txt"

    assert parse_initial_file_paths(["pdfmod", str(missing), str(notes)]) == (missing, notes)


def test_run_app_sets_runtime_desktop_identity() -> None:
    content = (ROOT / "src" / "pdfmod" / "app" / "bootstrap.py").read_text(encoding="utf-8")

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
