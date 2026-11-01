"""Native whole-document compression, called only by the isolated PDF worker."""

from __future__ import annotations

import itertools
import json
import os
import stat
import time
import zlib

import pikepdf

from priveopdf.domain.errors import (
    EncryptedPdfError,
    InputPathError,
    InvalidPdfError,
    PdfModError,
    PdfStructureTooComplexError,
)
from priveopdf.domain.jobs import CompressionMetrics, CompressionOptions, JobRequest, JobResult
from priveopdf.utils.validation import prepare_pdf_output_path, validate_pdf_inputs


class SignedPdfError(PdfModError):
    user_message = "La compression d'un PDF signe numeriquement n'est pas prise en charge."
    technical_code = "compression_signed_pdf"


class CompressionIntegrityError(InvalidPdfError):
    user_message = "La compression n'a pas pu verifier l'integrite du PDF. Aucun fichier cree."
    technical_code = "compression_integrity"


# Decompression bombs (audit 26/10): one Flate stream inflating past 256 MiB,
# or bomb-like streams (over 16 MiB at a ratio above 100:1) totalling 256 MiB.
# Real scans and images stay far below either bound.
_BOMB_STREAM_BYTES = 256 * 1024 * 1024
_BOMB_SUSPECT_BYTES = 16 * 1024 * 1024
_BOMB_SUSPECT_RATIO = 100
_BOMB_INFLATE_CHUNK = 1024 * 1024
# Past this much inflated data the check stops: the job's own limits apply.
_BOMB_CHECK_BUDGET = 2 * 1024 * 1024 * 1024


def _inflated_size(raw: bytes, limit: int) -> int:
    """Bytes `raw` inflates to, counted without keeping them; stops past `limit`."""

    inflater = zlib.decompressobj()
    data, total = raw, 0
    while True:
        chunk = inflater.decompress(data, _BOMB_INFLATE_CHUNK)
        total += len(chunk)
        data = inflater.unconsumed_tail
        if total > limit or (not chunk and not data):
            return total


def reject_decompression_bombs(pdf: pikepdf.Pdf) -> None:
    """Refuse a PDF carrying a decompression bomb before qpdf decodes it.

    qpdf's syntax check decodes every stream: a 300 MB bomb kept the worker busy
    for the whole job delay, then failed with a misleading write error.
    """

    budget = _BOMB_CHECK_BUDGET
    suspect = 0
    for obj in itertools.islice(pdf.objects, 100_001):
        if budget <= 0:
            return
        if not isinstance(obj, pikepdf.Stream):
            continue
        filters = obj.get("/Filter")
        first = filters[0] if isinstance(filters, pikepdf.Array) and len(filters) else filters
        if first != pikepdf.Name.FlateDecode:
            continue
        try:
            raw = obj.read_raw_bytes()
            size = _inflated_size(raw, _BOMB_STREAM_BYTES)
        except (zlib.error, pikepdf.PdfError, ValueError):
            continue  # a damaged stream is the integrity check's business
        budget -= size
        if size > _BOMB_STREAM_BYTES:
            raise PdfStructureTooComplexError()
        if size > _BOMB_SUSPECT_BYTES and size > _BOMB_SUSPECT_RATIO * max(1, len(raw)):
            suspect += size
            if suspect > _BOMB_STREAM_BYTES:
                raise PdfStructureTooComplexError()


