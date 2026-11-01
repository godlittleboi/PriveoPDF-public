"""Per-worker restrictions inside the launcher's AppArmor-compatible namespace.

Apply before importing native PDF/Qt code or creating threads. Landlock ABI 3
is mandatory (including truncate); seccomp closes socket and process IPC paths.
No fallback on a partial policy. Kernel interfaces: userspace-api/landlock.html.
"""

from __future__ import annotations

import ctypes
import errno
import json
import os
import platform
import stat
import sys
from pathlib import Path

PROFILE_ENV = "PRIVEOPDF_WORKER_PROFILE"
_READ = (1 << 2) | (1 << 3)
_EXEC = 1 << 0
_WRITE = (1 << 1) | (1 << 4) | (1 << 5) | (1 << 7) | (1 << 8) | (1 << 13) | (1 << 14)
_HANDLED = (1 << 15) - 1


class _PathRule(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("allowed_access", ctypes.c_uint64), ("parent_fd", ctypes.c_int)]


class _Comparison(ctypes.Structure):
    _fields_ = [
        ("arg", ctypes.c_uint),
        ("op", ctypes.c_uint),
        ("datum_a", ctypes.c_uint64),
        ("datum_b", ctypes.c_uint64),
    ]


def _libc():
    libc = ctypes.CDLL(None, use_errno=True)
    libc.syscall.restype = ctypes.c_long
    return libc


def landlock_abi() -> int:
    if platform.machine() not in {"x86_64", "aarch64"}:
        raise OSError(errno.ENOSYS, "unsupported confinement architecture")
    result = _libc().syscall(444, ctypes.c_void_p(), 0, 1)
    if result < 3:
        raise OSError(errno.ENOSYS, "Landlock ABI 3 required")
    return result


def _check(result: int) -> None:
    if result < 0:
        raise OSError(ctypes.get_errno() or errno.EPERM, "worker confinement unavailable")


def _restrict_files(read_paths: tuple[Path, ...], private: Path) -> None:
    landlock_abi()
    libc = _libc()
    handled = ctypes.c_uint64(_HANDLED)
    ruleset = libc.syscall(444, ctypes.byref(handled), ctypes.sizeof(handled), 0)
    _check(ruleset)
    try:
        rules = [(p, _READ | _EXEC) for p in _runtime_read_roots()]
        rules += [(p, 1 << 2) for p in read_paths]
        rules += [(private, _READ | _WRITE)]
        # Font configuration needed by Qt; never HOME or /run.
        rules += [(Path(p), _READ) for p in ("/etc/fonts",) if Path(p).exists()]
        rules += [
            (Path(p), (1 << 1) | (1 << 2))
            for p in ("/dev/null", "/dev/zero", "/dev/urandom", "/dev/random")
        ]
        for path, rights in rules:
            fd = os.open(path, os.O_PATH | os.O_CLOEXEC)
            try:
                if not stat.S_ISDIR(os.fstat(fd).st_mode):
                    rights &= _EXEC | (1 << 1) | (1 << 2) | (1 << 14)
                rule = _PathRule(rights, fd)
                _check(libc.syscall(445, ruleset, 1, ctypes.byref(rule), 0))
            finally:
                os.close(fd)
        _check(libc.prctl(38, 1, 0, 0, 0))  # PR_SET_NO_NEW_PRIVS
        _check(libc.syscall(446, ruleset, 0))
    finally:
        os.close(ruleset)


