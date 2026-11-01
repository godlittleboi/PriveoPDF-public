"""Linux render budget: verified systemd scope and mandatory worker confinement.

The scope preserves the caller's namespaces (unlike a transient service). The
worker sees cgroups read-only and cannot reach the user's systemd bus. No PDF
content or document pathname is passed to the service manager.
"""

from __future__ import annotations

import os
import re
import shutil
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path, PurePosixPath

VIRTUAL_RENDER_BYTES = 64 * 1024**3


def request_render_budget(memory_bytes: int) -> None:
    """Register this bootstrap before confinement; never send document data."""
    from priveopdf.workers.render_memory_broker import BROKER_ENV

    endpoint = os.environ.pop(BROKER_ENV, "")
    if not endpoint:
        raise OSError("render memory broker unavailable")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as peer:
        peer.settimeout(5)
        peer.connect(endpoint)
        if peer.recv(1) != b"1":
            raise OSError("render scope refused")
    # StartTransientUnit enqueues a job. Verify the kernel state after the
    # manager reply, with a bounded wait for actual cgroup migration.
    deadline = time.monotonic() + 3
    while True:
        try:
            verify_render_budget(memory_bytes)
            return
        except OSError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.02)


def scope_command(command: tuple[str, ...], memory_bytes: int) -> tuple[str, ...]:
    executable = shutil.which("systemd-run")
    if not sys.platform.startswith("linux") or executable is None:
        raise OSError("render memory isolation unavailable")
    _verify_scope_support(executable)
    return (
        executable,
        "--user",
        "--scope",
        "--quiet",
        "--collect",
        "--expand-environment=no",
        "--no-ask-password",
        "--unit=priveopdf-render-" + uuid.uuid4().hex + ".scope",
        "--description=PriveoPDF local render",
        "--property=MemoryMax=" + str(memory_bytes),
        "--property=MemorySwapMax=0",
        # scope_add_extras derives memory.oom.group from this policy.
        "--property=OOMPolicy=kill",
        "--property=TasksMax=64",
        "--",
        *command,
    )


def _verify_scope_support(executable: str) -> None:
    # Mint's document launcher has its own PID namespace. Require systemd's
    # PIDFD scope support on both ends; classic numeric PIDs are inappropriate.
    manager = shutil.which("systemctl")
    if manager is None or not hasattr(os, "pidfd_open"):
        raise OSError("PIDFD scope support unavailable")
    descriptor = os.pidfd_open(os.getpid())
    os.close(descriptor)
    runtime = f"/run/user/{os.getuid()}"
    environment = {
        "PATH": "/usr/bin:/bin",
        "LANG": "C",
        "XDG_RUNTIME_DIR": runtime,
        "DBUS_SESSION_BUS_ADDRESS": "unix:path=" + runtime + "/bus",
    }
    for command in (
        (executable, "--version"),
        (manager, "--user", "show", "--property=Version", "--value"),
    ):
        try:
            result = subprocess.run(  # noqa: S603 - fixed system executables and arguments
                command, env=environment, capture_output=True, timeout=3, check=True
            )
        except (subprocess.SubprocessError, OSError):
            raise OSError("systemd user manager unavailable") from None
        version = re.search(rb"(?:systemd )?(\d{3})", result.stdout[:256])
        if not version or int(version[1]) < 255:
            raise OSError("systemd 255 or newer is required for PIDFD scopes")


def verify_render_budget(memory_bytes: int) -> None:
    """Verify kernel enforcement before relaxing RLIMIT_AS, before native imports."""
    root = Path("/sys/fs/cgroup")
    if not os.statvfs(root).f_flag & os.ST_RDONLY:
        raise OSError("cgroup mount must be read-only")
    rows = Path("/proc/self/cgroup").read_text().splitlines()
    unified = [row[3:] for row in rows if row.startswith("0::/")]
    if len(unified) != 1:
        raise OSError("unified cgroup unavailable")
    relative = PurePosixPath(unified[0])
    if ".." in relative.parts or not relative.name.startswith("priveopdf-render-"):
        raise OSError("unexpected render scope")
    group = root.joinpath(*relative.parts[1:])
    limit = (group / "memory.max").read_text().strip()
    if not limit.isdecimal() or not 0 < int(limit) <= memory_bytes:
        raise OSError("memory budget not enforced")
    if (group / "memory.swap.max").read_text().strip() != "0":
        raise OSError("swap budget not enforced")
    if (group / "memory.oom.group").read_text().strip() != "1":
        raise OSError("group OOM policy not enforced")
    tasks = (group / "pids.max").read_text().strip()
    if not tasks.isdecimal() or not 0 < int(tasks) <= 64:
        raise OSError("task budget not enforced")
