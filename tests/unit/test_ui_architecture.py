from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pdfmod.ui.job_registry import BusyDocumentRegistry


@dataclass
class _BusyProvider:
    paths: tuple[Path, ...]

    def busy_document_paths(self) -> tuple[Path, ...]:
        return self.paths


def test_busy_document_registry_uses_public_page_contract(tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"
    alias = tmp_path / "folder" / ".." / source.name
    first = _BusyProvider((source,))
    duplicate = _BusyProvider((alias,))
    registry = BusyDocumentRegistry()

    registry.register(first)
    registry.register(first)
    registry.register(duplicate)

    assert registry.is_busy(source)
    assert registry.busy_paths() == (source,)

    registry.unregister(first)

    assert registry.is_busy(source)
    assert registry.busy_paths() == (alias,)


def test_main_window_does_not_probe_private_page_structure() -> None:
    source = (Path(__file__).parents[2] / "src" / "pdfmod" / "ui" / "main_window.py").read_text(
        encoding="utf-8"
    )

    assert "hasattr(" not in source
    assert "getattr(page" not in source
    assert '"_job_runner"' not in source
    assert '"_input_path"' not in source
    assert '"_file_list"' not in source