def _reject_signatures(pdf: pikepdf.Pdf) -> None:
    # Follow only signature-bearing native structures, including direct fields.
    # Bound both indirect objects and direct children; cyclic fields fail closed.
    # F08: never materialise more objects than the bound allows.
    objects = list(itertools.islice(pdf.objects, 100_001))
    if len(objects) > 100_000:
        raise CompressionIntegrityError()
    pending = [(pdf.Root, False), *((obj, False) for obj in objects)]
    seen: set[tuple[tuple[int, int], bool]] = set()
    remaining = 100_000
    while pending:
        remaining -= 1
        if remaining < 0 or len(pending) > 100_000:
            raise CompressionIntegrityError()
        obj, signature_value = pending.pop()
        if not isinstance(obj, pikepdf.Dictionary):
            continue
        if obj.is_indirect:
            key = (obj.objgen, signature_value)
            if key in seen:
                continue
            seen.add(key)
        if (
            signature_value
            or obj.get("/Type") in (pikepdf.Name.Sig, pikepdf.Name.DocTimeStamp)
            or "/ByteRange" in obj
        ):
            contents = obj.get("/Contents")
            if isinstance(contents, pikepdf.String) and any(bytes(contents)):
                raise SignedPdfError()
            # Empty signature fields are allowed; malformed populated values are not.
            if "/ByteRange" in obj:
                raise CompressionIntegrityError()
        for name in ("/AcroForm", "/Perms", "/DocMDP", "/UR", "/UR3", "/V"):
            child = obj.get(name)
            if isinstance(child, pikepdf.Dictionary):
                pending.append((child, name == "/V" and obj.get("/FT") == pikepdf.Name.Sig))
        for name in ("/Fields", "/Kids"):
            children = obj.get(name)
            if isinstance(children, pikepdf.Array):
                if len(children) > remaining:
                    raise CompressionIntegrityError()
                pending.extend((child, False) for child in children)


def has_digital_signature(pdf: pikepdf.Pdf) -> bool:
    """True when `pdf` carries at least one populated digital signature.

    A malformed signature structure is not a signature: the job that follows
    reports it as an integrity failure.
    """

    try:
        _reject_signatures(pdf)
    except SignedPdfError:
        return True
    except CompressionIntegrityError:
        return False
    return False


def strip_signatures(pdf: pikepdf.Pdf) -> int:
    """Remove every digital signature value from `pdf`, for a copy that carries none.

    Signature widgets keep their appearance: a visual signature stays a visual
    signature. Document permissions (`/Perms`) and the validation material
    (`/DSS`: certificates, revocation data, PAdES extensions) depend on the
    removed signatures and go with them. Returns the number of values removed;
    the caller verifies the saved copy with `_reject_signatures`.
    """

    removed = 0
    root = pdf.Root
    for name in ("/Perms", "/DSS"):
        if name in root:
            del root[name]
    extensions = root.get("/Extensions")
    if isinstance(extensions, pikepdf.Dictionary) and "/ESIC" in extensions:
        del extensions["/ESIC"]
        if len(extensions.keys()) == 0:
            del root["/Extensions"]
    pending: list[pikepdf.Object] = []
    acroform = root.get("/AcroForm")
    if isinstance(acroform, pikepdf.Dictionary):
        if "/SigFlags" in acroform:
            del acroform["/SigFlags"]
        pending.append(acroform)
    # A signature widget missing from the field tree still sits in a page.
    for page in pdf.pages:
        annots = page.obj.get("/Annots")
        if isinstance(annots, pikepdf.Array):
            pending.extend(annots)
    seen: set[tuple[int, int]] = set()
    remaining = 100_000
    while pending:
        remaining -= 1
        if remaining < 0:
            raise CompressionIntegrityError()
        obj = pending.pop()
        if not isinstance(obj, pikepdf.Dictionary):
            continue
        if obj.is_indirect:
            if obj.objgen in seen:
                continue
            seen.add(obj.objgen)
        if "/V" in obj and (obj.get("/FT") == pikepdf.Name.Sig or _parent_is_signature(obj)):
            del obj["/V"]
            removed += 1
        for name in ("/Fields", "/Kids"):
            children = obj.get(name)
            if isinstance(children, pikepdf.Array):
                if len(children) > remaining:
                    raise CompressionIntegrityError()
                pending.extend(children)
    return removed


def _parent_is_signature(field: pikepdf.Dictionary) -> bool:
    # A widget inherits `/FT` from its parent field (ISO 32000-1, 12.7.3.1).
    parent = field.get("/Parent")
    for _ in range(32):
        if not isinstance(parent, pikepdf.Dictionary):
            return False
        if "/FT" in parent:
            return parent.get("/FT") == pikepdf.Name.Sig
        parent = parent.get("/Parent")
    return False


