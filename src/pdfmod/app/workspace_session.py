from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from pdfmod.ui.workspace_state import (
    DEFAULT_WORKSPACE_NAME_PREFIX,
    MAX_DOCUMENTS_PER_WORKSPACE,
    MAX_WORKSPACE_NAME_CHARS,
    MAX_WORKSPACES,
    WorkspaceDocument,
    WorkspaceInfo,
    WorkspaceState,
    new_document_id,
    workspace_id,
)

SCHEMA_VERSION = 2
LEGACY_SCHEMA_VERSION = 1
MAX_SESSION_PAYLOAD_BYTES = 256 * 1024
MAX_PATH_CHARS = 4096
MAX_IDENTIFIER_CHARS = 64


@dataclass(frozen=True)
class WorkspaceSessionRestore:
    workspace_state: WorkspaceState | None
    missing_paths: tuple[Path, ...] = ()
    migrated_from_version: int | None = None


def serialize_workspace_session(
    workspaces: tuple[WorkspaceInfo, ...],
    active_workspace_id: str,
    *,
    remember_open_documents: bool = False,
) -> str:
    if not remember_open_documents:
        return ""

    serialized_workspaces: list[dict[str, Any]] = []
    for index, workspace in enumerate(workspaces[:MAX_WORKSPACES], start=1):
        documents: list[dict[str, str]] = []
        for document in workspace.documents[:MAX_DOCUMENTS_PER_WORKSPACE]:
            path_text = str(document.path)
            if not path_text or len(path_text) > MAX_PATH_CHARS:
                continue
            documents.append(
                {
                    "document_id": _safe_identifier(document.document_id, new_document_id()),
                    "path": path_text,
                }
            )
        document_ids = {document["document_id"] for document in documents}
        selected_document_id = (
            workspace.selected_document_id
            if workspace.selected_document_id in document_ids
            else (documents[0]["document_id"] if documents else None)
        )
        serialized_workspaces.append(
            {
                "workspace_id": _safe_identifier(workspace.workspace_id, workspace_id()),
                "name": (
                    workspace.name.strip()[:MAX_WORKSPACE_NAME_CHARS]
                    or f"{DEFAULT_WORKSPACE_NAME_PREFIX} {index}"
                ),
                "selected_document_id": selected_document_id,
                "documents": documents,
            }
        )

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "active_workspace_id": _safe_identifier(active_workspace_id, ""),
        "workspaces": serialized_workspaces,
    }
    encoded = _encode_payload(payload)
    while len(encoded.encode("utf-8")) > MAX_SESSION_PAYLOAD_BYTES:
        workspace_with_documents = next(
            (workspace for workspace in reversed(serialized_workspaces) if workspace["documents"]),
            None,
        )
        if workspace_with_documents is None:
            return ""
        workspace_with_documents["documents"].pop()
        remaining_ids = {
            document["document_id"] for document in workspace_with_documents["documents"]
        }
        if workspace_with_documents["selected_document_id"] not in remaining_ids:
            workspace_with_documents["selected_document_id"] = (
                workspace_with_documents["documents"][0]["document_id"]
                if workspace_with_documents["documents"]
                else None
            )
        encoded = _encode_payload(payload)
    return encoded


def restore_workspace_session(payload: str) -> WorkspaceSessionRestore:
    if not payload.strip() or len(payload.encode("utf-8")) > MAX_SESSION_PAYLOAD_BYTES:
        return WorkspaceSessionRestore(None)
    try:
        decoded = json.loads(payload)
    except (json.JSONDecodeError, RecursionError):
        return WorkspaceSessionRestore(None)
    if not isinstance(decoded, dict):
        return WorkspaceSessionRestore(None)
    schema_version = decoded.get("schema_version")
    if schema_version not in {LEGACY_SCHEMA_VERSION, SCHEMA_VERSION}:
        return WorkspaceSessionRestore(None)

    raw_workspaces = decoded.get("workspaces")
    if not isinstance(raw_workspaces, list):
        return WorkspaceSessionRestore(None)

    missing_paths: list[Path] = []
    workspaces: list[WorkspaceInfo] = []
    for index, raw_workspace in enumerate(raw_workspaces[:MAX_WORKSPACES], start=1):
        if not isinstance(raw_workspace, dict):
            continue
        workspace = _restore_workspace(raw_workspace, index, missing_paths, schema_version)
        if workspace is not None:
            workspaces.append(workspace)

    if not workspaces:
        return WorkspaceSessionRestore(
            None,
            tuple(missing_paths),
            LEGACY_SCHEMA_VERSION if schema_version == LEGACY_SCHEMA_VERSION else None,
        )

    active_workspace_id = decoded.get("active_workspace_id")
    active_id = (
        active_workspace_id
        if isinstance(active_workspace_id, str)
        and 0 < len(active_workspace_id) <= MAX_IDENTIFIER_CHARS
        else None
    )
    return WorkspaceSessionRestore(
        WorkspaceState(workspaces=tuple(workspaces), active_workspace_id=active_id),
        tuple(missing_paths),
        LEGACY_SCHEMA_VERSION if schema_version == LEGACY_SCHEMA_VERSION else None,
    )


