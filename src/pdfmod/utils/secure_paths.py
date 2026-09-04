from __future__ import annotations

import os
import secrets
import stat
import threading
import unicodedata
from collections.abc import Callable, Sequence
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO, Final

from pdfmod.domain.errors import DangerousOutputError, OutputWriteError

MAX_FILENAME_BYTES: Final = 240
PRIVATE_FILE_MODE: Final = 0o600
PRIVATE_UMASK: Final = 0o077

_TEMP_PREFIX: Final = ".priveopdf-"
_TEMP_SUFFIX: Final = ".tmp"
_TEMP_NAME_ATTEMPTS: Final = 32
_WINDOWS_INVALID_CHARACTERS: Final = frozenset('<>:"/\\|?*')
_WINDOWS_RESERVED_NAMES: Final = frozenset(
    {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{index}" for index in range(1, 10)),
        *(f"LPT{index}" for index in range(1, 10)),
    }
)
_UMASK_LOCK = threading.Lock()

type BinaryWriter = Callable[[BinaryIO], object]


@dataclass(slots=True)
class PublishedOutput:
    path: Path
    device: int
    inode: int
    _file_descriptor: int = field(repr=False)

    def matches_current_entry(self) -> bool:
        try:
            opened_stat = os.fstat(self._file_descriptor)
            path_stat = self.path.stat(follow_symlinks=False)
        except OSError:
            return False
        opened_identity = (opened_stat.st_dev, opened_stat.st_ino)
        path_identity = (path_stat.st_dev, path_stat.st_ino)
        return opened_identity == path_identity == (self.device, self.inode)

    def close(self) -> None:
        if self._file_descriptor < 0:
            return
        with suppress(OSError):
            os.close(self._file_descriptor)
        self._file_descriptor = -1


def normalize_filename_component(name: str, *, max_bytes: int = MAX_FILENAME_BYTES) -> str:
    """Return a portable NFC filename component or reject it without echoing it."""
    if not isinstance(name, str) or not isinstance(max_bytes, int) or max_bytes < 1:
        raise DangerousOutputError()

    normalized = unicodedata.normalize("NFC", name)
    if not normalized or normalized in {".", ".."}:
        raise DangerousOutputError()
    if normalized != normalized.strip() or normalized.endswith((".", " ")):
        raise DangerousOutputError()
    if any(character in _WINDOWS_INVALID_CHARACTERS for character in normalized):
        raise DangerousOutputError()
    if any(unicodedata.category(character).startswith("C") for character in normalized):
        raise DangerousOutputError()

    reserved_base = normalized.split(".", maxsplit=1)[0].rstrip(" .").upper()
    if reserved_base in _WINDOWS_RESERVED_NAMES:
        raise DangerousOutputError()

    try:
        encoded_name = normalized.encode("utf-8", errors="strict")
    except UnicodeError:
        raise DangerousOutputError() from None
    if len(encoded_name) > max_bytes:
        raise DangerousOutputError()
    return normalized


def build_confined_destination(
    output_dir: Path,
    filename: str,
    *,
    required_suffix: str | None = None,
) -> Path:
    """Build a normalized destination confined to an existing directory."""
    safe_name = normalize_filename_component(filename)
    if required_suffix is not None:
        suffix = required_suffix.casefold()
        if not suffix.startswith("."):
            raise ValueError("required_suffix must start with a dot")
        if not safe_name.casefold().endswith(suffix) or len(safe_name) == len(required_suffix):
            raise OutputWriteError()

    directory = _resolve_existing_directory(Path(output_dir))
    destination = directory / safe_name
    try:
        resolved_destination = destination.resolve(strict=False)
    except OSError:
        raise OutputWriteError() from None
    if not resolved_destination.is_relative_to(directory):
        raise DangerousOutputError()
    return destination