def _geometry(pdf: pikepdf.Pdf) -> tuple[tuple[object, ...], ...]:
    return tuple(
        (
            tuple(page.mediabox),
            tuple(page.cropbox),
            str(page.obj.get("/Rotate", 0)),
            str(page.obj.get("/UserUnit", 1)),
            *(str(page.obj.get(key, "")) for key in ("/TrimBox", "/BleedBox", "/ArtBox")),
            len(page.obj.get("/Annots", [])),
        )
        for page in pdf.pages
    )


def run_compression_job(job: JobRequest, started: float) -> JobResult:
    """Create a private candidate; ProcessSupervisor owns final publication.

    The supervisor remaps output_path to its own private temporary directory.
    A direct engine caller must likewise supply a private staging destination.
    """
    options = job.require_options(CompressionOptions)
    source_path = job.input_files[0]
    validate_pdf_inputs((source_path,), minimum_count=1)
    candidate = prepare_pdf_output_path(
        options.output_path, job.input_files, allowed_dir=job.output_dir
    )
    # Keep the source inode open while qpdf reads lazily. This qualified Linux
    # path avoids reopening a pathname that another process could replace.
    try:
        fd = os.open(source_path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError:
        raise InputPathError() from None
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):
            raise InputPathError()
        config = {
            "inputFile": f"/proc/self/fd/{fd}",
            "outputFile": str(candidate),
            # Empty user password (restrictions only, issue 446): write a plain copy.
            "decrypt": "",
            "compressStreams": "y",
            "recompressFlate": "",
            "compressionLevel": "9",
            "objectStreams": "generate",
            "decodeLevel": "generalized",
            "suppressRecovery": "",
            "noWarn": "",
            "removeUnreferencedResources": "no",
            "keepInlineImages": "",
        }
        if options.profile == "strong":
            config.update(optimizeImages="", jpegQuality="85")
        native_job = pikepdf.Job(json.dumps(config))
        try:
            with native_job.create_pdf() as source:
                # qpdf 12.3.2 can read this missing self-entry without recovery.
                # Match the entire native diagnostic, including our own input
                # identifier; every other warning still blocks compression.
                # The candidate below must be completely warning-free.
                missing_xref_self_entry = (
                    f"WARNING: {config['inputFile']}: xref entry for the xref stream itself "
                    "is missing - a common error handled correctly by qpdf and most other "
                    "applications"
                )
                reject_decompression_bombs(source)
                if native_job.has_warnings or any(
                    warning != missing_xref_self_entry for warning in source.check_pdf_syntax()
                ):
                    raise CompressionIntegrityError()
                _reject_signatures(source)
                geometry = _geometry(source)
                if not geometry:
                    raise InvalidPdfError()
                catalog_keys = set(source.Root.keys())
                native_job.write_pdf(source)
            if native_job.has_warnings or native_job.exit_code != 0:
                raise CompressionIntegrityError()
            with pikepdf.open(candidate, attempt_recovery=False, suppress_warnings=True) as result:
                if (
                    result.is_encrypted
                    or result.check_pdf_syntax()
                    or _geometry(result) != geometry
                    or not catalog_keys.issubset(result.Root.keys())
                ):
                    raise CompressionIntegrityError()
        except pikepdf.PasswordError:
            raise EncryptedPdfError() from None
        except pikepdf.PdfError:
            raise InvalidPdfError() from None
        after = os.fstat(fd)
        if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        ):
            raise CompressionIntegrityError()
        sizes = CompressionMetrics(before.st_size, candidate.stat().st_size)
        gained = sizes.candidate_bytes < sizes.source_bytes
        if not gained:
            candidate.unlink()
        return JobResult(
            success=gained,
            output_files=(candidate,) if gained else (),
            warnings=(),
            user_message="Compression terminee." if gained else "Aucune reduction obtenue.",
            technical_detail="" if gained else "compression_no_gain",
            duration_ms=int((time.monotonic() - started) * 1000),
            compression=sizes,
        )
    except BaseException:
        candidate.unlink(missing_ok=True)
        raise
    finally:
        os.close(fd)
