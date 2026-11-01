"""Bounded asynchronous client: native PDF code exists only in render_worker."""

from __future__ import annotations

import json
import math
import sys
import tempfile
import threading
from contextlib import suppress
from enum import IntEnum
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QSize, QSizeF, QThreadPool, Signal
from PySide6.QtGui import QImage

from priveopdf.domain.errors import InputPathError
from priveopdf.workers.local_confinement import PROFILE_ENV
from priveopdf.workers.process_supervisor import (
    ProcessSupervisor,
    ProcessSupervisorError,
    _bubblewrap_command,
    _local_profile,
    _minimal_environment,
    _network_isolation_unavailable,
    _SandboxAccess,
    _unsandboxed_development_allowed,
)

MAX_PIXELS = 4_000_000
MAX_RESPONSE = 18_000_000
MAX_TEXT_RECTS = 5_000
MAX_SEARCH_MATCHES = 1_000
_POOL = None


def _pool():
    global _POOL
    if _POOL is None:
        _POOL = QThreadPool()
        _POOL.setMaxThreadCount(2)
    return _POOL


def decode_frame(frame: bytes, action: str):
    if len(frame) < 4 or len(frame) > MAX_RESPONSE:
        raise ValueError("invalid frame")
    length = int.from_bytes(frame[:4], "big")
    if not 0 < length <= 2_000_000 or len(frame) < length + 4:
        raise ValueError("invalid header")
    value = json.loads(frame[4 : 4 + length])
    if not isinstance(value, dict):
        raise ValueError("invalid header")
    pixels = frame[4 + length :]
    if "error" in value:
        if pixels or value["error"] not in ("password", "load"):
            raise ValueError("invalid error")
        return value
    if action == "metadata":
        pages = value.get("pages")
        if pixels or not isinstance(pages, list) or not 0 < len(pages) <= 10_000:
            raise ValueError("invalid pages")
        for size in pages:
            if (
                not isinstance(size, list)
                or len(size) != 2
                or any(
                    type(v) not in (int, float) or not math.isfinite(v) or not 0.01 <= v <= 100_000
                    for v in size
                )
            ):
                raise ValueError("invalid geometry")
        return value
    if action == "selection":
        text = value.get("text")
        if pixels or not isinstance(text, str) or len(text) > 100_000:
            raise ValueError("invalid text")
        text.encode("utf-8", errors="strict")
        bounds = value.get("bounds", [])
        if not isinstance(bounds, list) or len(bounds) > 4096:
            raise ValueError("invalid selection geometry")
        for rect in bounds:
            if (
                not isinstance(rect, list)
                or len(rect) != 4
                or any(
                    type(v) not in (int, float) or not math.isfinite(v) or abs(v) > 100_000
                    for v in rect
                )
                or rect[2] < 0
                or rect[3] < 0
            ):
                raise ValueError("invalid selection geometry")
        return value
    if action == "search":
        matches = value.get("matches")
        if pixels or not isinstance(matches, list) or len(matches) > MAX_SEARCH_MATCHES:
            raise ValueError("invalid search results")
        for match in matches:
            if (
                not isinstance(match, list)
                or len(match) != 2
                or type(match[0]) is not int
                or not 0 <= match[0] < 10_000
                or not isinstance(match[1], list)
                or not 0 < len(match[1]) <= 16
                or any(not _valid_box(box) for box in match[1])
            ):
                raise ValueError("invalid search results")
        return value
    if action == "text_lines":
        rects = value.get("rects")
        if pixels or not isinstance(rects, list) or len(rects) > MAX_TEXT_RECTS:
            raise ValueError("invalid text geometry")
        if any(not _valid_box(rect) for rect in rects):
            raise ValueError("invalid text geometry")
        return value
    size = value.get("size")
    if (
        not isinstance(size, list)
        or len(size) != 2
        or any(type(v) is not int or not 0 < v <= 8192 for v in size)
        or size[0] * size[1] > MAX_PIXELS
        or len(pixels) != size[0] * size[1] * 4
    ):
        raise ValueError("invalid pixels")
    return QImage(pixels, size[0], size[1], size[0] * 4, QImage.Format.Format_RGBA8888).copy()


def _valid_box(rect: object) -> bool:
    return (
        isinstance(rect, list)
        and len(rect) == 4
        and all(type(v) in (int, float) and math.isfinite(v) and abs(v) <= 100_000 for v in rect)
        and rect[2] > 0
        and rect[3] > 0
    )


