"""Linux namespace verification without importing Qt or a document engine."""

from __future__ import annotations

import os
import sys
from pathlib import Path

_PROC_NET_DEV = Path("/proc/net/dev")


def document_namespace_verified(network_devices_path: Path | None = None) -> bool:
    if os.environ.get("PRIVEOPDF_DOCUMENT_SANDBOX") != "1":
        return False
    if not sys.platform.startswith("linux"):
        return False
    try:
        lines = (network_devices_path or _PROC_NET_DEV).read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return False
    interfaces: set[str] = set()
    for line in lines[2:]:
        if not line.strip():
            continue
        name, separator, _statistics = line.partition(":")
        interface = name.strip()
        if not separator or not interface:
            return False
        interfaces.add(interface)
    return bool(interfaces) and interfaces <= {"lo"}
