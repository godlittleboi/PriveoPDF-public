from __future__ import annotations

from pathlib import Path

import pikepdf
from pikepdf import Array, Dictionary, Name, Stream

from pdfmod.engine.document_inspection import (
    DocumentInspectionService,
    InspectionBudget,
)


def _write_text_pdf(path: Path) -> None:
    pdf = pikepdf.Pdf.new()
    page = pdf.add_blank_page(page_size=(200, 200))
    font = pdf.make_indirect(
        Dictionary(Type=Name.Font, Subtype=Name.Type1, BaseFont=Name.Helvetica)
    )
    page.obj["/Resources"] = Dictionary(Font=Dictionary(F1=font))
    page.obj["/Contents"] = pdf.make_indirect(Stream(pdf, b"BT /F1 12 Tf 20 20 Td (Hello) Tj ET"))
    pdf.save(path)
    pdf.close()


def _write_text_on_third_page_pdf(path: Path) -> None:
    pdf = pikepdf.Pdf.new()
    for index in range(3):
        page = pdf.add_blank_page(page_size=(200, 200))
        if index != 2:
            continue
        font = pdf.make_indirect(
            Dictionary(Type=Name.Font, Subtype=Name.Type1, BaseFont=Name.Helvetica)
        )
        page.obj["/Resources"] = Dictionary(Font=Dictionary(F1=font))
        page.obj["/Contents"] = pdf.make_indirect(
            Stream(pdf, b"BT /F1 12 Tf 20 20 Td (Late text) Tj ET")
        )
    pdf.save(path)
    pdf.close()


def _write_scan_like_pdf(path: Path) -> None:
    pdf = pikepdf.Pdf.new()
    page = pdf.add_blank_page(page_size=(200, 200))
    image = Stream(pdf, b"\xff\xff\xff")
    image["/Type"] = Name.XObject
    image["/Subtype"] = Name.Image
    image["/Width"] = 1
    image["/Height"] = 1
    image["/ColorSpace"] = Name.DeviceRGB
    image["/BitsPerComponent"] = 8
    page.obj["/Resources"] = Dictionary(XObject=Dictionary(Im1=pdf.make_indirect(image)))
    page.obj["/Contents"] = pdf.make_indirect(Stream(pdf, b"q 1 0 0 1 0 0 cm /Im1 Do Q"))
    pdf.save(path)
    pdf.close()


def _write_blank_pdf(path: Path) -> None:
    pdf = pikepdf.Pdf.new()
    pdf.add_blank_page(page_size=(200, 200))
    pdf.save(path)
    pdf.close()


def _write_encrypted_pdf(path: Path) -> None:
    pdf = pikepdf.Pdf.new()
    pdf.add_blank_page(page_size=(200, 200))
    pdf.save(path, encryption=pikepdf.Encryption(owner="owner", user="secret", R=4))
    pdf.close()


def _write_highly_compressed_text_pdf(path: Path) -> None:
    pdf = pikepdf.Pdf.new()
    page = pdf.add_blank_page(page_size=(200, 200))
    font = pdf.make_indirect(
        Dictionary(Type=Name.Font, Subtype=Name.Type1, BaseFont=Name.Helvetica)
    )
    page.obj["/Resources"] = Dictionary(Font=Dictionary(F1=font))
    decoded_content = b"BT /F1 12 Tf (Hello) Tj ET\n" + b" " * (8 * 1024 * 1024)
    page.obj["/Contents"] = pdf.make_indirect(Stream(pdf, decoded_content))
    pdf.save(path, compress_streams=True)
    pdf.close()


def _write_many_content_streams_pdf(path: Path) -> None:
    pdf = pikepdf.Pdf.new()
    page = pdf.add_blank_page(page_size=(200, 200))
    font = pdf.make_indirect(
        Dictionary(Type=Name.Font, Subtype=Name.Type1, BaseFont=Name.Helvetica)
    )
    page.obj["/Resources"] = Dictionary(Font=Dictionary(F1=font))
    page.obj["/Contents"] = Array(
        [pdf.make_indirect(Stream(pdf, b"BT (x) Tj ET")) for _ in range(4)]
    )
    pdf.save(path)
    pdf.close()


