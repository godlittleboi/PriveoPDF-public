"""Shared skeleton of the page-editing tools on the reader (Caviarder, Filigraner).

UX contract, page-editing adaptation of rule 1: the source and its pages on the
left (`IsolatedPdfView`, step 6A), settings, output, action and result stacked
on the right. This base owns the source, its loading and checks (L4, E2, E10),
the output, the job and the result; a subclass adds its settings panel, its
preview on the view, its blockers and its job options.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from priveopdf.app.settings import AppSettings
from priveopdf.domain.document_context import ToolLaunchContext
from priveopdf.domain.errors import EncryptedPdfError, InvalidPdfError
from priveopdf.domain.jobs import JobRequest, JobResult, OperationType
from priveopdf.ui.components import (
    GhostButton,
    OutputTargetField,
    PdfInputPanel,
    SourceCheck,
    SurfacePanel,
    ToolActionBar,
    install_page_tool_layout,
    open_output_folder_if_requested,
    output_suffix,
    page_count_text,
    proposed_output_directory,
)
from priveopdf.ui.components.isolated_pdf_view import IsolatedPdfView
from priveopdf.ui.i18n import Locale, tr
from priveopdf.ui.theme.tokens import SPACING
from priveopdf.ui.tool_specs import TOOL_SPECS_BY_KEY
from priveopdf.ui.workspace_state import WorkspaceDocument
from priveopdf.workers.job_runner import QtJobRunner
from priveopdf.workers.render_client import RemotePdfDocument as QPdfDocument

VIEW_MIN_HEIGHT = 240


def _identity(path: Path) -> tuple[int, ...]:
    try:
        s = path.stat(follow_symlinks=False)
    except OSError:
        return ()
    return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)


class RenderedSourceMixin:
    """Source handling shared by the tools that render their source in the
    document process (Faire pivoter, Caviarder, Filigraner).

    Expects `_input_path`, `_source_check`, `_job_runner`, `_launch_context`,
    `_input_panel`, `_input_status`, `_action_bar`, `_locale`, `_load_error`,
    `page_count_failed`, `load_document` and `_clear_document`.
    """

    _input_path: Path | None
    _launch_context: ToolLaunchContext | None

    def busy_document_paths(self) -> tuple[Path, ...]:
        page: Any = self
        if not page._job_runner.is_running() or self._input_path is None:
            return ()
        return (self._input_path,)

    def set_workspace_document(self, document: WorkspaceDocument | None) -> None:
        page: Any = self
        if document is None:
            page._clear_document()
            return
        if self._input_path != document.path or page._source_check.is_stale(document.path):
            page.load_document(document.path)

    def set_tool_launch_context(self, context: ToolLaunchContext | None) -> None:
        page: Any = self
        self._launch_context = context
        if context is None or not context.input_files:
            return
        source = context.input_files[0]
        if self._input_path != source or page._source_check.is_stale(source):
            page.load_document(source)

    def _record_load_failure(self, path: Path, error: Any) -> None:
        """The source could not be rendered: tell the workspace and the user."""

        page: Any = self
        locked = error == QPdfDocument.Error.IncorrectPassword
        # Isolation unavailable is not the PDF's fault: no code, status kept (B38).
        reason = InvalidPdfError.technical_code
        if locked:
            reason = EncryptedPdfError.technical_code
        elif error == QPdfDocument.Error.IsolationUnavailable:
            reason = ""
        page.page_count_failed.emit(path, reason)
        page._load_error = (
            "viewer.isolation_unavailable"
            if error == QPdfDocument.Error.IsolationUnavailable
            else "viewer.load_error"
        )
        if locked:
            page._source_check.record_problem(path, "protected")
        # L4: a protected or damaged PDF is reported under the source,
        # with `Change PDF` kept; other failures stay at the action.
        reported = bool(page._source_check.problem())
        if not reported:
            page._action_bar.show_error(tr(page._load_error, page._locale))
        page._input_panel.set_loaded(reported)
        page._input_status.setText(path.name if reported else "")


class ViewerToolPage(RenderedSourceMixin, QWidget):
    """Base of a tool that works on the pages shown in the reader skeleton."""

    back_requested = Signal()
    workspace_files_added = Signal(list)
    page_count_ready = Signal(object, int)
    page_count_failed = Signal(object, str)
    job_completed = Signal(object)
    output_pdf_requested = Signal(object)

    # Set by each subclass.
    SPEC_KEY = ""
    OPERATION: OperationType
    READY_STATUS_KEY = ""
    FRESH_BLOCKER_KEY = ""

    def __init__(self, locale: Locale = "en", settings: AppSettings | None = None) -> None:
        super().__init__()
        self._locale = locale
        self._settings = settings or AppSettings()
        self._spec = TOOL_SPECS_BY_KEY[self.SPEC_KEY]
        self._input_path: Path | None = None
        self._page_count: int | None = None
        self._load_error = ""
        self._launch_context: ToolLaunchContext | None = None
        # Identity of the file whose pages are shown: the job carries it, and a
        # file replaced on disk since then blocks the action.
        self._loaded_identity: tuple[int, ...] = ()

        self._document = QPdfDocument(self)
        self._document.loaded.connect(self._document_loaded)
        self._job_runner = QtJobRunner(self)
        self._job_runner.finished.connect(self._job_finished)
        self._job_runner.progress.connect(self._job_progress)

        self._description_label = QLabel()
        self._description_label.setObjectName("HelpText")
        self._description_label.setWordWrap(True)
        self._back_button = GhostButton()
        self._back_button.clicked.connect(self.back_requested.emit)
        self._input_panel = PdfInputPanel(multiple=False, locale=locale)
        self._input_panel.paths_selected.connect(self._handle_files)
        # L4: a protected or damaged source is reported under it.
        self._source_check = SourceCheck(locale, unsigned_copy=True)
        self._source_check.changed.connect(self._source_check_changed)
        # E2: the page names the file it will act on, with its page count.
        self._input_status = QLabel()
        self._input_status.setObjectName("HelpText")

        self._view = IsolatedPdfView()
        self._view.setDocument(self._document)
        self._view.setPageMode(IsolatedPdfView.PageMode.MultiPage)
        self._view.setZoomMode(IsolatedPdfView.ZoomMode.FitToWidth)
        self._view.setMinimumHeight(VIEW_MIN_HEIGHT)
        self._view.zoom_requested.connect(self._zoom_by)
        self._status_label = QLabel()
        self._status_label.setObjectName("StatusText")
        self._status_label.setWordWrap(True)

        self._output = OutputTargetField("file", locale)
        self._output.changed.connect(self._output_changed)
        self._action_bar = ToolActionBar(locale)
        self._action_bar.set_action_text_key(self._spec.action_button_key)
        self._action_bar.action_requested.connect(self._start)
        self._action_bar.cancel_requested.connect(self._job_runner.cancel)
        self._action_bar.open_pdf_requested.connect(self.output_pdf_requested.emit)
        self._action_button = self._action_bar.action_button()

        self._settings_panel = SurfacePanel(role="primary")
        settings_layout = QVBoxLayout(self._settings_panel)
        settings_layout.setContentsMargins(*(SPACING["lg"],) * 4)
        settings_layout.setSpacing(SPACING["sm"])
        self._build_settings(settings_layout)

        viewer_panel = SurfacePanel(role="primary")
        viewer_layout = QVBoxLayout(viewer_panel)
        viewer_layout.setContentsMargins(*(SPACING["lg"],) * 4)
        viewer_layout.setSpacing(SPACING["md"])
        viewer_layout.addWidget(self._view, 1)
        viewer_layout.addWidget(self._status_label)

        self._output_panel = SurfacePanel(role="primary")
        output_layout = QVBoxLayout(self._output_panel)
        output_layout.setContentsMargins(*(SPACING["lg"],) * 4)
        output_layout.setSpacing(SPACING["sm"])
        output_layout.addWidget(self._output)
        output_layout.addWidget(self._action_bar)

        install_page_tool_layout(
            self,
            back=self._back_button,
            header=(
                self._description_label,
                self._input_panel,
                self._input_status,
                self._source_check,
            ),
            pages=viewer_panel,
            side_panels=(self._settings_panel, self._output_panel),
        )
        self.set_locale(locale)
        self._clear_document()

    # Subclass hooks -------------------------------------------------------

    def _build_settings(self, layout: QVBoxLayout) -> None:
        """Create the tool's settings and its preview on `self._view`."""
        raise NotImplementedError

    def _set_settings_texts(self, locale: Locale) -> None:
        raise NotImplementedError

    def _reset_settings(self) -> None:
        """A new source or none: drop what was drawn on the previous one."""

    def _settings_blocker(self) -> str:
        """What the settings still lack, empty when the job can start."""
        raise NotImplementedError

    def _job_options(self) -> dict[str, object]:
        """Options specific to the tool; raises ValueError with a visible reason."""
        raise NotImplementedError

    def _result_message(self, result: JobResult) -> str:
        raise NotImplementedError

    def _settings_running(self, running: bool) -> None:
        """Settings are frozen while the job runs."""
        self._settings_panel.setEnabled(not running)

    # Public API -----------------------------------------------------------

    def set_locale(self, locale: Locale) -> None:
        self._locale = locale
        self._description_label.setText(tr(self._spec.description_key, locale))
        self._back_button.setText(tr("button.back", locale))
        self._set_settings_texts(locale)
        self._input_panel.set_locale(locale)
        self._source_check.set_locale(locale)
        self._output.set_locale(locale)
        self._action_bar.set_locale(locale)
        self._view.set_locale(locale)
        if self._input_path is not None and self._page_count is not None:
            self._input_status.setText(self._ready_status_text(self._input_path))
        self._propose_output()
        self._update_action_state()

    def load_document(self, path: Path) -> None:
        self._input_path = path
        self._page_count = None
        self._loaded_identity = _identity(path)
        self._reset_settings()
        self._document.close()
        self._load_error = ""
        self._action_bar.clear_result()
        self._output.clear()
        self._propose_output()
        self._source_check.check([path])
        # E10: the screen says what is happening while the pages load.
        self._input_status.setText(tr("blank.loading", self._locale, name=path.name))
        self._status_label.setText(tr("viewer.loading", self._locale))
        self._document.load(str(path))
        self._update_action_state()

    def pdf_view(self) -> IsolatedPdfView:
        return self._view

    # Source ---------------------------------------------------------------

    def _ready_status_text(self, path: Path) -> str:
        return tr(
            "blank.ready",
            self._locale,
            name=path.name,
            pages=page_count_text(self._page_count or 0, self._locale),
        )

    def _document_loaded(self, error) -> None:  # noqa: ANN001
        path = self._input_path
        if path is None:
            return
        if error != QPdfDocument.Error.None_:
            self._record_load_failure(path, error)
            self._status_label.setText(tr(self._load_error, self._locale))
            self._update_action_state()
            return
        self._page_count = self._document.pageCount()
        self.page_count_ready.emit(path, self._page_count)
        self._input_panel.set_loaded(True)
        self._input_status.setText(self._ready_status_text(path))
        self._status_label.setText(tr(self.READY_STATUS_KEY, self._locale))
        self._update_action_state()

    def _handle_files(self, paths: list[Path]) -> None:
        if not paths:
            return
        self.load_document(paths[0])
        self.workspace_files_added.emit(paths)

    def _clear_document(self) -> None:
        self._input_path = None
        self._page_count = None
        self._loaded_identity = ()
        self._document.close()
        self._input_panel.set_loaded(False)
        self._input_status.setText("")
        self._source_check.clear()
        self._reset_settings()
        self._status_label.setText(tr("viewer.no_pdf", self._locale))
        self._load_error = ""
        self._action_bar.clear_result()
        self._output.clear()
        self._update_action_state()

    def _zoom_by(self, factor: float, anchor) -> None:  # noqa: ANN001
        self._view.setZoomMode(IsolatedPdfView.ZoomMode.Custom)
        self._view.setZoomFactor(self._view.zoomFactor() * factor, anchor)

    def _source_check_changed(self) -> None:
        if self._load_error and self._source_check.problem():
            self._action_bar.clear_result()
            self._input_panel.set_loaded(True)
        self._update_action_state()

    # Output, job, result --------------------------------------------------

    def _settings_changed(self) -> None:
        # Changing the settings after a success clears the displayed result (rule 8).
        self._action_bar.clear_result()
        self._update_action_state()

    def _propose_output(self) -> None:
        source = self._input_path
        if source is not None:
            directory = proposed_output_directory(source, self._settings)
            self._output.propose(directory, source.stem, output_suffix(self.SPEC_KEY, self._locale))

    def _output_changed(self) -> None:
        self._action_bar.clear_result()
        self._update_action_state()

    def _start(self) -> None:
        if self._job_runner.is_running() or self._blocker():
            return
        try:
            job = self._build_job()
        except ValueError as exc:
            self._action_bar.show_error(str(exc))
            return
        self._action_bar.set_running(
            tr("job.running", self._locale), expected_pages=self._page_count
        )
        self._job_runner.start(job)
        self._update_action_state()

    def _build_job(self) -> JobRequest:
        if self._input_path is None or self._page_count is None:
            raise ValueError(tr("tool.required.source", self._locale))
        output_path = self._output.path()
        if output_path is None:
            raise ValueError(tr("tool.required.output", self._locale))
        options = self._job_options()
        options.update(
            {
                "output_path": output_path,
                "source_identity": self._loaded_identity,
                "allow_unsigned_copy": self._source_check.unsigned_copy_allowed(),
            }
        )
        return JobRequest(
            operation=self.OPERATION,
            input_files=(self._input_path,),
            output_dir=output_path.parent,
            options=options,
            naming_strategy="explicit",
            job_id=str(uuid.uuid4()),
        )

    def _job_progress(self, done: int, total: int) -> None:
        self._action_bar.set_progress(done, total, tr("job.running", self._locale))

    def _job_finished(self, result: JobResult) -> None:
        if result.success:
            # Next free name first: a destination change clears the displayed result.
            self._output.refresh()
        self._action_bar.finish(result, self._result_message(result), page_count=self._page_count)
        self._update_action_state()
        if result.success:
            open_output_folder_if_requested(self._settings, result)
        self.job_completed.emit(result)

    def _blocker(self) -> str:
        if self._input_path is None:
            return tr("tool.required.source", self._locale)
        problem = self._source_check.blocker_text()
        if problem:
            return problem
        if self._load_error:
            return tr("tool.required.valid_source", self._locale)
        if self._page_count is None:
            return tr("viewer.loading", self._locale)
        if not self._loaded_identity or _identity(self._input_path) != self._loaded_identity:
            return tr(self.FRESH_BLOCKER_KEY, self._locale)
        settings_problem = self._settings_blocker()
        if settings_problem:
            return settings_problem
        if self._output.path() is None:
            return tr("tool.required.output", self._locale)
        return ""

    def _update_action_state(self) -> None:
        running = self._job_runner.is_running()
        self._output.setEnabled(not running)
        self._input_panel.setEnabled(not running)
        self._settings_running(running)
        self._action_bar.set_blocker(self._blocker())