class RenderSupervisor(ProcessSupervisor):
    def __init__(self):
        super().__init__(timeout_seconds=35, max_response_bytes=MAX_RESPONSE)

    def request(self, path: Path, action: str, **params):
        if not sys.platform.startswith("linux") and not _unsandboxed_development_allowed():
            raise _network_isolation_unavailable()
        # Landlock opens the document before confinement: a file gone from the
        # disk made the worker exit 78, shown as missing isolation (#315).
        if not Path(path).is_file():
            raise ProcessSupervisorError("input_path_error", InputPathError.user_message)
        with tempfile.TemporaryDirectory(prefix="priveopdf-render-") as temp:
            private = Path(temp)
            private.chmod(0o700)
            local_confinement = self._local_confinement_enabled()
            isolated = self._bubblewrap_enabled()
            with self._state_lock:
                self._last_isolation_mode = (
                    "landlock" if local_confinement else ("bubblewrap" if isolated else "process")
                )
            environment = _minimal_environment(Path("/tmp") if isolated else private)  # noqa: S108 - sandbox mount
            environment["QT_QPA_PLATFORM"] = "offscreen"
            if local_confinement:
                environment[PROFILE_ENV] = _local_profile(
                    _SandboxAccess((path.absolute(),), ()), private
                )
            if isolated or local_confinement:
                environment["PRIVEOPDF_DOCUMENT_SANDBOX"] = "1"
            command = (
                (sys.executable, "--render-worker")
                if getattr(sys, "frozen", False)
                else (sys.executable, "-P", "-m", "priveopdf.workers.render_worker")
            )
            if isolated:
                command = _bubblewrap_command(
                    command,
                    environment=environment,
                    access=_SandboxAccess((path.absolute(),), ()),
                    private_temp=private,
                )
            frame = json.dumps({"path": str(path.absolute()), "action": action, **params}).encode()
            done = threading.Event()
            exhausted = threading.Event()

            def watch_memory():
                while not done.wait(0.05):
                    pid = self.active_pid()
                    if pid is None:
                        continue
                    try:
                        total = _resident_tree_bytes(pid)
                        if total > 768 * 1024**2:
                            exhausted.set()
                            self.cancel()
                    except (OSError, ValueError):
                        if self.active_pid() is None:
                            continue
                        # Some test containers expose a host procfs with different
                        # PIDs. Only explicit nonqualifying development may proceed.
                        if (
                            not isolated
                            and not local_confinement
                            and _unsandboxed_development_allowed()
                        ):
                            continue
                        exhausted.set()
                        self.cancel()

            watcher = threading.Thread(target=watch_memory, daemon=True)
            if sys.platform.startswith("linux"):
                watcher.start()
            try:
                output, code = self._run_process(
                    command, frame, environment=environment, working_dir=private
                )
                if code == 78:
                    raise _network_isolation_unavailable()
                if code or exhausted.is_set():
                    raise ValueError("render worker failed")
                return decode_frame(output, action)
            finally:
                done.set()


class _TaskSignals(QObject):
    completed = Signal(int, int, str, object)


class _Task(QRunnable):
    def __init__(self, generation, request_id, path, action, params):
        super().__init__()
        self.signals = _TaskSignals()
        self.generation, self.request_id, self.path, self.action, self.params = (
            generation,
            request_id,
            path,
            action,
            params,
        )
        self.supervisor = RenderSupervisor()
        self.cancelled = False

    def run(self):
        if self.cancelled:
            return
        try:
            result = self.supervisor.request(self.path, self.action, **self.params)
        except ProcessSupervisorError as exc:
            result = {
                "error": "isolation" if exc.code == "network_isolation_unavailable" else "load"
            }
        except Exception:
            result = {"error": "load"}
        if not self.cancelled:
            # Qt teardown can delete signal objects before thread completion.
            with suppress(RuntimeError):
                self.signals.completed.emit(self.generation, self.request_id, self.action, result)

    def cancel(self):
        self.cancelled = True
        self.supervisor.request_cancel()


