from __future__ import annotations

import threading
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal, Slot

from pdfmod.engine.document_inspection import DocumentInspection, unavailable_inspection
from pdfmod.workers.document_metadata_cache import (
    SHARED_DOCUMENT_METADATA_CACHE,
    DocumentMetadataCache,
)
from pdfmod.workers.process_supervisor import (
    DEFAULT_TIMEOUT_SECONDS,
    ProcessSupervisor,
    ProcessSupervisorError,
)


@dataclass(frozen=True)
class DocumentInspectionResult:
    pdf_path: Path
    inspection: DocumentInspection
    from_cache: bool = False


@dataclass(frozen=True)
class InitialDocumentClassificationResult:
    valid_paths: tuple[Path, ...]
    invalid_count: int
    cancelled: bool = False


def inspect_document_cached(
    pdf_path: Path,
    supervisor: ProcessSupervisor,
    metadata_cache: DocumentMetadataCache = SHARED_DOCUMENT_METADATA_CACHE,
) -> tuple[DocumentInspection, bool]:
    """Inspect a file once per ephemeral file version, without caching its path."""

    fingerprint = metadata_cache.fingerprint(pdf_path)
    if fingerprint is not None:
        cached = metadata_cache.lookup(fingerprint)
        if cached is not None and cached.inspection is not None:
            return cached.inspection, True

    inspection = supervisor.inspect_document(pdf_path)
    if fingerprint is not None and metadata_cache.fingerprint(pdf_path) == fingerprint:
        metadata_cache.store_inspection(fingerprint, inspection)
    return inspection, False


class DocumentInspectionWorker(QObject):
    finished = Signal(object)

    def __init__(
        self,
        pdf_path: Path,
        supervisor: ProcessSupervisor | None = None,
        metadata_cache: DocumentMetadataCache | None = None,
    ) -> None:
        super().__init__()
        self._pdf_path = pdf_path
        self._supervisor = supervisor or ProcessSupervisor()
        self._metadata_cache = (
            SHARED_DOCUMENT_METADATA_CACHE if metadata_cache is None else metadata_cache
        )

    @Slot()
    def run(self) -> None:
        from_cache = False
        try:
            inspection, from_cache = inspect_document_cached(
                self._pdf_path,
                self._supervisor,
                self._metadata_cache,
            )
        except ProcessSupervisorError as exc:
            inspection = unavailable_inspection(_size_bytes(self._pdf_path), exc.code)
        self.finished.emit(DocumentInspectionResult(self._pdf_path, inspection, from_cache))


class InitialDocumentClassificationWorker(QObject):
    """Classify startup files away from the GUI thread."""

    finished = Signal(object)
    progress = Signal(int, int)

    def __init__(
        self,
        paths: Sequence[Path],
        supervisor: ProcessSupervisor | None = None,
        metadata_cache: DocumentMetadataCache | None = None,
    ) -> None:
        super().__init__()
        self._paths = tuple(Path(path) for path in paths)
        self._supervisor = supervisor or ProcessSupervisor()
        self._metadata_cache = (
            SHARED_DOCUMENT_METADATA_CACHE if metadata_cache is None else metadata_cache
        )
        self._cancel_requested = threading.Event()

    def request_cancel(self) -> None:
        self._cancel_requested.set()

    @Slot()
    def run(self) -> None:
        valid_paths: list[Path] = []
        invalid_count = 0
        total = len(self._paths)
        for index, candidate in enumerate(self._paths, start=1):
            if self._cancel_requested.is_set():
                break
            if (
                candidate.suffix.lower() != ".pdf"
                or not candidate.exists()
                or not candidate.is_file()
            ):
                invalid_count += 1
                self.progress.emit(index, total)
                continue
            try:
                inspection, _from_cache = inspect_document_cached(
                    candidate,
                    self._supervisor,
                    self._metadata_cache,
                )
            except ProcessSupervisorError as exc:
                if exc.code == "user_cancelled":
                    self._cancel_requested.set()
                    break
                invalid_count += 1
            else:
                if inspection.can_open:
                    valid_paths.append(candidate)
                else:
                    invalid_count += 1
            self.progress.emit(index, total)

        self.finished.emit(
            InitialDocumentClassificationResult(
                valid_paths=tuple(valid_paths),
                invalid_count=invalid_count,
                cancelled=self._cancel_requested.is_set(),
            )
        )