def test_document_inspection_detects_text_pdf(tmp_path: Path) -> None:
    source = tmp_path / "text.pdf"
    _write_text_pdf(source)

    inspection = DocumentInspectionService().inspect(source)

    assert inspection.can_open
    assert inspection.page_count == 1
    assert inspection.has_extractable_text
    assert inspection.scan_likelihood == "low"
    assert not inspection.ocr_recommended


def test_document_inspection_samples_multiple_pages_for_extractable_text(
    tmp_path: Path,
) -> None:
    source = tmp_path / "text-third-page.pdf"
    _write_text_on_third_page_pdf(source)

    inspection = DocumentInspectionService().inspect(source)

    assert inspection.can_open
    assert inspection.page_count == 3
    assert inspection.has_extractable_text
    assert inspection.scan_likelihood == "low"


def test_document_inspection_detects_scan_like_pdf(tmp_path: Path) -> None:
    source = tmp_path / "scan.pdf"
    _write_scan_like_pdf(source)

    inspection = DocumentInspectionService().inspect(source)

    assert inspection.can_open
    assert inspection.page_count == 1
    assert not inspection.has_extractable_text
    assert inspection.scan_likelihood == "high"
    assert inspection.ocr_recommended


def test_document_inspection_does_not_call_blank_pdf_a_scan(tmp_path: Path) -> None:
    source = tmp_path / "blank.pdf"
    _write_blank_pdf(source)

    inspection = DocumentInspectionService().inspect(source)

    assert inspection.can_open
    assert not inspection.has_extractable_text
    assert inspection.scan_likelihood == "unknown"
    assert not inspection.ocr_recommended


def test_document_inspection_reports_encrypted_pdf_without_password(tmp_path: Path) -> None:
    source = tmp_path / "protected.pdf"
    _write_encrypted_pdf(source)

    inspection = DocumentInspectionService().inspect(source)

    assert not inspection.can_open
    assert inspection.is_encrypted
    assert inspection.scan_likelihood == "unknown"
    assert "encrypted" in inspection.warnings


def test_document_inspection_reports_corrupt_pdf_as_unavailable(tmp_path: Path) -> None:
    source = tmp_path / "broken.pdf"
    source.write_text("not a pdf", encoding="utf-8")

    inspection = DocumentInspectionService().inspect(source)

    assert not inspection.can_open
    assert inspection.page_count is None
    assert inspection.scan_likelihood == "unknown"
    assert "analysis_failed" in inspection.warnings


def test_document_inspection_does_not_decompress_a_large_content_stream(
    tmp_path: Path,
) -> None:
    source = tmp_path / "compressed.pdf"
    _write_highly_compressed_text_pdf(source)
    assert source.stat().st_size < 128 * 1024

    inspection = DocumentInspectionService().inspect(source)

    assert inspection.can_open
    assert inspection.page_count == 1
    assert inspection.has_extractable_text
    assert inspection.scan_likelihood == "low"


def test_document_inspection_stops_at_the_global_stream_budget(tmp_path: Path) -> None:
    source = tmp_path / "many-streams.pdf"
    _write_many_content_streams_pdf(source)
    service = DocumentInspectionService(
        InspectionBudget(
            max_pages=1,
            max_content_streams=1,
            max_declared_content_bytes=1024,
            max_resource_objects=8,
            timeout_seconds=1,
        )
    )

    inspection = service.inspect(source)

    assert inspection.can_open
    assert "content_stream_budget_exhausted" in inspection.warnings


def test_document_inspection_has_a_soft_time_budget(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = tmp_path / "timeout.pdf"
    _write_blank_pdf(source)
    ticks = iter((0.0, 2.0, 2.0, 2.0))
    monkeypatch.setattr(
        "pdfmod.engine.document_inspection.time.monotonic",
        lambda: next(ticks, 2.0),
    )
    service = DocumentInspectionService(InspectionBudget(timeout_seconds=0.1))

    inspection = service.inspect(source)

    assert inspection.can_open
    assert "inspection_timeout" in inspection.warnings
