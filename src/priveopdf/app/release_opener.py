"""Open a broker-verified release page in the user's desktop session.

The update broker runs in a sandbox without the user's home, session bus or
desktop settings: a browser started there cannot use the user's browser. The
launcher therefore runs this helper outside every sandbox. It only reads the
request file written by the broker, accepts a single release page of the public
repository and reports whether ``xdg-open`` could hand it to the desktop.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import time
from collections.abc import Callable, Sequence
from pathlib import Path

OPEN_RELEASE_REQUEST = "open-release.request"
OPEN_RELEASE_STATUS = "open-release.status"
# The broker waits this long for a status; keep the opener's own wait below it.
STATUS_WAIT_SECONDS = 2.5
OPENER_GRACE_SECONDS = 1.5
XDG_OPEN = Path("/usr/bin/xdg-open")  # xdg-utils, a package dependency; never from PATH (F05)
_RELEASE_URL = re.compile(
    r"https://github\.com/godlittleboi/PriveoPDF(?:-public)?/releases(?:/tag/[A-Za-z0-9._-]{1,64})?\Z"
)


def is_release_page(url: str) -> bool:
    return _RELEASE_URL.match(url) is not None


def open_release_page(url: str, *, grace_seconds: float = OPENER_GRACE_SECONDS) -> bool:
    """True when ``xdg-open`` accepted the page, or is still running its handler."""
    if not XDG_OPEN.is_file() or not is_release_page(url):
        return False
    try:
        process = subprocess.Popen(  # noqa: S603 - fixed opener, validated URL
            (str(XDG_OPEN), url),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            start_new_session=True,
        )
    except OSError:
        return False
    try:
        return process.wait(timeout=grace_seconds) == 0
    except subprocess.TimeoutExpired:
        return True  # some handlers stay in the foreground once the browser is up


def serve_once(directory: Path, opener: Callable[[str], bool] = open_release_page) -> bool:
    """Handle one pending request; False when there is none."""
    request = directory / OPEN_RELEASE_REQUEST
    try:
        descriptor = os.open(request, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError:
        return False
    with os.fdopen(descriptor, "rb") as stream:
        raw = stream.read(4096)
    request.unlink(missing_ok=True)
    url = raw.decode("ascii", errors="replace").strip()
    status = "ok" if opener(url) else "failed"
    pending = directory / f".{OPEN_RELEASE_STATUS}.{os.getpid()}"
    pending.write_text(status + "\n", encoding="ascii")
    pending.replace(directory / OPEN_RELEASE_STATUS)
    return True


def main(arguments: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", type=Path, required=True)
    directory = parser.parse_args(arguments).dir.resolve(strict=True)
    while True:
        if not serve_once(directory):
            time.sleep(0.1)


if __name__ == "__main__":
    raise SystemExit(main())