class QtDocumentInspectionRunner(QObject):
    finished = Signal(object)

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        metadata_cache: DocumentMetadataCache | None = None,
    ) -> None:
        super().__init__(parent)
        self._thread: QThread | None = None
        self._worker: DocumentInspectionWorker | None = None
        self._supervisor: ProcessSupervisor | None = None
        self._timeout_seconds = timeout_seconds
        self._metadata_cache = (
            SHARED_DOCUMENT_METADATA_CACHE if metadata_cache is None else metadata_cache
        )
        self._running = False
        self._pending_result: DocumentInspectionResult | None = None

    def is_running(self) -> bool:
        return self._running

    def start(self, pdf_path: Path) -> None:
        if self.is_running():
            raise RuntimeError("a document inspection job is already running")

        self._running = True
        self._pending_result = None
        self._thread = QThread(self)
        self._supervisor = ProcessSupervisor(timeout_seconds=self._timeout_seconds)
        self._worker = DocumentInspectionWorker(
            pdf_path,
            self._supervisor,
            self._metadata_cache,
        )
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._handle_finished)
        self._worker.finished.connect(self._thread.quit)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.destroyed.connect(self._cleanup)
        self._thread.start()

    def cancel(self) -> bool:
        if not self._running or self._supervisor is None:
            return False
        return self._supervisor.cancel()

    @Slot(object)
    def _handle_finished(self, result: DocumentInspectionResult) -> None:
        self._pending_result = result

    @Slot()
    def _cleanup(self) -> None:
        result = self._pending_result
        self._thread = None
        self._worker = None
        self._supervisor = None
        self._pending_result = None
        self._running = False
        if result is not None:
            self.finished.emit(result)


class QtInitialDocumentClassificationRunner(QObject):
    """Asynchronous startup classification API for the application coordinator."""

    finished = Signal(object)
    progress = Signal(int, int)

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        metadata_cache: DocumentMetadataCache | None = None,
    ) -> None:
        super().__init__(parent)
        self._thread: QThread | None = None
        self._worker: InitialDocumentClassificationWorker | None = None
        self._supervisor: ProcessSupervisor | None = None
        self._timeout_seconds = timeout_seconds
        self._metadata_cache = (
            SHARED_DOCUMENT_METADATA_CACHE if metadata_cache is None else metadata_cache
        )
        self._running = False
        self._pending_result: InitialDocumentClassificationResult | None = None

    def is_running(self) -> bool:
        return self._running

    def start(self, paths: Sequence[Path]) -> None:
        if self.is_running():
            raise RuntimeError("an initial document classification is already running")

        self._running = True
        self._pending_result = None
        self._thread = QThread(self)
        self._supervisor = ProcessSupervisor(timeout_seconds=self._timeout_seconds)
        self._worker = InitialDocumentClassificationWorker(
            paths,
            self._supervisor,
            self._metadata_cache,
        )
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self.progress.emit)
        self._worker.finished.connect(self._handle_finished)
        self._worker.finished.connect(self._thread.quit)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.destroyed.connect(self._cleanup)
        self._thread.start()

    def cancel(self) -> bool:
        if not self._running or self._worker is None or self._supervisor is None:
            return False
        self._worker.request_cancel()
        self._supervisor.cancel()
        return True

    @Slot(object)
    def _handle_finished(self, result: InitialDocumentClassificationResult) -> None:
        self._pending_result = result

    @Slot()
    def _cleanup(self) -> None:
        result = self._pending_result
        self._thread = None
        self._worker = None
        self._supervisor = None
        self._pending_result = None
        self._running = False
        if result is not None:
            self.finished.emit(result)


def _size_bytes(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0
