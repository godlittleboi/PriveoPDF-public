from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal, Slot

from pdfmod.app.beta_diagnostics import record_diagnostic_event
from pdfmod.domain.jobs import JobRequest, JobResult
from pdfmod.workers.document_metadata_cache import (
    SHARED_DOCUMENT_METADATA_CACHE,
    DocumentMetadataCache,
)
from pdfmod.workers.process_supervisor import (
    DEFAULT_TIMEOUT_SECONDS,
    ProcessSupervisor,
    ProcessSupervisorError,
    run_structural_job,
)


@dataclass(frozen=True)
class PageCountResult:
    success: bool
    pdf_path: Path
    page_count: int = 0
    user_message: str = ""
    technical_detail: str = ""
    from_cache: bool = False


class JobWorker(QObject):
    finished = Signal(object)

    def __init__(
        self,
        job: JobRequest,
        supervisor: ProcessSupervisor | None = None,
    ) -> None:
        super().__init__()
        self._job = job
        self._supervisor = supervisor

    @Slot()
    def run(self) -> None:
        if self._supervisor is None:
            result = run_structural_job(self._job)
        else:
            result = self._supervisor.run_job(self._job)
        self.finished.emit(result)


class PageCountWorker(QObject):
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
        fingerprint = self._metadata_cache.fingerprint(self._pdf_path)
        if fingerprint is not None:
            cached = self._metadata_cache.lookup(fingerprint)
            if cached is not None and cached.page_count is not None:
                self.finished.emit(
                    PageCountResult(
                        success=True,
                        pdf_path=self._pdf_path,
                        page_count=cached.page_count,
                        from_cache=True,
                    )
                )
                return
        try:
            response = self._supervisor.get_page_count(self._pdf_path)
            if not response.success or response.page_count is None:
                self.finished.emit(
                    PageCountResult(
                        success=False,
                        pdf_path=self._pdf_path,
                        user_message=response.user_message,
                        technical_detail=response.technical_code,
                    )
                )
                return
            if (
                fingerprint is not None
                and self._metadata_cache.fingerprint(self._pdf_path) == fingerprint
            ):
                self._metadata_cache.store_page_count(fingerprint, response.page_count)
            self.finished.emit(
                PageCountResult(
                    success=True,
                    pdf_path=self._pdf_path,
                    page_count=response.page_count,
                    user_message=response.user_message,
                )
            )
        except ProcessSupervisorError as exc:
            self.finished.emit(
                PageCountResult(
                    success=False,
                    pdf_path=self._pdf_path,
                    user_message=exc.user_message,
                    technical_detail=exc.code,
                )
            )


class QtJobRunner(QObject):
    finished = Signal(object)

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        super().__init__(parent)
        self._thread: QThread | None = None
        self._worker: JobWorker | None = None
        self._supervisor: ProcessSupervisor | None = None
        self._timeout_seconds = timeout_seconds
        self._running = False
        self._pending_result: JobResult | None = None

    def is_running(self) -> bool:
        return self._running

    def start(self, job: JobRequest) -> None:
        if self.is_running():
            raise RuntimeError("a job is already running")

        self._running = True
        record_diagnostic_event("job_started", operation=job.operation.value)
        self._pending_result = None
        self._thread = QThread(self)
        self._supervisor = ProcessSupervisor(timeout_seconds=self._timeout_seconds)
        self._worker = JobWorker(job, self._supervisor)
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
        cancelled = self._supervisor.cancel()
        record_diagnostic_event("job_cancel_requested", accepted=cancelled)
        return cancelled

    @Slot(object)
    def _handle_finished(self, result: JobResult) -> None:
        record_diagnostic_event(
            "job_finished",
            success=result.success,
            duration_ms=result.duration_ms,
            output_count=len(result.output_files),
            warning_count=len(result.warnings),
        )
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


class QtPageCountRunner(QObject):
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
        self._worker: PageCountWorker | None = None
        self._supervisor: ProcessSupervisor | None = None
        self._timeout_seconds = timeout_seconds
        self._metadata_cache = (
            SHARED_DOCUMENT_METADATA_CACHE if metadata_cache is None else metadata_cache
        )
        self._running = False
        self._pending_result: PageCountResult | None = None

    def is_running(self) -> bool:
        return self._running

    def start(self, pdf_path: Path) -> None:
        if self.is_running():
            raise RuntimeError("a page count job is already running")

        self._running = True
        self._pending_result = None
        self._thread = QThread(self)
        self._supervisor = ProcessSupervisor(timeout_seconds=self._timeout_seconds)
        self._worker = PageCountWorker(
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
    def _handle_finished(self, result: PageCountResult) -> None:
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
