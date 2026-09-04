from __future__ import annotations

from pathlib import Path
from typing import Protocol

from pdfmod.domain.document_context import ToolLaunchContext
from pdfmod.ui.i18n import Locale
from pdfmod.ui.workspace_state import WorkspaceDocument


class LocalizedPage(Protocol):
    def set_locale(self, locale: Locale) -> None: ...


class WorkspaceDocumentPage(Protocol):
    def set_workspace_document(self, document: WorkspaceDocument | None) -> None: ...


class WorkspaceDocumentsPage(Protocol):
    def set_workspace_documents(
        self,
        documents: tuple[WorkspaceDocument, ...],
    ) -> None: ...


class ToolLaunchPage(Protocol):
    def set_tool_launch_context(self, context: ToolLaunchContext | None) -> None: ...


class BusyDocumentProvider(Protocol):
    def busy_document_paths(self) -> tuple[Path, ...]: ...
