"""B3 transformations: verified private candidates, published by ProcessSupervisor."""

from __future__ import annotations

import os
import stat
import time
from collections.abc import Callable
from pathlib import Path

import pikepdf

from priveopdf.domain.errors import EncryptedPdfError, InputPathError, InvalidPdfError, PdfModError
from priveopdf.domain.jobs import (
    JobRequest,
    JobResult,
    OperationType,
    PhotocopyOptions,
    RedactOptions,
    RemoveMetadataOptions,
    WatermarkOptions,
)
from priveopdf.engine.pdf_compression import (
    CompressionIntegrityError,
    SignedPdfError,
    _geometry,
    _reject_signatures,
    has_digital_signature,
    reject_decompression_bombs,
    strip_signatures,
)
from priveopdf.utils.validation import prepare_pdf_output_path, validate_pdf_inputs


class ShareIntegrityError(PdfModError):
    user_message = "Le resultat n'a pas pu etre verifie. Aucun fichier cree."
    technical_code = "share_integrity"


class ShareSignedError(PdfModError):
    user_message = "Ce PDF porte une signature. La transformation est refusee."
    technical_code = "share_signed"


def _verify_unsigned(candidate: Path) -> None:
    """The copy announced as unsigned carries no digital signature."""

    with pikepdf.open(candidate, attempt_recovery=False, suppress_warnings=True) as result:
        if has_digital_signature(result):
            raise ShareIntegrityError()


