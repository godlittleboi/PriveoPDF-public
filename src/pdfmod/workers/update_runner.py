from __future__ import annotations

import os

from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot

from pdfmod.app.network_broker import request_update_check
from pdfmod.app.source_update import check_source_update, source_checkout_available
from pdfmod.app.update_checker import check_for_updates


class UpdateCheckWorker(QObject):
    finished = Signal(object)

    def __init__(
        self,
        manifest_url: str = "",
        *,
        allow_source_checkout: bool = False,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._manifest_url = manifest_url
        self._allow_source_checkout = allow_source_checkout

    @Slot()
    def run(self) -> None:
        if os.environ.get("PRIVEOPDF_DOCUMENT_SANDBOX") == "1":
            self.finished.emit(
                request_update_check(
                    allow_source_checkout=self._allow_source_checkout,
                )
            )
            return
        if self._allow_source_checkout and source_checkout_available():
            self.finished.emit(check_source_update())
            return
        self.finished.emit(check_for_updates(manifest_url=self._manifest_url))


class QtUpdateCheckRunner(QObject):
    finished = Signal(object)
    idle = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._thread: QThread | None = None
        self._worker: UpdateCheckWorker | None = None
        self._running = False
        self._source_checkout_authorized_once = False

    def is_running(self) -> bool:
        return self._running

    def authorize_source_checkout_once(self) -> None:
        if self.is_running():
            raise RuntimeError("an update check is already running")
        self._source_checkout_authorized_once = True

    def start(self, manifest_url: str = "") -> None:
        if self.is_running():
            raise RuntimeError("an update check is already running")

        allow_source_checkout = self._source_checkout_authorized_once
        self._source_checkout_authorized_once = False
        self._running = True
        self._thread = QThread(self)
        self._worker = UpdateCheckWorker(
            manifest_url,
            allow_source_checkout=allow_source_checkout,
        )
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._handle_finished)
        self._worker.finished.connect(self._thread.quit)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.destroyed.connect(self._cleanup)
        self._thread.start()

    @Slot(object)
    def _handle_finished(self, result) -> None:  # noqa: ANN001
        self.finished.emit(result)

    @Slot()
    def _cleanup(self) -> None:
        self._thread = None
        self._worker = None
        self._running = False
        QTimer.singleShot(0, self.idle.emit)
