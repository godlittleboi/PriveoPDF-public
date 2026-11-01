"""Hand a system package to the desktop's installer (`apt://` link, apturl).

PriveoPDF makes no network connection and gains no privilege: the system
installer asks the user's password and downloads the package itself, exactly
as the Software Manager would. Used for Tesseract language models
(`tesseract-ocr-<code>`), the only packages the application asks for.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from priveopdf.domain.ocr_languages import is_ocr_language_code

_PACKAGE_PREFIX = "tesseract-ocr-"
_CHILD_ENVIRONMENT = frozenset(
    {
        "DISPLAY",
        "LANG",
        "LC_ALL",
        "PATH",
        "WAYLAND_DISPLAY",
        "XAUTHORITY",
        "XDG_CACHE_HOME",
        "XDG_CONFIG_HOME",
        "XDG_DATA_HOME",
        "XDG_RUNTIME_DIR",
        "XDG_STATE_HOME",
        "XDG_SESSION_TYPE",
        "DBUS_SESSION_BUS_ADDRESS",
    }
)


def ocr_model_package(code: str) -> str:
    """Debian package of a language model; the code is validated first."""

    if not is_ocr_language_code(code):
        raise ValueError("invalid OCR model code")
    return f"{_PACKAGE_PREFIX}{code}"


def install_command(code: str) -> str:
    """The terminal fallback shown to the user."""

    return f"sudo apt install {ocr_model_package(code)}"


_APT_SCHEME = "x-scheme-handler/apt"


def _apt_handler_registered() -> bool:
    """True when a desktop entry handles `apt://` (apturl, Software Manager).

    Read from the desktop's own caches, without a subprocess on the UI thread:
    without a handler `xdg-open` would start and do nothing.
    """

    home = Path.home()
    data_home = os.environ.get("XDG_DATA_HOME") or str(home / ".local/share")
    data_dirs = [data_home, *(os.environ.get("XDG_DATA_DIRS") or "/usr/share").split(":")]
    config_home = os.environ.get("XDG_CONFIG_HOME") or str(home / ".config")
    files = [Path(d) / "applications" / "mimeinfo.cache" for d in data_dirs if d]
    files += [Path(config_home) / "mimeapps.list", Path(data_home) / "applications/mimeapps.list"]
    for path in files:
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        section = ""
        for line in lines:
            line = line.strip()
            if line.startswith("["):
                section = line
                continue
            key, _, value = line.partition("=")
            if (
                section != "[Removed Associations]"
                and key.strip() == _APT_SCHEME
                and value.strip(" ;")
            ):
                return True
    return False


def system_installer_available() -> bool:
    return shutil.which("xdg-open") is not None and _apt_handler_registered()


def open_system_installer(code: str) -> bool:
    """Open `apt://tesseract-ocr-<code>` with the desktop handler. False when the
    desktop has no opener; the caller then shows the command."""

    package = ocr_model_package(code)
    opener = shutil.which("xdg-open")
    if opener is None:
        return False
    environment = {k: v for k, v in os.environ.items() if k in _CHILD_ENVIRONMENT and v}
    environment.setdefault("LANG", "C.UTF-8")
    try:
        process = subprocess.Popen(  # noqa: S603 -- resolved opener, validated package name
            (opener, f"apt://{package}"),
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            start_new_session=True,
        )
    except OSError:
        return False
    return process.pid > 0
