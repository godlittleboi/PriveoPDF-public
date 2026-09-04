from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from uuid import uuid4

PageCountStatus = Literal["unknown", "loading", "ready", "error"]
MAX_WORKSPACES = 5
MAX_DOCUMENTS_PER_WORKSPACE = 100
MAX_WORKSPACE_NAME_CHARS = 120
DEFAULT_WORKSPACE_NAME_PREFIX = "Session"


@dataclass(frozen=True)
class WorkspaceDocument:
    document_id: str
    path: Path
    resolved_path: Path
    page_count: int | None = None
    page_count_status: PageCountStatus = "unknown"

    @property
    def display_name(self) -> str:
        return self.path.name


@dataclass(frozen=True)
class WorkspaceInfo:
    workspace_id: str
    name: str
    documents: tuple[WorkspaceDocument, ...] = ()
    selected_document_id: str | None = None


class WorkspaceState:
    def __init__(
        self,
        documents: Iterable[WorkspaceDocument] = (),
        *,
        workspaces: Iterable[WorkspaceInfo] | None = None,
        active_workspace_id: str | None = None,
    ) -> None:
        self._persistence_revision = 0
        if workspaces is not None:
            restored_workspaces = tuple(workspaces)[:MAX_WORKSPACES]
            if restored_workspaces:
                self._workspaces = tuple(
                    _normalized_workspace(workspace) for workspace in restored_workspaces
                )
                workspace_ids = {workspace.workspace_id for workspace in self._workspaces}
                self._active_workspace_id = (
                    active_workspace_id
                    if active_workspace_id in workspace_ids
                    else self._workspaces[0].workspace_id
                )
                self._workspace_counter = len(self._workspaces)
                return

        initial_documents = tuple(documents)
        self._workspace_counter = 1
        self._active_workspace_id = _workspace_id()
        self._workspaces = (
            WorkspaceInfo(
                workspace_id=self._active_workspace_id,
                name=f"{DEFAULT_WORKSPACE_NAME_PREFIX} 1",
                documents=initial_documents,
                selected_document_id=(
                    initial_documents[0].document_id if initial_documents else None
                ),
            ),
        )

    def workspaces(self) -> tuple[WorkspaceInfo, ...]:
        return self._workspaces

    def persistence_revision(self) -> int:
        """Return a cheap token for changes represented in the persisted session."""

        return self._persistence_revision

    def active_workspace_id(self) -> str:
        return self._active_workspace_id

    def active_workspace(self) -> WorkspaceInfo:
        workspace = self._workspace_by_id(self._active_workspace_id)
        if workspace is None:
            self._active_workspace_id = self._workspaces[0].workspace_id
            self._persistence_revision += 1
            return self._workspaces[0]
        return workspace

    def can_add_workspace(self) -> bool:
        return len(self._workspaces) < MAX_WORKSPACES

    def add_workspace(self) -> WorkspaceInfo | None:
        if not self.can_add_workspace():
            return None
        self._workspace_counter += 1
        workspace = WorkspaceInfo(
            workspace_id=_workspace_id(),
            name=f"{DEFAULT_WORKSPACE_NAME_PREFIX} {self._workspace_counter}",
        )
        self._workspaces = (*self._workspaces, workspace)
        self._active_workspace_id = workspace.workspace_id
        self._persistence_revision += 1
        return workspace

    def select_workspace(self, workspace_id: str) -> bool:
        if self._workspace_by_id(workspace_id) is None:
            return False
        if self._active_workspace_id == workspace_id:
            return True
        self._active_workspace_id = workspace_id
        self._persistence_revision += 1
        return True

    def remove_workspace(self, workspace_id: str) -> WorkspaceInfo | None:
        if len(self._workspaces) <= 1:
            return None
        removed_index = next(
            (
                index
                for index, workspace in enumerate(self._workspaces)
                if workspace.workspace_id == workspace_id
            ),
            None,
        )
        if removed_index is None:
            return None
        removed = self._workspaces[removed_index]
        workspaces = list(self._workspaces)
        workspaces.pop(removed_index)
        self._workspaces = tuple(workspaces)
        if self._active_workspace_id == workspace_id:
            selected_index = min(removed_index, len(self._workspaces) - 1)
            self._active_workspace_id = self._workspaces[selected_index].workspace_id
        self._persistence_revision += 1
        return removed

    def rename_workspace(self, workspace_id: str, name: str) -> bool:
        workspace = self._workspace_by_id(workspace_id)
        if workspace is None:
            return False
        cleaned_name = name.strip()[:MAX_WORKSPACE_NAME_CHARS] or workspace.name
        self._replace_workspace(
            WorkspaceInfo(
                workspace_id=workspace.workspace_id,
                name=cleaned_name,
                documents=workspace.documents,
                selected_document_id=workspace.selected_document_id,
            )
        )
        return True

    def documents(self) -> tuple[WorkspaceDocument, ...]:
        return self.active_workspace().documents

    def selected_document_id(self) -> str | None:
        return self.active_workspace().selected_document_id

    def selected_document(self) -> WorkspaceDocument | None:
        selected_document_id = self.selected_document_id()
        if selected_document_id is None:
            return None
        return self.document_by_id(selected_document_id)

    def document_by_id(self, document_id: str) -> WorkspaceDocument | None:
        return next(
            (document for document in self.documents() if document.document_id == document_id),
            None,
        )

    def document_by_path(self, path: Path) -> WorkspaceDocument | None:
        resolved_path = Path(path).resolve(strict=False)
        for workspace in self._workspaces:
            for document in workspace.documents:
                if document.resolved_path == resolved_path:
                    return document
        return None

    def add_documents(self, paths: Iterable[Path]) -> tuple[WorkspaceDocument, ...]:
        workspace = self.active_workspace()
        documents = list(workspace.documents)
        known = {document.resolved_path for document in documents}
        added: list[WorkspaceDocument] = []
        for path in paths:
            if len(documents) >= MAX_DOCUMENTS_PER_WORKSPACE:
                break
            candidate = Path(path)
            if (
                candidate.suffix.lower() != ".pdf"
                or not candidate.exists()
                or not candidate.is_file()
            ):
                continue
            resolved_path = candidate.resolve(strict=True)
            if resolved_path in known:
                continue
            document = WorkspaceDocument(
                document_id=new_document_id(),
                path=candidate,
                resolved_path=resolved_path,
            )
            documents.append(document)
            added.append(document)
            known.add(resolved_path)

        if added:
            selected_document_id = workspace.selected_document_id
            if selected_document_id is None:
                selected_document_id = added[0].document_id
            self._replace_workspace(
                WorkspaceInfo(
                    workspace_id=workspace.workspace_id,
                    name=workspace.name,
                    documents=tuple(documents),
                    selected_document_id=selected_document_id,
                )
            )
        return tuple(added)

    def select_document(self, document_id: str) -> bool:
        if self.document_by_id(document_id) is None:
            return False
        workspace = self.active_workspace()
        self._replace_workspace(
            WorkspaceInfo(
                workspace_id=workspace.workspace_id,
                name=workspace.name,
                documents=workspace.documents,
                selected_document_id=document_id,
            )
        )
        return True

    def set_documents(self, documents: Iterable[WorkspaceDocument]) -> None:
        workspace = self.active_workspace()
        new_documents = tuple(documents)
        document_ids = {document.document_id for document in new_documents}
        selected_document_id = workspace.selected_document_id
        if selected_document_id not in document_ids:
            selected_document_id = new_documents[0].document_id if new_documents else None
        self._replace_workspace(
            WorkspaceInfo(
                workspace_id=workspace.workspace_id,
                name=workspace.name,
                documents=new_documents,
                selected_document_id=selected_document_id,
            )
        )

    def remove_document(self, document_id: str) -> WorkspaceDocument | None:
        workspace = self.active_workspace()
        documents = list(workspace.documents)
        removed_index = next(
            (
                index
                for index, document in enumerate(documents)
                if document.document_id == document_id
            ),
            None,
        )
        if removed_index is None:
            return None
        removed = documents.pop(removed_index)
        selected_document_id = workspace.selected_document_id
        if selected_document_id == document_id:
            selected_document_id = (
                documents[min(removed_index, len(documents) - 1)].document_id if documents else None
            )
        self._replace_workspace(
            WorkspaceInfo(
                workspace_id=workspace.workspace_id,
                name=workspace.name,
                documents=tuple(documents),
                selected_document_id=selected_document_id,
            )
        )
        return removed

    def set_page_count_status(
        self,
        document_id: str,
        page_count: int | None,
        status: PageCountStatus,
    ) -> None:
        updated_workspaces: list[WorkspaceInfo] = []
        for workspace in self._workspaces:
            updated_documents: list[WorkspaceDocument] = []
            changed = False
            for document in workspace.documents:
                if document.document_id == document_id:
                    changed = True
                    updated_documents.append(
                        WorkspaceDocument(
                            document_id=document.document_id,
                            path=document.path,
                            resolved_path=document.resolved_path,
                            page_count=page_count,
                            page_count_status=status,
                        )
                    )
                else:
                    updated_documents.append(document)
            updated_workspaces.append(
                WorkspaceInfo(
                    workspace_id=workspace.workspace_id,
                    name=workspace.name,
                    documents=tuple(updated_documents) if changed else workspace.documents,
                    selected_document_id=workspace.selected_document_id,
                )
            )
        self._workspaces = tuple(updated_workspaces)

    def _workspace_by_id(self, workspace_id: str) -> WorkspaceInfo | None:
        return next(
            (workspace for workspace in self._workspaces if workspace.workspace_id == workspace_id),
            None,
        )

    def _replace_workspace(self, replacement: WorkspaceInfo) -> None:
        current = self._workspace_by_id(replacement.workspace_id)
        if current == replacement:
            return
        self._workspaces = tuple(
            replacement if workspace.workspace_id == replacement.workspace_id else workspace
            for workspace in self._workspaces
        )
        self._persistence_revision += 1


def new_document_id() -> str:
    """Return a per-session identifier that reveals nothing about the document path."""
    return str(uuid4())


def _workspace_id() -> str:
    return str(uuid4())


def workspace_id() -> str:
    return _workspace_id()


def _normalized_workspace(workspace: WorkspaceInfo) -> WorkspaceInfo:
    documents = workspace.documents[:MAX_DOCUMENTS_PER_WORKSPACE]
    document_ids = {document.document_id for document in documents}
    selected_document_id = workspace.selected_document_id
    if selected_document_id not in document_ids:
        selected_document_id = documents[0].document_id if documents else None
    return WorkspaceInfo(
        workspace_id=workspace.workspace_id or _workspace_id(),
        name=(
            workspace.name.strip()[:MAX_WORKSPACE_NAME_CHARS]
            or f"{DEFAULT_WORKSPACE_NAME_PREFIX} 1"
        ),
        documents=documents,
        selected_document_id=selected_document_id,
    )
