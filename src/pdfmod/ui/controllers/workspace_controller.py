from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from pdfmod.app.settings import AppSettings
from pdfmod.app.workspace_session import restore_workspace_session, serialize_workspace_session
from pdfmod.domain.document_context import (
    DocumentContext,
    DocumentSourceKind,
    ToolLaunchContext,
    ToolLaunchSource,
)
from pdfmod.ui.app_store import AppStore
from pdfmod.ui.tool_specs import TOOL_SPECS_BY_KEY
from pdfmod.ui.workspace_state import WorkspaceDocument


class WorkspaceController:
    """Own workspace state, document context, and privacy-aware persistence."""

    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings
        restored = restore_workspace_session(settings.workspace_session_json())
        self._restored_missing_paths = restored.missing_paths
        self._store = AppStore(settings=settings, workspace_state=restored.workspace_state)
        self._document_contexts: dict[Path, DocumentContext] = {}

    @property
    def store(self) -> AppStore:
        return self._store

    @property
    def restored_missing_paths(self) -> tuple[Path, ...]:
        return self._restored_missing_paths

    def add_documents(
        self,
        paths: Sequence[Path],
        *,
        source_kind: DocumentSourceKind,
        last_output_path: Path | None = None,
    ) -> tuple[WorkspaceDocument, ...]:
        added = self._store.add_documents(paths)
        for path in paths:
            document = self._store.document_by_path(path)
            if document is not None:
                self.remember_document_context(
                    document.path,
                    source_kind,
                    last_output_path=last_output_path,
                )
        return added

    def remember_document_context(
        self,
        path: Path,
        source_kind: DocumentSourceKind,
        *,
        last_output_path: Path | None = None,
    ) -> None:
        candidate = Path(path)
        self._document_contexts[candidate.resolve(strict=False)] = DocumentContext(
            source_path=candidate,
            display_name=candidate.name,
            source_kind=source_kind,
            last_output_path=last_output_path,
        )

    def document_context_for(self, document: WorkspaceDocument) -> DocumentContext:
        return self._document_contexts.get(
            document.resolved_path,
            DocumentContext(
                source_path=document.path,
                display_name=document.display_name,
                source_kind="workspace",
            ),
        )

    def build_tool_launch_context(
        self,
        key: str,
        *,
        source: ToolLaunchSource,
        return_to_document: bool,
    ) -> ToolLaunchContext | None:
        document = self._store.selected_document()
        if document is None:
            return None
        context = self.document_context_for(document)
        spec = TOOL_SPECS_BY_KEY.get(key)
        input_files = (document.path,)
        if spec is not None and spec.input_kind == "pdf_multiple":
            input_files = tuple(item.path for item in self._store.documents())
        suffix = spec.default_output_suffix if spec is not None else ""
        basename = f"{document.path.stem}{suffix}.pdf" if suffix else None
        return ToolLaunchContext(
            input_files=input_files,
            active_document=context,
            source=source,
            return_to_document=return_to_document,
            suggested_output_dir=self._settings.default_output_dir() or document.path.parent,
            suggested_output_basename=basename,
        )

    def set_page_count_ready(self, path: Path, page_count: int) -> bool:
        document = self._store.document_by_path(path)
        if document is None:
            return False
        self._store.set_page_count_status(document.document_id, page_count, "ready")
        return True

    def set_page_count_failed(self, path: Path) -> bool:
        document = self._store.document_by_path(path)
        if document is None:
            return False
        self._store.set_page_count_status(document.document_id, None, "error")
        return True

    def persist(self) -> None:
        self._settings.set_workspace_session_json(
            serialize_workspace_session(
                self._store.workspaces(),
                self._store.active_workspace_id(),
                remember_open_documents=self._settings.remember_open_documents(),
            )
        )
        self._settings.sync()

    def close(self) -> None:
        self.persist()
        self._settings.flush()
