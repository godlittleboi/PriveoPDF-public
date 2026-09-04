from __future__ import annotations

from pathlib import Path

from pdfmod.ui.workspace_state import MAX_WORKSPACES, WorkspaceState


def test_workspace_adds_pdfs_once_and_selects_first(tmp_path: Path) -> None:
    first = tmp_path / "first.pdf"
    second = tmp_path / "second.pdf"
    text = tmp_path / "notes.txt"
    first.write_bytes(b"%PDF-1.4\n")
    second.write_bytes(b"%PDF-1.4\n")
    text.write_text("not a pdf", encoding="utf-8")

    state = WorkspaceState()
    added = state.add_documents([first, second, first, text])

    assert [document.path for document in added] == [first, second]
    assert [document.path for document in state.documents()] == [first, second]
    selected = state.selected_document()
    assert selected is not None
    assert selected.path == first


def test_workspace_tracks_selection_and_page_count(tmp_path: Path) -> None:
    first = tmp_path / "first.pdf"
    second = tmp_path / "second.pdf"
    first.write_bytes(b"%PDF-1.4\n")
    second.write_bytes(b"%PDF-1.4\n")

    state = WorkspaceState()
    state.add_documents([first, second])
    second_document = state.documents()[1]

    assert state.select_document(second_document.document_id)
    state.set_page_count_status(second_document.document_id, 12, "ready")

    selected = state.selected_document()
    assert selected is not None
    assert selected.path == second
    assert selected.page_count == 12
    assert selected.page_count_status == "ready"


def test_workspace_state_creates_independent_workspaces(tmp_path: Path) -> None:
    first = tmp_path / "first.pdf"
    second = tmp_path / "second.pdf"
    first.write_bytes(b"%PDF-1.4\n")
    second.write_bytes(b"%PDF-1.4\n")

    state = WorkspaceState()
    first_workspace_id = state.active_workspace_id()
    state.add_documents([first])

    second_workspace = state.add_workspace()
    assert second_workspace is not None
    state.add_documents([second])

    assert [workspace.name for workspace in state.workspaces()] == ["Session 1", "Session 2"]
    assert state.active_workspace_id() == second_workspace.workspace_id
    assert [document.path for document in state.documents()] == [second]

    assert state.select_workspace(first_workspace_id)
    assert [document.path for document in state.documents()] == [first]


def test_workspace_state_renames_workspace_without_changing_id() -> None:
    state = WorkspaceState()
    workspace_id = state.active_workspace_id()

    assert state.rename_workspace(workspace_id, "Client files")

    workspace = state.active_workspace()
    assert workspace.workspace_id == workspace_id
    assert workspace.name == "Client files"


def test_workspace_state_refuses_empty_rename_by_keeping_current_name() -> None:
    state = WorkspaceState()
    workspace_id = state.active_workspace_id()

    assert state.rename_workspace(workspace_id, "")

    assert state.active_workspace().name == "Session 1"


def test_workspace_state_removes_workspace_without_deleting_files(tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.4\n")

    state = WorkspaceState()
    first_workspace_id = state.active_workspace_id()
    state.add_documents([source])
    second_workspace = state.add_workspace()
    assert second_workspace is not None

    removed = state.remove_workspace(first_workspace_id)

    assert removed is not None
    assert removed.workspace_id == first_workspace_id
    assert source.exists()
    assert state.workspaces() == (second_workspace,)
    assert state.active_workspace_id() == second_workspace.workspace_id


def test_workspace_state_refuses_to_remove_last_workspace() -> None:
    state = WorkspaceState()

    assert state.remove_workspace(state.active_workspace_id()) is None
    assert len(state.workspaces()) == 1


def test_workspace_remove_document_keeps_disk_file_and_selects_next(tmp_path: Path) -> None:
    first = tmp_path / "first.pdf"
    second = tmp_path / "second.pdf"
    first.write_bytes(b"%PDF-1.4\n")
    second.write_bytes(b"%PDF-1.4\n")

    state = WorkspaceState()
    state.add_documents([first, second])
    first_document, second_document = state.documents()

    removed = state.remove_document(first_document.document_id)

    assert removed == first_document
    assert first.exists()
    assert [document.path for document in state.documents()] == [second]
    assert state.selected_document() == second_document


def test_same_pdf_can_exist_in_multiple_workspaces(tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.4\n")

    state = WorkspaceState()
    first_workspace_id = state.active_workspace_id()
    state.add_documents([source])

    state.add_workspace()
    added = state.add_documents([source])

    assert len(added) == 1
    assert state.documents()[0].path == source
    assert state.select_workspace(first_workspace_id)
    assert state.documents()[0].path == source


def test_page_count_status_can_update_inactive_workspace(tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"
    other = tmp_path / "other.pdf"
    source.write_bytes(b"%PDF-1.4\n")
    other.write_bytes(b"%PDF-1.4\n")

    state = WorkspaceState()
    first_workspace_id = state.active_workspace_id()
    state.add_documents([source])
    source_document = state.documents()[0]
    state.add_workspace()
    state.add_documents([other])

    document = state.document_by_path(source)
    assert document == source_document
    assert document is not None
    state.set_page_count_status(document.document_id, 7, "ready")

    assert state.select_workspace(first_workspace_id)
    assert state.documents()[0].page_count == 7


def test_workspace_state_limits_workspaces_to_five() -> None:
    state = WorkspaceState()

    for _ in range(MAX_WORKSPACES - 1):
        assert state.add_workspace() is not None

    assert len(state.workspaces()) == MAX_WORKSPACES
    assert not state.can_add_workspace()
    assert state.add_workspace() is None
    assert len(state.workspaces()) == MAX_WORKSPACES


def test_persistence_revision_tracks_only_session_changes(tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.4\n")
    state = WorkspaceState()

    assert state.persistence_revision() == 0
    added = state.add_documents((source,))
    assert state.persistence_revision() == 1

    document = added[0]
    state.set_page_count_status(document.document_id, 7, "ready")
    assert state.persistence_revision() == 1

    assert state.select_document(document.document_id)
    assert state.persistence_revision() == 1
    assert state.rename_workspace(state.active_workspace_id(), "Renamed")
    assert state.persistence_revision() == 2
