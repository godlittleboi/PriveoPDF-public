"""Password protection and removal in the isolated, local PDF worker."""

from __future__ import annotations

import os
import stat
import time

import pikepdf

from priveopdf.domain.errors import InputPathError, InvalidPdfError, PdfModError, WrongPasswordError
from priveopdf.domain.jobs import (
    JobRequest,
    JobResult,
    OperationType,
    ProtectOptions,
    UnlockOptions,
    validate_pdf_password,
)
from priveopdf.engine.pdf_compression import (
    CompressionIntegrityError,
    SignedPdfError,
    _geometry,
    _reject_signatures,
    reject_decompression_bombs,
)
from priveopdf.utils.validation import prepare_pdf_output_path, validate_pdf_inputs


class PasswordSignedPdfError(PdfModError):
    user_message = "La protection d'un PDF signe numeriquement ne peut pas etre modifiee."
    technical_code = "password_signed_pdf"


class PasswordIntegrityError(InvalidPdfError):
    user_message = "L'integrite du PDF n'a pas pu etre verifiee. Aucun fichier cree."
    technical_code = "password_integrity"


class PdfNotEncryptedError(PdfModError):
    user_message = "Ce PDF n'est pas chiffre. Il n'a pas besoin d'etre deverrouille."
    technical_code = "pdf_not_encrypted"


class PdfAlreadyEncryptedError(PdfModError):
    user_message = "Ce PDF est deja protege. Deverrouillez-le avant de le proteger a nouveau."
    technical_code = "pdf_already_encrypted"


def run_password_job(job: JobRequest, started: float) -> JobResult:
    """Write a verified private candidate; the supervisor publishes it atomically.

    Passwords remain in process memory and the anonymous worker input pipe.
    Do not move them into options, native job JSON, filenames or diagnostics.
    """
    protecting = job.operation is OperationType.PROTECT_PDF
    options = (
        job.require_options(ProtectOptions) if protecting else job.require_options(UnlockOptions)
    )
    password = validate_pdf_password(job.password)
    source_path = job.input_files[0]
    validate_pdf_inputs((source_path,), minimum_count=1)
    candidate = prepare_pdf_output_path(
        options.output_path, job.input_files, allowed_dir=job.output_dir
    )
    try:
        fd = os.open(source_path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError:
        raise InputPathError() from None
    created = False
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):
            raise InputPathError()
        try:
            with (
                os.fdopen(fd, "rb", closefd=False) as stream,
                pikepdf.open(
                    stream,
                    password="" if protecting else password,
                    attempt_recovery=False,
                    suppress_warnings=True,
                ) as source,
            ):
                # Protect opened the source without a password: an empty user
                # password only carries restrictions, replaced by the new
                # encryption (issue 446). A real password raised PasswordError.
                if not protecting:
                    if not source.is_encrypted:
                        raise PdfNotEncryptedError()
                    if not (source.user_password_matched or source.owner_password_matched):
                        raise WrongPasswordError()
                reject_decompression_bombs(source)
                if source.check_pdf_syntax():
                    raise PasswordIntegrityError()
                try:
                    _reject_signatures(source)
                except SignedPdfError:
                    raise PasswordSignedPdfError() from None
                except CompressionIntegrityError:
                    raise PasswordIntegrityError() from None
                geometry = _geometry(source)
                if not geometry:
                    raise InvalidPdfError()
                catalog_keys = set(source.Root.keys())
                encryption = (
                    pikepdf.Encryption(
                        owner=password,
                        user=password,
                        R=6,
                        aes=True,
                        metadata=True,
                        allow=pikepdf.Permissions(modify_assembly=True),
                    )
                    if protecting
                    else False
                )
                output_fd = os.open(candidate, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                created = True
                with os.fdopen(output_fd, "wb") as output:
                    source.save(output, encryption=encryption)
            with pikepdf.open(
                candidate,
                password=password if protecting else "",
                attempt_recovery=False,
                suppress_warnings=True,
            ) as result:
                if (
                    result.is_encrypted != protecting
                    or result.check_pdf_syntax()
                    or _geometry(result) != geometry
                    or not catalog_keys.issubset(result.Root.keys())
                    or (protecting and (result.encryption.R != 6 or result.encryption.bits != 256))
                ):
                    raise PasswordIntegrityError()
            if protecting:
                try:
                    with pikepdf.open(candidate, password="", suppress_warnings=True):
                        raise PasswordIntegrityError()
                except pikepdf.PasswordError:
                    pass
        except pikepdf.PasswordError:
            if protecting:
                raise PdfAlreadyEncryptedError() from None
            raise WrongPasswordError() from None
        except pikepdf.PdfError:
            raise InvalidPdfError() from None
        after = os.fstat(fd)
        if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        ):
            raise PasswordIntegrityError()
        return JobResult(
            success=True,
            output_files=(candidate,),
            warnings=(),
            user_message="PDF protege." if protecting else "PDF deverrouille.",
            duration_ms=int((time.monotonic() - started) * 1000),
        )
    except BaseException:
        if created:
            candidate.unlink(missing_ok=True)
        raise
    finally:
        os.close(fd)