def _restore_workspace(
    raw_workspace: dict[str, Any],
    index: int,
    missing_paths: list[Path],
    schema_version: int,
) -> WorkspaceInfo | None:
    raw_id = raw_workspace.get("workspace_id")
    restored_id = (
        raw_id.strip()
        if isinstance(raw_id, str) and 0 < len(raw_id.strip()) <= MAX_IDENTIFIER_CHARS
        else workspace_id()
    )
    raw_name = raw_workspace.get("name")
    name = (
        raw_name.strip()[:MAX_WORKSPACE_NAME_CHARS]
        if isinstance(raw_name, str) and raw_name.strip()
        else f"{DEFAULT_WORKSPACE_NAME_PREFIX} {index}"
    )
    raw_documents = raw_workspace.get("documents")
    documents = _restore_documents(
        raw_documents if isinstance(raw_documents, list) else (),
        missing_paths,
        schema_version,
    )
    selected_document_id = _restored_selected_document_id(
        raw_workspace.get("selected_document_id"),
        documents,
        schema_version,
    )
    return WorkspaceInfo(
        workspace_id=restored_id,
        name=name,
        documents=documents,
        selected_document_id=selected_document_id,
    )


def _restore_documents(
    raw_documents: Iterable[Any],
    missing_paths: list[Path],
    schema_version: int,
) -> tuple[WorkspaceDocument, ...]:
    documents: list[WorkspaceDocument] = []
    seen: set[Path] = set()
    for raw_document in raw_documents:
        if len(documents) >= MAX_DOCUMENTS_PER_WORKSPACE:
            break
        raw_id: object = None
        if schema_version == LEGACY_SCHEMA_VERSION:
            raw_path = raw_document
        elif isinstance(raw_document, dict):
            raw_id = raw_document.get("document_id")
            raw_path = raw_document.get("path")
        else:
            continue
        if not isinstance(raw_path, str) or not raw_path.strip() or len(raw_path) > MAX_PATH_CHARS:
            continue
        candidate = Path(raw_path)
        if candidate.suffix.lower() != ".pdf" or not candidate.exists() or not candidate.is_file():
            missing_paths.append(candidate)
            continue
        try:
            resolved = candidate.resolve(strict=True)
        except OSError:
            missing_paths.append(candidate)
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        restored_document_id = (
            raw_id.strip()
            if isinstance(raw_id, str) and _is_uuid(raw_id.strip())
            else new_document_id()
        )
        documents.append(
            WorkspaceDocument(
                document_id=restored_document_id,
                path=candidate,
                resolved_path=resolved,
            )
        )
    return tuple(documents)


def _restored_selected_document_id(
    raw_selected_document_id: object,
    documents: tuple[WorkspaceDocument, ...],
    schema_version: int,
) -> str | None:
    if isinstance(raw_selected_document_id, str):
        if schema_version == LEGACY_SCHEMA_VERSION:
            for document in documents:
                if _legacy_document_id_for_path(document.resolved_path) == raw_selected_document_id:
                    return document.document_id
        else:
            document_ids = {document.document_id for document in documents}
            if raw_selected_document_id in document_ids:
                return raw_selected_document_id
    return documents[0].document_id if documents else None


def _legacy_document_id_for_path(path: Path) -> str:
    return str(uuid5(NAMESPACE_URL, Path(path).resolve(strict=False).as_uri()))


def _safe_identifier(value: str, fallback: str) -> str:
    cleaned = value.strip()
    return cleaned if 0 < len(cleaned) <= MAX_IDENTIFIER_CHARS else fallback


def _is_uuid(value: str) -> bool:
    if len(value) > MAX_IDENTIFIER_CHARS:
        return False
    try:
        UUID(value)
    except (ValueError, AttributeError):
        return False
    return True


def _encode_payload(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