def _restrict_ipc() -> None:
    # libseccomp resolves native syscall numbers and rejects foreign ABIs.
    system_library = {
        "x86_64": "/lib/x86_64-linux-gnu/libseccomp.so.2",
        "aarch64": "/lib/aarch64-linux-gnu/libseccomp.so.2",
    }.get(platform.machine())
    if system_library is None:
        raise OSError(errno.ENOSYS, "unsupported seccomp architecture")
    # Explicit system dependency (Debian libseccomp2), not a bundled private copy.
    lib = ctypes.CDLL(system_library, use_errno=True)
    lib.seccomp_init.argtypes = [ctypes.c_uint32]
    lib.seccomp_init.restype = ctypes.c_void_p
    lib.seccomp_release.argtypes = [ctypes.c_void_p]
    lib.seccomp_load.argtypes = [ctypes.c_void_p]
    lib.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    lib.seccomp_rule_add_array.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_int,
        ctypes.c_uint,
        ctypes.POINTER(_Comparison),
    ]
    context = lib.seccomp_init(0x7FFF0000)  # SCMP_ACT_ALLOW
    if not context:
        raise OSError(errno.ENOMEM, "seccomp unavailable")
    try:
        # File metadata syscalls are not mediated by Landlock ABI 3. Block them
        # too; output files are created with mode 0600 from the outset.
        denied = [
            "fork",
            "vfork",
            "kcmp",
            "process_madvise",
            "sched_setaffinity",
            "sched_setscheduler",
            "sched_setparam",
            "setpriority",
            "ioprio_set",
            "socket",
            "socketpair",
            "connect",
            "bind",
            "listen",
            "accept",
            "accept4",
            "ptrace",
            "process_vm_readv",
            "process_vm_writev",
            "pidfd_getfd",
            "pidfd_open",
            "pidfd_send_signal",
            "io_uring_setup",
            "io_uring_register",
            "io_uring_enter",
            "shmget",
            "shmat",
            "shmdt",
            "shmctl",
            "semget",
            "semop",
            "semtimedop",
            "semctl",
            "msgget",
            "msgsnd",
            "msgrcv",
            "msgctl",
            "mount",
            "umount2",
            "pivot_root",
            "move_mount",
            "open_tree",
            "fsopen",
            "fsconfig",
            "fsmount",
            "mount_setattr",
            "unshare",
            "setns",
            "bpf",
            "perf_event_open",
            "userfaultfd",
            "chmod",
            "fchmod",
            "fchmodat",
            "fchmodat2",
            "chown",
            "fchown",
            "lchown",
            "fchownat",
            "utime",
            "utimes",
            "futimesat",
            "utimensat",
            "getxattr",
            "lgetxattr",
            "fgetxattr",
            "listxattr",
            "llistxattr",
            "flistxattr",
            "setxattr",
            "lsetxattr",
            "fsetxattr",
            "removexattr",
            "lremovexattr",
            "fremovexattr",
            "tkill",
            "rt_sigqueueinfo",
            "rt_tgsigqueueinfo",
        ]
        for name in denied:
            number = lib.seccomp_syscall_resolve_name(name.encode())
            if number == -1:  # nonexistent on this architecture/libseccomp version
                continue
            result = lib.seccomp_rule_add_array(context, 0x50000 | errno.EPERM, number, 0, None)
            if result != 0:
                raise OSError(-result, "seccomp rule unavailable")
        # Qt can signal its own threads, never another process (or a process group).
        for name in ("kill", "tgkill"):
            number = lib.seccomp_syscall_resolve_name(name.encode())
            comparison = _Comparison(0, 1, os.getpid(), 0)  # SCMP_CMP_NE
            result = lib.seccomp_rule_add_array(
                context, 0x50000 | errno.EPERM, number, 1, ctypes.byref(comparison)
            )
            if result != 0:
                raise OSError(-result, "seccomp signal rule unavailable")
        # Current PDF engines need threads, not subprocesses. Forbid detached
        # descendants which could outlive the job and race output publication.
        comparison = _Comparison(0, 7, 0x10000, 0)  # MASKED_EQ, no CLONE_THREAD
        clone = lib.seccomp_syscall_resolve_name(b"clone")
        result = lib.seccomp_rule_add_array(
            context, 0x50000 | errno.EPERM, clone, 1, ctypes.byref(comparison)
        )
        if result != 0:
            raise OSError(-result, "seccomp clone rule unavailable")
        clone3 = lib.seccomp_syscall_resolve_name(b"clone3")
        # glibc retries clone when clone3 is unavailable; its pointer argument
        # cannot be safely inspected by a classic seccomp filter.
        result = lib.seccomp_rule_add_array(context, 0x50000 | errno.ENOSYS, clone3, 0, None)
        if result != 0:
            raise OSError(-result, "seccomp clone3 rule unavailable")
        comparison = _Comparison(0, 1, 0, 0)  # only prlimit64(pid=0), this process
        result = lib.seccomp_rule_add_array(
            context,
            0x50000 | errno.EPERM,
            lib.seccomp_syscall_resolve_name(b"prlimit64"),
            1,
            ctypes.byref(comparison),
        )
        if result != 0:
            raise OSError(-result, "seccomp resource rule unavailable")
        result = lib.seccomp_load(context)
        if result != 0:
            raise OSError(-result, "seccomp activation failed")
    finally:
        lib.seccomp_release(context)


def confine(read_paths: tuple[Path, ...], private: Path) -> None:
    """Irreversibly restrict this fresh single-threaded worker and descendants."""
    _restrict_files(read_paths, private)
    _restrict_ipc()


def apply_worker_profile() -> None:
    profile = os.environ.pop(PROFILE_ENV, None)
    if profile is None:
        return  # standalone workers use a complete Bubblewrap profile
    from priveopdf.workers.network_isolation import document_namespace_verified

    if not document_namespace_verified():
        raise OSError(errno.EPERM, "document namespace required")
    if len(profile) > 100_000:
        raise ValueError("oversized worker profile")
    value = json.loads(profile)
    if not isinstance(value, dict) or set(value) != {"read", "private"}:
        raise ValueError("invalid worker profile")
    paths = value["read"]
    if not isinstance(paths, list) or not paths or len(paths) > 1024:
        raise ValueError("invalid input list")
    if any(not isinstance(p, str) or not Path(p).is_absolute() for p in [*paths, value["private"]]):
        raise ValueError("invalid worker path")
    confine(tuple(Path(p) for p in paths), Path(value["private"]))


def _runtime_read_roots() -> tuple[Path, ...]:
    candidates = {
        Path(__file__).resolve().parents[2],
        Path(sys.base_prefix).resolve(),
        Path(sys.prefix).resolve(),
        Path(sys.executable).resolve().parent,
    }
    for path_text in ("/usr", "/lib", "/lib64", "/bin"):
        path = Path(path_text)
        if path.exists():
            candidates.add(path.absolute())
    return _remove_nested_paths(candidates)


def _remove_nested_paths(paths: set[Path]) -> tuple[Path, ...]:
    ordered = sorted(paths, key=lambda path: (len(path.parts), str(path)))
    result: list[Path] = []
    for path in ordered:
        if any(path == parent or parent in path.parents for parent in result):
            continue
        result.append(path)
    return tuple(result)
