from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal, Slot

from priveopdf.app.beta_diagnostics import record_diagnostic_event
from priveopdf.domain.jobs import JobRequest, JobResult
from priveopdf.workers.document_metadata_cache import (
    SHARED_DOCUMENT_METADATA_CACHE,
    DocumentMetadataCache,
)
from priveopdf.workers.process_supervisor import (
    DEFAULT_TIMEOUT_SECONDS,
    ProcessSupervisor,
    ProcessSupervisorError,
    ResourceLimits,
    run_structural_job,
)
from priveopdf.workers.thread_shutdown import shutdown_runner_thread


@dataclass(frozen=True)
class PageCountResult:
    success: bool
    pdf_path: Path
    page_count: int = 0
    user_message: str = ""
    technical_detail: str = ""
    from_cache: bool = False
    signed: bool = False


class JobWorker(QObject):
    finished = Signal(object)

    def __init__(
        self,
        job: JobRequest,
        supervisor: ProcessSupervisor | None = None,
    ) -> None:
        super().__init__()
        self._job: JobRequest | None = job
        self._supervisor = supervisor

    @Slot()
    def run(self) -> None:
        job = self._job
        if job is None:
            return
        try:
            if self._supervisor is None:
                result = run_structural_job(job)
            else:
                result = self._supervisor.run_job(job)
        except Exception as exc:  # noqa: BLE001 - last boundary of the worker thread
            # Without this, `finished` is never emitted and the tool stays "in progress".
            # Only the exception type is recorded: its text may contain paths or a password.
            record_diagnostic_event("job_internal_error", exception=type(exc).__name__)
            result = JobResult(
                success=False,
                output_files=(),
                warnings=(),
                user_message="Le traitement a echoue.",
                technical_detail="internal_error",
            )
        finally:
            # Release the transient request (and password) once processing ends.
            self._job = None
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
            # A count cached by an inspection does not know about signatures:
            # the file is counted again so the tool can show them on load (E4).
            if cached is not None and cached.page_count is not None and cached.signed is not None:
                self.finished.emit(
                    PageCountResult(
                        success=True,
                        pdf_path=self._pdf_path,
                        page_count=cached.page_count,
                        from_cache=True,
                        signed=cached.signed,
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
                self._metadata_cache.store_page_count(
                    fingerprint, response.page_count, response.signed
                )
            self.finished.emit(
                PageCountResult(
                    success=True,
                    pdf_path=self._pdf_path,
                    page_count=response.page_count,
                    user_message=response.user_message,
                    signed=response.signed,
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
    progress = Signal(int, int)

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        limits: ResourceLimits | None = None,
    ) -> None:
        super().__init__(parent)
        self._thread: QThread | None = None
        self._worker: JobWorker | None = None
        self._supervisor: ProcessSupervisor | None = None
        self._timeout_seconds = timeout_seconds
        self._limits = limits
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
        self._supervisor = ProcessSupervisor(
            timeout_seconds=self._timeout_seconds, limits=self._limits, progress=self.progress.emit
        )
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

    def shutdown(self) -> bool:
        """Window closing: cancel and wait for the thread (B22)."""

        return shutdown_runner_thread(self._thread, self.cancel)

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

    def shutdown(self) -> bool:
        """Window closing: cancel and wait for the thread (B22)."""

        return shutdown_runner_thread(self._thread, self.cancel)

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
