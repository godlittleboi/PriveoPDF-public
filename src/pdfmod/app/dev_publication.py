from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pdfmod.app.app_info import PROJECT_ROOT, is_beta_runtime, is_dev_runtime
from pdfmod.ui.i18n import Locale

PublicationMode = Literal["check", "publish"]
_REQUEST_DIRECTORY = PROJECT_ROOT / ".tmp"
_REQUEST_PATH = _REQUEST_DIRECTORY / "public-source-publish.request"

_TEXT: dict[Locale, dict[str, str]] = {
    "fr": {
        "heading": "PUBLICATION DEV",
        "help": (
            "Publie ponctuellement un snapshot propre de main vers le dépôt public. "
            "L'historique privé, les PR Bêta et les fichiers internes ne sont jamais copiés."
        ),
        "check": "VÉRIFIER LA PUBLICATION",
        "publish": "METTRE À JOUR LE DÉPÔT PUBLIC",
        "check_title": "Vérifier la publication publique",
        "check_message": (
            "Fermer PriveoPDF DEV et vérifier le snapshot public du main actuel ? "
            "Aucun dépôt distant ne sera modifié."
        ),
        "publish_title": "Mettre à jour le dépôt public",
        "publish_message": (
            "Fermer PriveoPDF DEV et publier le snapshot propre du main actuel vers "
            "PriveoPDF-public ? La première publication pourra créer le dépôt public après "
            "les contrôles obligatoires."
        ),
        "queue_error_title": "Publication DEV indisponible",
        "queue_error_message": (
            "La demande n'a pas pu être préparée. Vérifie qu'aucune publication précédente "
            "n'est encore en attente."
        ),
    },
    "en": {
        "heading": "DEV PUBLICATION",
        "help": (
            "Occasionally publish a clean main snapshot to the public repository. Private "
            "history, Beta PRs, and internal files are never copied."
        ),
        "check": "CHECK PUBLICATION",
        "publish": "UPDATE PUBLIC REPOSITORY",
        "check_title": "Check public publication",
        "check_message": (
            "Close PriveoPDF DEV and validate the public snapshot of the current main? "
            "No remote repository will be changed."
        ),
        "publish_title": "Update public repository",
        "publish_message": (
            "Close PriveoPDF DEV and publish the clean snapshot of the current main to "
            "PriveoPDF-public? The first publication may create the public repository after "
            "the required checks."
        ),
        "queue_error_title": "DEV publication unavailable",
        "queue_error_message": (
            "The request could not be prepared. Check that no previous publication is still "
            "pending."
        ),
    },
}


class DevPublicationError(RuntimeError):
    pass


def dev_publication_text(key: str, locale: Locale) -> str:
    return _TEXT[locale][key]


def publication_request_path() -> Path:
    return _REQUEST_PATH


def queue_publication(mode: PublicationMode) -> Path:
    if mode not in {"check", "publish"}:
        raise DevPublicationError("unsupported publication mode")
    if not is_dev_runtime() or is_beta_runtime():
        raise DevPublicationError("publication is restricted to the canonical DEV runtime")

    try:
        _REQUEST_DIRECTORY.mkdir(mode=0o700, parents=True, exist_ok=True)
        _REQUEST_DIRECTORY.chmod(0o700)
    except OSError as error:
        raise DevPublicationError("cannot prepare publication request directory") from error

    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(_REQUEST_PATH, flags, 0o600)
    except OSError as error:
        raise DevPublicationError(
            "publication request already exists or cannot be created"
        ) from error
    try:
        with os.fdopen(descriptor, "w", encoding="ascii", newline="\n") as request:
            request.write(f"{mode}\n")
            request.flush()
            os.fsync(request.fileno())
    except BaseException:
        _REQUEST_PATH.unlink(missing_ok=True)
        raise
    return _REQUEST_PATH