def run_share_job(
    job: JobRequest, started: float, progress: Callable[[int, int], None] = lambda *_: None
) -> JobResult:
    options = job.options
    if not isinstance(
        options, (RemoveMetadataOptions, PhotocopyOptions, RedactOptions, WatermarkOptions)
    ):
        raise ValueError("invalid sharing options")
    source_path = job.input_files[0]
    validate_pdf_inputs((source_path,), minimum_count=1)
    candidate = prepare_pdf_output_path(
        options.output_path, job.input_files, allowed_dir=job.output_dir
    )
    try:
        fd = os.open(source_path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError:
        raise InputPathError() from None
    renderer = None
    created = False
    warnings: tuple[str, ...] = ()
    try:
        before = os.fstat(fd)
        if (
            isinstance(options, (PhotocopyOptions, RedactOptions, WatermarkOptions))
            and options.source_identity
            and options.source_identity
            != (
                before.st_dev,
                before.st_ino,
                before.st_size,
                before.st_mtime_ns,
                before.st_ctime_ns,
            )
        ):
            raise ShareIntegrityError()
        if not stat.S_ISREG(before.st_mode):
            raise InputPathError()
        with (
            os.fdopen(fd, "rb", closefd=False) as stream,
            pikepdf.open(stream, attempt_recovery=False, suppress_warnings=True) as source,
        ):
            reject_decompression_bombs(source)
            if source.check_pdf_syntax():
                raise InvalidPdfError()
            unsigned_copy = False
            try:
                _reject_signatures(source)
            except SignedPdfError:
                # Redact and Watermark may produce a copy without the signatures
                # they would invalidate, on the user's explicit choice (E4).
                if not (
                    isinstance(options, (RedactOptions, WatermarkOptions))
                    and options.allow_unsigned_copy
                ):
                    raise ShareSignedError() from None
                unsigned_copy = True
            except CompressionIntegrityError:
                raise ShareIntegrityError() from None
            if job.operation is OperationType.REMOVE_METADATA:
                if "/Info" not in source.trailer and "/Metadata" not in source.Root:
                    return JobResult(
                        False, (), (), "Aucune propriete globale a retirer.", "metadata_absent"
                    )
                geometry = _geometry(source)
                keys = set(source.Root.keys()) - {"/Metadata"}
                if "/Info" in source.trailer:
                    del source.trailer["/Info"]
                if "/Metadata" in source.Root:
                    del source.Root["/Metadata"]
                output_fd = os.open(candidate, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                created = True
                with os.fdopen(output_fd, "wb") as output:
                    source.save(output, fix_metadata_version=False)
                progress(1, 2)
                with pikepdf.open(
                    candidate, attempt_recovery=False, suppress_warnings=True
                ) as result:
                    if (
                        result.check_pdf_syntax()
                        or "/Info" in result.trailer
                        or "/Metadata" in result.Root
                        or _geometry(result) != geometry
                        or set(result.Root.keys()) != keys
                    ):
                        raise ShareIntegrityError()
                progress(2, 2)
            elif isinstance(options, WatermarkOptions):
                from priveopdf.engine.pdf_watermark import (
                    WatermarkSpec,
                    apply_watermark,
                    verify_watermark,
                )

                spec = WatermarkSpec(options.text, options.layout, options.strength)
                annotations = tuple(len(page.obj.get("/Annots", [])) for page in source.pages)
                if unsigned_copy:
                    strip_signatures(source)
                marked = apply_watermark(source, spec)
                output_fd = os.open(candidate, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                created = True
                with os.fdopen(output_fd, "wb") as output:
                    source.save(output, fix_metadata_version=False)
                progress(marked, 2 * marked)
                report = verify_watermark(
                    Path(f"/proc/self/fd/{fd}"),
                    annotations,
                    candidate,
                    spec,
                    progress=lambda done, count: progress(count + done, count * 2),
                )
                if report.pages != marked:
                    raise ShareIntegrityError()
                warnings = (f"watermark_pages_{report.pages}",)
            elif isinstance(options, RedactOptions):
                from priveopdf.engine.pdf_redaction import (
                    RedactionArea,
                    redact_to_candidate,
                    verify_redaction,
                )

                areas = tuple(RedactionArea(*area) for area in options.areas)
                expected, units = redact_to_candidate(
                    Path(f"/proc/self/fd/{fd}"), source, areas, candidate, progress
                )
                created = True
                report = verify_redaction(
                    candidate,
                    expected,
                    areas,
                    units,
                    progress=lambda done, count: progress(count + done, count * 2),
                )
                warnings = (
                    f"redaction_areas_{report.areas}",
                    f"redaction_pages_{report.redacted_pages}",
                )
            else:
                from priveopdf.engine.pdf_photocopy import (
                    build_image_pdf,
                    open_renderer,
                    render_pixels,
                    source_geometry,
                    verify_image_pdf,
                )

                # Both libraries read the same held inode, even if the pathname is changed.
                renderer = open_renderer(Path(f"/proc/self/fd/{fd}"))
                document = renderer
                geometry = source_geometry(source, document)
                total = 2 * len(geometry)

                def pages():
                    for index, dimensions in enumerate(geometry):
                        yield render_pixels(document, index, dimensions)
                        progress(index + 1, total)

                expected = build_image_pdf(pages(), candidate)
                created = True
                renderer.close()
                renderer = None
                verify_image_pdf(
                    candidate,
                    expected,
                    progress=lambda done, count: progress(count + done, count * 2),
                )
            if unsigned_copy:
                _verify_unsigned(candidate)
        after = os.fstat(fd)
        current = source_path.stat(follow_symlinks=False)

        def identity(value):
            return (
                value.st_dev,
                value.st_ino,
                value.st_size,
                value.st_mtime_ns,
                value.st_ctime_ns,
            )

        if identity(before) != identity(after) or identity(before) != identity(current):
            raise ShareIntegrityError()
        return JobResult(
            True,
            (candidate,),
            warnings,
            "PDF verifie.",
            duration_ms=int((time.monotonic() - started) * 1000),
        )
    except pikepdf.PasswordError:
        if created:
            candidate.unlink(missing_ok=True)
        raise EncryptedPdfError() from None
    except pikepdf.PdfError:
        if created:
            candidate.unlink(missing_ok=True)
        raise InvalidPdfError() from None
    except BaseException:
        if created:
            candidate.unlink(missing_ok=True)
        raise
    finally:
        if renderer is not None:
            renderer.close()
        os.close(fd)