def prepare_new_output_path(
    destination: Path,
    input_paths: Sequence[Path] = (),
    *,
    allowed_dir: Path | None = None,
    required_suffix: str | None = None,
) -> Path:
    """Validate and canonicalize a new output path without claiming race safety."""
    requested = Path(destination)
    directory = Path(allowed_dir) if allowed_dir is not None else requested.parent
    confined = build_confined_destination(
        directory,
        requested.name,
        required_suffix=required_suffix,
    )

    try:
        requested_parent = requested.parent.resolve(strict=True)
    except OSError:
        raise OutputWriteError() from None
    if requested_parent != confined.parent:
        raise DangerousOutputError()
    requested_entry = confined.parent / requested.name

    try:
        resolved_destination = confined.resolve(strict=False)
        resolved_inputs = {Path(path).resolve(strict=True) for path in input_paths}
    except OSError:
        raise DangerousOutputError() from None
    if resolved_destination in resolved_inputs:
        raise DangerousOutputError()
    if _entry_exists(confined) or (requested_entry != confined and _entry_exists(requested_entry)):
        raise DangerousOutputError()
    return confined


def atomic_write_no_replace(
    destination: Path,
    writer: BinaryWriter,
    input_paths: Sequence[Path] = (),
    *,
    allowed_dir: Path | None = None,
    required_suffix: str | None = None,
) -> Path:
    """Publish one private file atomically and return its confined path."""
    published = atomic_write_no_replace_tracked(
        destination,
        writer,
        input_paths,
        allowed_dir=allowed_dir,
        required_suffix=required_suffix,
    )
    try:
        return published.path
    finally:
        published.close()


def atomic_write_no_replace_tracked(
    destination: Path,
    writer: BinaryWriter,
    input_paths: Sequence[Path] = (),
    *,
    allowed_dir: Path | None = None,
    required_suffix: str | None = None,
) -> PublishedOutput:
    """Write privately and publish atomically without replacing any directory entry.

    The temporary file and destination are addressed through one verified directory
    descriptor. Publication uses ``link(2)`` with an absent destination requirement;
    unlike ``rename`` or ``shutil.move``, this cannot silently replace a concurrent file.
    """
    target = prepare_new_output_path(
        destination,
        input_paths,
        allowed_dir=allowed_dir,
        required_suffix=required_suffix,
    )
    directory = target.parent
    if os.name != "posix":
        return _atomic_write_no_replace_tracked_portable(target, writer)

    directory_stat = _directory_identity(directory)

    directory_fd = -1
    temporary_fd = -1
    temporary_name: str | None = None
    published_identity: tuple[int, int] | None = None
    tracking_fd = -1
    completed = False
    try:
        directory_fd = _open_verified_directory(directory, directory_stat)
        _require_directory_path_identity(directory, directory_stat)
        _require_absent_at(directory_fd, target.name)

        temporary_name, temporary_fd = _create_private_temporary(directory_fd)
        temporary_stream = os.fdopen(temporary_fd, "w+b", closefd=False)
        try:
            writer(temporary_stream)
            temporary_stream.flush()
            os.fchmod(temporary_fd, PRIVATE_FILE_MODE)
            os.fsync(temporary_fd)
        finally:
            temporary_stream.close()

        temporary_stat = os.fstat(temporary_fd)
        if not stat.S_ISREG(temporary_stat.st_mode):
            raise OutputWriteError()

        _require_directory_path_identity(directory, directory_stat)
        try:
            os.link(
                temporary_name,
                target.name,
                src_dir_fd=directory_fd,
                dst_dir_fd=directory_fd,
                follow_symlinks=False,
            )
        except FileExistsError:
            raise DangerousOutputError() from None

        published_identity = (temporary_stat.st_dev, temporary_stat.st_ino)
        output_stat = os.stat(target.name, dir_fd=directory_fd, follow_symlinks=False)
        if (output_stat.st_dev, output_stat.st_ino) != published_identity:
            raise OutputWriteError()
        if stat.S_IMODE(output_stat.st_mode) != PRIVATE_FILE_MODE:
            raise OutputWriteError()

        os.fsync(directory_fd)
        os.unlink(temporary_name, dir_fd=directory_fd)
        temporary_name = None
        os.fsync(directory_fd)
        _require_directory_path_identity(directory, directory_stat)
        final_stat = os.stat(target.name, dir_fd=directory_fd, follow_symlinks=False)
        if (final_stat.st_dev, final_stat.st_ino) != published_identity:
            raise DangerousOutputError()
        tracking_fd = os.dup(temporary_fd)
        os.set_inheritable(tracking_fd, False)
        published = PublishedOutput(
            path=target,
            device=published_identity[0],
            inode=published_identity[1],
            _file_descriptor=tracking_fd,
        )
        completed = True
        return published
    except (DangerousOutputError, OutputWriteError):
        raise
    except OSError:
        raise OutputWriteError() from None
    finally:
        if not completed and tracking_fd >= 0:
            with suppress(OSError):
                os.close(tracking_fd)
        if not completed and published_identity is not None and directory_fd >= 0:
            _unlink_if_same(directory_fd, target.name, published_identity)
        if temporary_name is not None and directory_fd >= 0:
            _unlink_if_present(directory_fd, temporary_name)
        if temporary_fd >= 0:
            with suppress(OSError):
                os.close(temporary_fd)
        if directory_fd >= 0:
            with suppress(OSError):
                os.close(directory_fd)


