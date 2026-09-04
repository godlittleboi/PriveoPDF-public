from __future__ import annotations

from pathlib import Path

from pdfmod.domain.errors import (
    InputPathError,
    InvalidPdfError,
)
from pdfmod.utils.secure_paths import prepare_new_output_path


def validate_pdf_inputs(input_paths: tuple[Path, ...], minimum_count: int = 1) -> None:
    if len(input_paths) < minimum_count:
        raise InvalidPdfError()
    for path in input_paths:
        if path.suffix.lower() != ".pdf":
            raise InvalidPdfError()
        if not path.exists() or not path.is_file():
            raise InputPathError()


def prepare_pdf_output_path(
    output_path: Path,
    input_paths: tuple[Path, ...],
    *,
    allowed_dir: Path | None = None,
) -> Path:
    return prepare_new_output_path(
        output_path,
        input_paths,
        allowed_dir=allowed_dir,
        required_suffix=".pdf",
    )


def validate_pdf_output_path(output_path: Path, input_paths: tuple[Path, ...]) -> None:
    prepare_pdf_output_path(output_path, input_paths)
