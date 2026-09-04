from __future__ import annotations


class PdfModError(Exception):
    user_message = "L'operation PDF a echoue."
    technical_code = "pdf_error"

    def __init__(self, message: str | None = None, *, technical_detail: str = "") -> None:
        if message is not None and not isinstance(message, str):
            raise TypeError("message must be a string or None")
        if not isinstance(technical_detail, str):
            raise TypeError("technical_detail must be a string")
        super().__init__(message or self.user_message)
        self.technical_detail = technical_detail


class InvalidPdfError(PdfModError):
    user_message = "Le PDF est invalide ou corrompu."
    technical_code = "invalid_pdf"


class InvalidPageSelectionError(InvalidPdfError):
    user_message = "La selection de pages est invalide."
    technical_code = "invalid_page_selection"


class InvalidPageOrderError(InvalidPdfError):
    user_message = "L'ordre des pages est invalide."
    technical_code = "invalid_page_order"


class InvalidSplitPlanError(InvalidPdfError):
    user_message = "Le plan de division est invalide."
    technical_code = "invalid_split_plan"


class EncryptedPdfError(PdfModError):
    user_message = "Le fichier semble protege par mot de passe."
    technical_code = "encrypted_pdf"


class WrongPasswordError(PdfModError):
    user_message = "Le mot de passe fourni ne permet pas d'ouvrir ce PDF."
    technical_code = "wrong_password"


class InputPathError(PdfModError):
    user_message = "Le fichier d'entree ne peut pas etre lu."
    technical_code = "input_path_error"


class UnsupportedPdfFeatureError(PdfModError):
    user_message = "Ce PDF utilise une fonctionnalite non prise en charge."
    technical_code = "unsupported_pdf_feature"


class OutputWriteError(PdfModError):
    user_message = "Le fichier de sortie ne peut pas etre ecrit."
    technical_code = "output_write_error"


class DangerousOutputError(OutputWriteError):
    user_message = "La sortie demandee est dangereuse ou deja utilisee."
    technical_code = "dangerous_output"


class InternalPdfEngineError(PdfModError):
    user_message = "L'operation PDF a rencontre une erreur interne."
    technical_code = "internal_pdf_engine_error"


class ExternalToolMissingError(PdfModError):
    user_message = "Un outil local requis est absent."
    technical_code = "external_tool_missing"


class ExternalToolFailedError(PdfModError):
    user_message = "Un outil local a echoue."
    technical_code = "external_tool_failed"


class UserCancelledError(PdfModError):
    user_message = "L'operation a ete annulee."
    technical_code = "user_cancelled"