def _atomic_write_no_replace_tracked_portable(
    target: Path,
    writer: BinaryWriter,
) -> PublishedOutput:
    """Portable no-replace publication for platforms without directory descriptors.

    The destination is claimed with a hard link, which is atomic and refuses an
    existing target. The POSIX path above remains stronger because it also addresses
    every operation through a verified directory descriptor.
    """
    directory = target.parent
    directory_identity = _directory_identity(directory)
    temporary_path: Path | None = None
    temporary_fd = -1
    tracking_fd = -1
    published_identity: tuple[int, int] | None = None
    completed = False
    try:
        _require_directory_path_identity(directory, directory_identity)
        if _entry_exists(target):
            raise DangerousOutputError()

        temporary_path, temporary_fd = _create_private_temporary_path(directory)
        temporary_stream = os.fdopen(temporary_fd, "w+b", closefd=False)
        try:
            writer(temporary_stream)
            temporary_stream.flush()
            if hasattr(os, "fchmod"):
                os.fchmod(temporary_fd, PRIVATE_FILE_MODE)
            os.fsync(temporary_fd)
        finally:
            temporary_stream.close()

        temporary_stat = temporary_path.stat(follow_symlinks=False)
        if not stat.S_ISREG(temporary_stat.st_mode):
            raise OutputWriteError()
        # Windows denies unlinking a file while the CRT descriptor remains open.
        os.close(temporary_fd)
        temporary_fd = -1

        _require_directory_path_identity(directory, directory_identity)
        try:
            os.link(temporary_path, target)
        except FileExistsError:
            raise DangerousOutputError() from None

        published_identity = (temporary_stat.st_dev, temporary_stat.st_ino)
        output_stat = target.stat(follow_symlinks=False)
        if (output_stat.st_dev, output_stat.st_ino) != published_identity:
            raise OutputWriteError()
        with suppress(OSError):
            target.chmod(PRIVATE_FILE_MODE)

        temporary_path.unlink()
        temporary_path = None
        _require_directory_path_identity(directory, directory_identity)
        final_stat = target.stat(follow_symlinks=False)
        if (final_stat.st_dev, final_stat.st_ino) != published_identity:
            raise DangerousOutputError()

        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
        tracking_fd = os.open(target, flags)
        os.set_inheritable(tracking_fd, False)
        tracked_stat = os.fstat(tracking_fd)
        if (tracked_stat.st_dev, tracked_stat.st_ino) != published_identity:
            raise DangerousOutputError()

        published = PublishedOutput(
            path=target,
            device=published_identity[0],
            inode=published_identity[1],
            _file_descriptor=tracking_fd,
        )
        completed = True
        return published
    except (DangerousOutputError, OutputWriteError):
        raise
    except OSError:
        raise OutputWriteError() from None
    finally:
        if not completed and tracking_fd >= 0:
            with suppress(OSError):
                os.close(tracking_fd)
        if not completed and published_identity is not None:
            _unlink_path_if_same(target, published_identity)
        if temporary_path is not None:
            with suppress(OSError):
                temporary_path.unlink()
        if temporary_fd >= 0:
            with suppress(OSError):
                os.close(temporary_fd)


