from __future__ import annotations

from pathlib import Path

import pikepdf
import pytest

import pdfmod.engine.pdf_structural as pdf_structural
from pdfmod.domain.errors import DangerousOutputError, OutputWriteError
from pdfmod.utils.validation import validate_pdf_output_path


def _write_pdf(path: Path) -> None:
    pdf = pikepdf.Pdf.new()
    try:
        pdf.add_blank_page(page_size=(200, 200))
        pdf.save(path)
    finally:
        pdf.close()


def test_output_validation_rejects_output_identical_to_source(tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"
    _write_pdf(source)

    with pytest.raises(DangerousOutputError):
        validate_pdf_output_path(source, (source,))


def test_output_validation_rejects_existing_output_without_deleting_it(tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"
    output = tmp_path / "output.pdf"
    _write_pdf(source)
    output.write_text("preexisting", encoding="utf-8")

    with pytest.raises(DangerousOutputError):
        validate_pdf_output_path(output, (source,))

    assert output.read_text(encoding="utf-8") == "preexisting"


def test_output_validation_rejects_non_pdf_suffix_and_missing_parent(tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"
    _write_pdf(source)

    with pytest.raises(OutputWriteError):
        validate_pdf_output_path(tmp_path / "output.txt", (source,))

    with pytest.raises(OutputWriteError):
        validate_pdf_output_path(tmp_path / "missing" / "output.pdf", (source,))


def test_output_validation_resolves_relative_and_absolute_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source.pdf"
    _write_pdf(source)
    monkeypatch.chdir(tmp_path)

    validate_pdf_output_path(Path("relative.pdf"), (source,))
    validate_pdf_output_path((tmp_path / "absolute.pdf").resolve(), (source,))

    with pytest.raises(DangerousOutputError):
        validate_pdf_output_path(Path("source.pdf"), (source,))


def test_save_write_os_error_is_reported_as_output_write_error(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.pdf"
    output = tmp_path / "output.pdf"
    _write_pdf(source)

    class FailingPdf:
        def save(self, _stream: object) -> None:
            raise OSError("permission denied for /sensitive/output.pdf")

    with pytest.raises(OutputWriteError) as raised:
        pdf_structural._save_pdf_to_new_output(FailingPdf(), output, (source,))  # type: ignore[arg-type]

    assert raised.value.technical_detail == ""
    assert not output.exists()
    assert list(tmp_path.glob(".priveopdf-*.tmp")) == []
