from __future__ import annotations

import fcntl
import os
import stat
from contextlib import suppress
from pathlib import Path

from pdfmod.app.app_info import PROJECT_ROOT

LOCK_FILE_NAME = "priveopdf-application.lock"
UNSAFE_UPDATE_MARKER_NAME = "priveopdf-update-unsafe"
MAX_GIT_FILE_BYTES = 4_096


class SourceApplicationLock:
    """Shared app / exclusive updater lock for one source checkout."""

    def __init__(self, project_root: Path = PROJECT_ROOT) -> None:
        git_directory = _resolve_git_directory(project_root)
        self._path = git_directory / LOCK_FILE_NAME if git_directory is not None else None
        self._fd: int | None = None
        self._operation: int | None = None

    @property
    def path(self) -> Path | None:
        return self._path

    @property
    def file_descriptor(self) -> int | None:
        return self._fd

    @property
    def unsafe_update_marker_path(self) -> Path | None:
        if self._path is None:
            return None
        return self._path.parent / UNSAFE_UPDATE_MARKER_NAME

    def unsafe_update_marker_exists(self) -> bool:
        marker = self.unsafe_update_marker_path
        if marker is None:
            return False
        try:
            marker.lstat()
        except FileNotFoundError:
            return False
        except OSError:
            return True
        return True

    def try_acquire_shared(self) -> bool:
        return self._try_acquire(fcntl.LOCK_SH)

    def try_acquire_exclusive(self) -> bool:
        return self._try_acquire(fcntl.LOCK_EX)

    def _try_acquire(self, operation: int) -> bool:
        if self._fd is not None:
            return self._operation == operation
        if self._path is None or not hasattr(os, "getuid"):
            return False
        flags = os.O_RDWR | os.O_CREAT | os.O_CLOEXEC
        flags |= getattr(os, "O_NOFOLLOW", 0)
        try:
            fd = os.open(self._path, flags, 0o600)
        except OSError:
            return False
        try:
            file_stat = os.fstat(fd)
            if not stat.S_ISREG(file_stat.st_mode) or file_stat.st_uid != os.getuid():
                raise OSError("unsafe application lock file")
            os.fchmod(fd, 0o600)
            fcntl.flock(fd, operation | fcntl.LOCK_NB)
        except (BlockingIOError, OSError):
            os.close(fd)
            return False
        self._fd = fd
        self._operation = operation
        return True

    def set_inheritable(self, inheritable: bool) -> bool:
        if self._fd is None:
            return False
        try:
            os.set_inheritable(self._fd, inheritable)
        except OSError:
            return False
        return True

    def release(self) -> None:
        if self._fd is None:
            return
        fd = self._fd
        self._fd = None
        self._operation = None
        with suppress(OSError):
            os.close(fd)

    def __del__(self) -> None:
        self.release()


def _resolve_git_directory(project_root: Path) -> Path | None:
    dot_git = project_root / ".git"
    if dot_git.is_symlink():
        return None
    if dot_git.is_dir():
        return dot_git.resolve()
    if not dot_git.is_file():
        return None
    try:
        with dot_git.open("rb") as handle:
            raw = handle.read(MAX_GIT_FILE_BYTES + 1)
    except OSError:
        return None
    if len(raw) > MAX_GIT_FILE_BYTES:
        return None
    prefix = b"gitdir:"
    if not raw.lower().startswith(prefix):
        return None
    value = raw[len(prefix) :].strip()
    if not value or b"\x00" in value:
        return None
    try:
        decoded = value.decode("utf-8")
        candidate = Path(decoded)
        if not candidate.is_absolute():
            candidate = dot_git.parent / candidate
        resolved = candidate.resolve(strict=True)
    except (OSError, UnicodeError):
        return None
    return resolved if resolved.is_dir() else None