def _create_private_temporary_path(directory: Path) -> tuple[Path, int]:
    flags = os.O_RDWR | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    for _attempt in range(_TEMP_NAME_ATTEMPTS):
        path = directory / f"{_TEMP_PREFIX}{secrets.token_hex(16)}{_TEMP_SUFFIX}"
        try:
            with _restricted_umask():
                file_descriptor = os.open(path, flags, PRIVATE_FILE_MODE)
        except FileExistsError:
            continue
        with suppress(OSError):
            path.chmod(PRIVATE_FILE_MODE)
        return path, file_descriptor
    raise OutputWriteError()


def _unlink_path_if_same(path: Path, expected: tuple[int, int]) -> None:
    try:
        current = path.stat(follow_symlinks=False)
        if (current.st_dev, current.st_ino) == expected:
            path.unlink()
    except OSError:
        return


def _resolve_existing_directory(output_dir: Path) -> Path:
    try:
        directory = output_dir.resolve(strict=True)
        directory_stat = directory.stat(follow_symlinks=False)
    except OSError:
        raise OutputWriteError() from None
    if not stat.S_ISDIR(directory_stat.st_mode):
        raise OutputWriteError()
    return directory


def _entry_exists(path: Path) -> bool:
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    except OSError:
        raise OutputWriteError() from None
    return True


def _directory_identity(directory: Path) -> tuple[int, int]:
    try:
        directory_stat = directory.stat(follow_symlinks=False)
    except OSError:
        raise OutputWriteError() from None
    if not stat.S_ISDIR(directory_stat.st_mode):
        raise OutputWriteError()
    return (directory_stat.st_dev, directory_stat.st_ino)


def _open_verified_directory(directory: Path, expected: tuple[int, int]) -> int:
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        directory_fd = os.open(directory, flags)
    except OSError:
        raise OutputWriteError() from None
    try:
        opened_stat = os.fstat(directory_fd)
    except OSError:
        with suppress(OSError):
            os.close(directory_fd)
        raise OutputWriteError() from None
    opened_identity = (opened_stat.st_dev, opened_stat.st_ino)
    if not stat.S_ISDIR(opened_stat.st_mode) or opened_identity != expected:
        os.close(directory_fd)
        raise DangerousOutputError()
    return directory_fd


def _require_directory_path_identity(directory: Path, expected: tuple[int, int]) -> None:
    if _directory_identity(directory) != expected:
        raise DangerousOutputError()


def _require_absent_at(directory_fd: int, filename: str) -> None:
    try:
        os.stat(filename, dir_fd=directory_fd, follow_symlinks=False)
    except FileNotFoundError:
        return
    except OSError:
        raise OutputWriteError() from None
    raise DangerousOutputError()


def _create_private_temporary(directory_fd: int) -> tuple[str, int]:
    flags = os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    for _attempt in range(_TEMP_NAME_ATTEMPTS):
        name = f"{_TEMP_PREFIX}{secrets.token_hex(16)}{_TEMP_SUFFIX}"
        try:
            with _restricted_umask():
                temporary_fd = os.open(
                    name,
                    flags,
                    PRIVATE_FILE_MODE,
                    dir_fd=directory_fd,
                )
        except FileExistsError:
            continue
        try:
            os.fchmod(temporary_fd, PRIVATE_FILE_MODE)
        except OSError:
            with suppress(OSError):
                os.close(temporary_fd)
            _unlink_if_present(directory_fd, name)
            raise OutputWriteError() from None
        return name, temporary_fd
    raise OutputWriteError()


class _restricted_umask:
    _previous: int

    def __enter__(self) -> None:
        _UMASK_LOCK.acquire()
        try:
            self._previous = os.umask(PRIVATE_UMASK)
        except BaseException:
            _UMASK_LOCK.release()
            raise

    def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
        os.umask(self._previous)
        _UMASK_LOCK.release()


def _unlink_if_same(directory_fd: int, filename: str, expected: tuple[int, int]) -> None:
    try:
        current = os.stat(filename, dir_fd=directory_fd, follow_symlinks=False)
        if (current.st_dev, current.st_ino) != expected:
            return
        os.unlink(filename, dir_fd=directory_fd)
    except OSError:
        return


def _unlink_if_present(directory_fd: int, filename: str) -> None:
    try:
        os.unlink(filename, dir_fd=directory_fd)
    except OSError:
        return
