from __future__ import annotations

from priveopdf.ui.main_window import workspace_compatible_tool_specs


def test_workspace_tools_hide_pending_and_require_enough_pdfs_for_merge() -> None:
    no_document = workspace_compatible_tool_specs(0)
    one_document = workspace_compatible_tool_specs(1)
    two_documents = workspace_compatible_tool_specs(2)

    assert no_document == ()
    assert {spec.key for spec in one_document} == {
        "view",
        "split",
        "extract",
        "remove",
        "rotate",
        "reorder",
        "blank_page",
        "compress",
        "ocr_pdf",
        "protect",
        "unlock_pdf",
        "share_check",
        "redact_pdf",
        "watermark",
    }
    assert {spec.key for spec in two_documents} == {
        "view",
        "merge",
        "insert",
        "split",
        "extract",
        "remove",
        "rotate",
        "reorder",
        "blank_page",
        "compress",
        "ocr_pdf",
        "protect",
        "unlock_pdf",
        "share_check",
        "redact_pdf",
        "watermark",
    }
    assert all(spec.status == "available" for spec in two_documents)
