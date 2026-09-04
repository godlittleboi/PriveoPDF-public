from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Slot
from PySide6.QtWidgets import QDialog, QWidget

from pdfmod.app.settings import AppSettings
from pdfmod.engine.document_inspection import DocumentInspectionService
from pdfmod.ui.first_run_dialog import FirstRunDialog
from pdfmod.workers.document_inspection_runner import (
    InitialDocumentClassificationResult,
    QtInitialDocumentClassificationRunner,
)
from pdfmod.workers.document_metadata_cache import DocumentMetadataCache

InitialPreferencesCallback = Callable[[str], None]
FirstRunDialogFactory = Callable[[AppSettings, QWidget], FirstRunDialog]


class StartupCoordinator(QObject):
    """Route startup documents asynchronously and defer initial preferences setup."""

    def __init__(
        self,
        *,
        parent: QWidget,
        settings: AppSettings,
        selected_document_path: Callable[[], Path | None],
        show_dashboard: Callable[[], None],
        open_initial_documents: Callable[[tuple[Path, ...], Path], None],
        show_invalid_message: Callable[[], None],
        show_multiple_message: Callable[[], None],
        apply_initial_preferences: InitialPreferencesCallback,
        refresh_updates: Callable[[], None],
        disable_updates: Callable[[], None],
        is_closing: Callable[[], bool],
        first_run_dialog_factory: FirstRunDialogFactory = FirstRunDialog,
        metadata_cache: DocumentMetadataCache | None = None,
    ) -> None:
        super().__init__(parent)
        self._parent = parent
        self._settings = settings
        self._selected_document_path = selected_document_path
        self._show_dashboard = show_dashboard
        self._open_initial_documents = open_initial_documents
        self._show_invalid_message = show_invalid_message
        self._show_multiple_message = show_multiple_message
        self._apply_initial_preferences = apply_initial_preferences
        self._refresh_updates = refresh_updates
        self._disable_updates = disable_updates
        self._is_closing = is_closing
        self._first_run_dialog_factory = first_run_dialog_factory
        self._setup_deferred_for_classification = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._finish_when_ready)
        self._classification_runner = QtInitialDocumentClassificationRunner(
            self,
            metadata_cache=metadata_cache,
        )
        self._classification_runner.finished.connect(self._classification_finished)

    @property
    def timer(self) -> QTimer:
        return self._timer

    @property
    def classification_runner(self) -> QtInitialDocumentClassificationRunner:
        return self._classification_runner

    def start(self, initial_files: Sequence[Path]) -> None:
        self._route_initial_files(tuple(Path(path) for path in initial_files))
        self._timer.start(0)

    def close(self) -> None:
        if self._timer.isActive():
            self._timer.stop()
        if self._classification_runner.is_running():
            self._classification_runner.cancel()

    def finish_startup(self) -> None:
        if self._is_closing():
            return
        has_legacy_preferences = self._settings.has_legacy_user_preferences()
        if not self._settings.initial_setup_completed() and has_legacy_preferences:
            self._settings.set_initial_setup_completed(True)
            self._settings.sync()

        if self._settings.should_show_initial_setup():
            dialog = self._first_run_dialog_factory(self._settings, self._parent)
            dialog.preferences_applied.connect(self._apply_initial_preferences)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                self._disable_updates()
                return

        self._refresh_updates()

    def _finish_when_ready(self) -> None:
        if self._classification_runner.is_running():
            self._setup_deferred_for_classification = True
            return
        self.finish_startup()

    def classify_files_now(
        self,
        initial_files: Sequence[Path],
    ) -> tuple[tuple[Path, ...], tuple[Path, ...]]:
        """Compatibility helper; application startup itself uses the async runner."""

        service = DocumentInspectionService()
        valid: list[Path] = []
        invalid: list[Path] = []
        for path in initial_files:
            candidate = Path(path)
            if (
                candidate.suffix.lower() != ".pdf"
                or not candidate.exists()
                or not candidate.is_file()
            ):
                invalid.append(candidate)
                continue
            if service.inspect(candidate).can_open:
                valid.append(candidate)
            else:
                invalid.append(candidate)
        return tuple(valid), tuple(invalid)

    def _route_initial_files(self, initial_files: tuple[Path, ...]) -> None:
        if not initial_files:
            selected_path = self._selected_document_path()
            if selected_path is not None and self._settings.open_last_pdf_on_startup():
                self._open_initial_documents((), selected_path)
            else:
                self._show_dashboard()
            return

        # Give immediate feedback while every potentially hostile PDF is classified off-thread.
        self._show_dashboard()
        self._classification_runner.start(initial_files)

    @Slot(object)
    def _classification_finished(self, value: object) -> None:
        try:
            if not isinstance(value, InitialDocumentClassificationResult):
                return
            if self._is_closing() or value.cancelled:
                return
            if not value.valid_paths:
                self._show_dashboard()
                self._show_invalid_message()
                return
            self._open_initial_documents(value.valid_paths, value.valid_paths[0])
            if value.invalid_count:
                self._show_invalid_message()
            elif len(value.valid_paths) > 1:
                self._show_multiple_message()
        finally:
            if self._setup_deferred_for_classification and not self._is_closing():
                self._setup_deferred_for_classification = False
                self._timer.start(0)
