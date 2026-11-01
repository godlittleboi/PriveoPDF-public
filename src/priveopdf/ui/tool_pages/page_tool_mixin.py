"""Shared behaviour of the page-plan tools (Réorganiser, Diviser, Extraire,
Supprimer): source from the workspace, proposed output, start of the job.

A mixin, not a widget: each page keeps its own widgets and state. It expects
`_input_path`, `_page_count`, `_spec`, `_settings`, `_locale`, `_output`,
`_action_bar`, `_job_runner`, `_source_check`, `_launch_context`, and the
methods `_set_input_path`, `_clear_input_path`, `_blocker`, `_build_job`,
`_update_action_state`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from priveopdf.domain.document_context import ToolLaunchContext
from priveopdf.ui.components import expected_output_pages, output_suffix, proposed_output_directory
from priveopdf.ui.i18n import tr
from priveopdf.ui.workspace_state import WorkspaceDocument


class PageToolMixin:
    _input_path: Path | None
    _launch_context: ToolLaunchContext | None

    def set_workspace_document(self, document: WorkspaceDocument | None) -> None:
        page: Any = self
        if document is None:
            page._clear_input_path()
            return
        if self._input_path != document.path or page._source_check.is_stale(document.path):
            page._set_input_path(document.path)

    def set_tool_launch_context(self, context: ToolLaunchContext | None) -> None:
        page: Any = self
        self._launch_context = context
        if context is None or not context.input_files:
            return
        source = context.input_files[0]
        if self._input_path != source or page._source_check.is_stale(source):
            page._set_input_path(source)

    def _propose_output(self) -> None:
        page: Any = self
        source = self._input_path
        if source is None:
            return
        directory = proposed_output_directory(source, page._settings)
        suffix = (
            ""
            if page._spec.output_mode == "directory"
            else output_suffix(page._spec.key, page._locale)
        )
        page._output.propose(directory, source.stem, suffix)

    def _output_changed(self) -> None:
        page: Any = self
        page._action_bar.clear_result()
        page._update_action_state()

    def _start_operation(self) -> None:
        page: Any = self
        if page._job_runner.is_running() or page._blocker():
            return
        try:
            job = page._build_job()
        except ValueError:
            page._action_bar.show_error(tr("visual.error.invalid_plan", page._locale))
            return
        page._action_bar.set_running(
            tr("job.running", page._locale),
            expected_pages=expected_output_pages(job, page._page_count),
        )
        page._job_runner.start(job)
        page._update_action_state()
