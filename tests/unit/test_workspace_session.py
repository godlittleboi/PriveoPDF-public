from __future__ import annotations

import json
from pathlib import Path

from pdfmod.app.workspace_session import (
    MAX_SESSION_PAYLOAD_BYTES,
    restore_workspace_session,
    serialize_workspace_session,
)
from pdfmod.ui.workspace_state import MAX_DOCUMENTS_PER_WORKSPACE, WorkspaceState


def _write_pdf(path: Path, content: bytes = b"%PDF-1.4\n") -> Path:
    path.write_bytes(content)
    return path


def test_workspace_session_roundtrip_restores_metadata_without_pdf_bytes(tmp_path: Path) -> None:
    source = _write_pdf(tmp_path / "source.pdf", b"%PDF-1.4\nprivate bytes\n")
    state = WorkspaceState()
    document = state.add_documents([source])[0]
    assert state.rename_workspace(state.active_workspace_id(), "Client")

    payload = serialize_workspace_session(
        state.workspaces(),
        state.active_workspace_id(),
        remember_open_documents=True,
    )
    decoded = json.loads(payload)

    assert decoded["schema_version"] == 2
    assert decoded["workspaces"][0]["name"] == "Client"
    assert decoded["workspaces"][0]["documents"] == [
        {"document_id": document.document_id, "path": str(source)}
    ]
    assert "private bytes" not in payload

    restored = restore_workspace_session(payload)

    assert restored.missing_paths == ()
    assert restored.workspace_state is not None
    assert restored.workspace_state.active_workspace().name == "Client"
    assert restored.workspace_state.selected_document() is not None
    assert restored.workspace_state.selected_document().document_id == document.document_id
    assert restored.workspace_state.selected_document().path == source


def test_workspace_session_payload_is_limited_to_local_paths_names_and_selection(
    tmp_path: Path,
) -> None:
    source = _write_pdf(tmp_path / "source.pdf", b"%PDF-1.4\nprivate bytes\n")
    state = WorkspaceState()
    document = state.add_documents([source])[0]
    assert state.rename_workspace(state.active_workspace_id(), "Client")

    payload = serialize_workspace_session(
        state.workspaces(), state.active_workspace_id(), remember_open_documents=True
    )
    decoded = json.loads(payload)

    assert set(decoded) == {"schema_version", "active_workspace_id", "workspaces"}
    assert set(decoded["workspaces"][0]) == {
        "workspace_id",
        "name",
        "selected_document_id",
        "documents",
    }
    assert decoded["workspaces"][0]["name"] == "Client"
    assert decoded["workspaces"][0]["selected_document_id"] == document.document_id
    assert decoded["workspaces"][0]["documents"] == [
        {"document_id": document.document_id, "path": str(source)}
    ]
    assert "private bytes" not in payload
    assert "page_count" not in payload
    assert "thumbnail" not in payload
    assert "password" not in payload
    assert "temporary" not in payload


def test_workspace_session_ignores_missing_files_and_keeps_session_name(
    tmp_path: Path,
) -> None:
    existing = _write_pdf(tmp_path / "existing.pdf")
    missing = tmp_path / "missing.pdf"
    payload = json.dumps(
        {
            "schema_version": 1,
            "active_workspace_id": "session-a",
            "saved_at": 123.0,
            "workspaces": [
                {
                    "workspace_id": "session-a",
                    "name": "Session locale",
                    "selected_document_id": "missing-document",
                    "documents": [str(missing), str(existing)],
                }
            ],
        }
    )

    restored = restore_workspace_session(payload)

    assert restored.workspace_state is not None
    assert restored.missing_paths == (missing,)
    assert restored.workspace_state.active_workspace().name == "Session locale"
    assert [document.path for document in restored.workspace_state.documents()] == [existing]
    assert restored.workspace_state.selected_document() is not None
    assert restored.workspace_state.selected_document().path == existing


def test_workspace_session_does_not_restore_removed_session(tmp_path: Path) -> None:
    first = _write_pdf(tmp_path / "first.pdf")
    second = _write_pdf(tmp_path / "second.pdf")
    state = WorkspaceState()
    removed_workspace_id = state.active_workspace_id()
    state.add_documents([first])
    second_workspace = state.add_workspace()
    assert second_workspace is not None
    state.add_documents([second])

    removed = state.remove_workspace(removed_workspace_id)
    assert removed is not None
    payload = serialize_workspace_session(
        state.workspaces(), state.active_workspace_id(), remember_open_documents=True
    )

    restored = restore_workspace_session(payload)

    assert restored.workspace_state is not None
    assert [workspace.workspace_id for workspace in restored.workspace_state.workspaces()] == [
        second_workspace.workspace_id
    ]
    assert restored.workspace_state.selected_document() is not None
    assert restored.workspace_state.selected_document().path == second


def test_workspace_session_rejects_invalid_json() -> None:
    restored = restore_workspace_session("{broken")

    assert restored.workspace_state is None
    assert restored.missing_paths == ()


def test_workspace_session_serialization_is_empty_without_remember_consent(
    tmp_path: Path,
) -> None:
    source = _write_pdf(tmp_path / "medical.pdf")
    state = WorkspaceState()
    state.add_documents([source])

    payload = serialize_workspace_session(
        state.workspaces(),
        state.active_workspace_id(),
    )

    assert payload == ""
    assert str(source) not in payload


def test_schema_v1_is_migrated_to_random_document_identifier(tmp_path: Path) -> None:
    source = _write_pdf(tmp_path / "legacy.pdf")
    legacy_payload = json.dumps(
        {
            "schema_version": 1,
            "active_workspace_id": "session-a",
            "workspaces": [
                {
                    "workspace_id": "session-a",
                    "name": "Legacy",
                    "selected_document_id": "not-a-current-id",
                    "documents": [str(source)],
                }
            ],
        }
    )

    first = restore_workspace_session(legacy_payload)
    second = restore_workspace_session(legacy_payload)

    assert first.migrated_from_version == 1
    assert first.workspace_state is not None
    assert second.workspace_state is not None
    first_id = first.workspace_state.documents()[0].document_id
    second_id = second.workspace_state.documents()[0].document_id
    assert first_id != second_id
    assert str(source) not in first_id


def test_workspace_session_limits_payload_and_document_count(tmp_path: Path) -> None:
    state = WorkspaceState()
    paths = [
        _write_pdf(tmp_path / f"document-{index}.pdf")
        for index in range(MAX_DOCUMENTS_PER_WORKSPACE + 5)
    ]
    state.add_documents(paths)

    payload = serialize_workspace_session(
        state.workspaces(), state.active_workspace_id(), remember_open_documents=True
    )
    decoded = json.loads(payload)

    assert len(payload.encode("utf-8")) <= MAX_SESSION_PAYLOAD_BYTES
    assert len(decoded["workspaces"][0]["documents"]) == MAX_DOCUMENTS_PER_WORKSPACE


def test_workspace_session_rejects_oversized_payload() -> None:
    payload = " " * (MAX_SESSION_PAYLOAD_BYTES + 1)

    restored = restore_workspace_session(payload)

    assert restored.workspace_state is None