class RemotePdfDocument(QObject):
    class Status(IntEnum):
        Null = 0
        Loading = 1
        Ready = 2
        Error = 3

    class Error(IntEnum):
        None_ = 0
        IncorrectPassword = 1
        Unknown = 2
        IsolationUnavailable = 3

    statusChanged = Signal(object)
    pageCountChanged = Signal(int)
    loaded = Signal(object)
    resultReady = Signal(int, str, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._status = self.Status.Null
        self._pages = []
        self._path = None
        self._generation = 0
        self._serial = 0
        self._tasks = {}
        tasks = self._tasks
        self.destroyed.connect(lambda: [task.cancel() for task in tuple(tasks.values())])

    def _cancel_tasks(self):
        for task in self._tasks.values():
            task.cancel()
        self._tasks.clear()

    def close(self):
        self._generation += 1
        self._cancel_tasks()
        self._pages = []
        self._path = None
        self._status = self.Status.Null
        self.pageCountChanged.emit(0)
        self.statusChanged.emit(self._status)

    def load(self, path):
        self.close()
        self._path = Path(path)
        self._status = self.Status.Loading
        self.statusChanged.emit(self._status)
        self.request("metadata")
        return self.Error.None_

    def cancel_request(self, request_id):
        task = self._tasks.pop(request_id, None)
        if task is not None:
            task.cancel()

    def request(self, action, **params):
        self._serial += 1
        task = _Task(self._generation, self._serial, self._path, action, params)
        task.signals.completed.connect(self._completed)
        self._tasks[self._serial] = task
        _pool().start(task)
        return self._serial

    def _completed(self, generation, request_id, action, result):
        self._tasks.pop(request_id, None)
        if generation != self._generation:
            return
        if action == "metadata":
            error = self.Error.None_
            if "error" in result:
                error = (
                    self.Error.IncorrectPassword
                    if result["error"] == "password"
                    else self.Error.Unknown
                )
                if result["error"] == "isolation":
                    error = self.Error.IsolationUnavailable
                self._status = self.Status.Error
            else:
                self._pages = result["pages"]
                self._status = self.Status.Ready
                self.pageCountChanged.emit(len(self._pages))
            self.statusChanged.emit(self._status)
            self.loaded.emit(error)
        else:
            self.resultReady.emit(request_id, action, result)

    def pageCount(self):
        return len(self._pages)

    def pagePointSize(self, page):
        return QSizeF(*self._pages[page]) if 0 <= page < len(self._pages) else QSizeF()

    def status(self):
        return self._status


class RemoteRenderOptions:
    class Rotation(IntEnum):
        None_ = 0
        Clockwise90 = 1
        Clockwise180 = 2
        Clockwise270 = 3

    def __init__(self):
        self.rotation = 0
        self.annotations = False

    def setScaledSize(self, size):
        pass

    def setRotation(self, rotation):
        self.rotation = int(rotation) * 90

    def setAnnotations(self, enabled):
        """Draw annotation appearances (stamps, filled fields), as a photocopy does."""
        self.annotations = bool(enabled)


class RemotePageRenderer(QObject):
    pageRendered = Signal(int, QSize, QImage, object, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._requests = {}

    def setDocument(self, document):
        self._document = document
        document.resultReady.connect(self._ready)
        document.statusChanged.connect(
            lambda _: self._requests.clear() if document.status() == document.Status.Null else None
        )

    def cancel_pending(self):
        for request_id in self._requests:
            self._document.cancel_request(request_id)
        self._requests.clear()

    def requestPage(self, page, size, options):
        size = bounded_render_size(size)
        request = self._document.request(
            "render",
            page=page,
            size=[size.width(), size.height()],
            rotation=options.rotation,
            annotations=options.annotations,
        )
        self._requests[request] = (page, size, options)
        return request

    def _ready(self, request, action, result):
        parameters = self._requests.pop(request, None)
        if parameters is not None and action == "render":
            page, size, options = parameters
            self.pageRendered.emit(
                page, size, result if isinstance(result, QImage) else QImage(), options, request
            )


def bounded_render_size(size: QSize) -> QSize:
    """Preserve aspect ratio within the same pixel limit for every UI renderer."""
    width, height = max(1, size.width()), max(1, size.height())
    scale = min(1.0, 8192 / max(width, height), math.sqrt(MAX_PIXELS / (width * height)))
    return QSize(max(1, int(width * scale)), max(1, int(height * scale)))


def _resident_tree_bytes(pid: int, proc_root: Path = Path("/proc")) -> int:
    """Count processes forked by every thread, with each process RSS counted once."""
    pending, seen, total = [pid], set(), 0
    while pending:
        current = pending.pop()
        if current in seen:
            continue
        seen.add(current)
        base = proc_root / str(current)
        try:
            fields = (base / "status").read_text().splitlines()
            total += next(
                (int(line.split()[1]) * 1024 for line in fields if line.startswith("VmRSS:")), 0
            )
            for task in (base / "task").iterdir():
                try:
                    pending.extend(int(v) for v in (task / "children").read_text().split())
                except FileNotFoundError:
                    if task.exists():
                        raise OSError("process children cannot be inspected") from None
                    continue
        except FileNotFoundError:
            if current == pid:
                raise
            continue
    return total
