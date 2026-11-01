"""Shared skeleton of the single-PDF form tools (Compresser, Protéger,
Déverrouiller, Reconnaître le texte): one source, a settings panel, one action.

A mixin, not a widget: each page keeps its own signals and state. It expects
`_back`, `_description`, `_input`, `_document`, `_source_check`, `_input_path`,
`_job_runner`, `_launch_context`, `workspace_files_added` and `_set_input`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtWidgets import QHBoxLayout, QScrollArea, QVBoxLayout, QWidget

from priveopdf.domain.document_context import ToolLaunchContext
from priveopdf.ui.theme.tokens import SPACING
from priveopdf.ui.workspace_state import WorkspaceDocument


class FormToolPageMixin:
    _input_path: Path | None
    _launch_context: ToolLaunchContext | None
    _job_runner: Any

    def _set_input(self, path: Path) -> None:
        raise NotImplementedError

    def _install_form_layout(self, panel: QWidget) -> None:
        """Back, description, source, file name and its check, then the panel."""

        page: Any = self
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(*(SPACING["xxl"],) * 4)
        layout.setSpacing(SPACING["md"])
        navigation = QHBoxLayout()
        navigation.addWidget(page._back)
        navigation.addStretch(1)
        layout.addLayout(navigation)
        for widget in (page._description, page._input, page._document, page._source_check, panel):
            layout.addWidget(widget)
        layout.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(content)
        root = QVBoxLayout(page)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)

    def _handle_files(self, paths: list[Path]) -> None:
        if paths and not self._job_runner.is_running():
            self._set_input(paths[0])
            page: Any = self
            page.workspace_files_added.emit([paths[0]], True)

    def set_workspace_document(self, document: WorkspaceDocument | None) -> None:
        if document is not None:
            self._set_input(document.path)

    def set_tool_launch_context(self, context: ToolLaunchContext | None) -> None:
        self._launch_context = context
        if context and context.input_files:
            self._set_input(
                context.active_document.source_path
                if context.active_document
                else context.input_files[0]
            )

    def busy_document_paths(self) -> tuple[Path, ...]:
        return (self._input_path,) if self._job_runner.is_running() and self._input_path else ()
