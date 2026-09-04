from __future__ import annotations

import pytest

from pdfmod.domain.jobs import OperationType
from pdfmod.ui import i18n
from pdfmod.ui.components.tool_icons import TOOL_ICON_BY_ID, tool_icon_signature
from pdfmod.ui.dashboard import (
    _available_dashboard_specs,
    _document_summary_text,
    _pending_dashboard_groups,
    _planned_dashboard_groups,
    _ready_action_keys,
    _ready_available_action_keys,
    _ready_primary_action_key,
    _ready_secondary_action_keys,
)
from pdfmod.ui.tool_specs import (
    TOOL_SPECS,
    TOOL_SPECS_BY_KEY,
    TOOL_SPECS_BY_OPERATION,
    ToolSpec,
    tool_spec_for_operation,
)
from pdfmod.ui.workspace_state import WorkspaceDocument

VISIBLE_CATEGORIES = {
    "base",
    "organize",
    "optimize",
    "convert_to_pdf",
    "convert_from_pdf",
    "edit",
    "security",
}
INPUT_KINDS = {"none", "pdf_single", "pdf_multiple", "images", "folder"}


def test_page_operation_specs_define_expected_modes() -> None:
    split = tool_spec_for_operation(OperationType.SPLIT_BY_RANGES)
    reorder = tool_spec_for_operation(OperationType.REORDER_PAGES)
    rotate = tool_spec_for_operation(OperationType.ROTATE_PAGES)
    extract = tool_spec_for_operation(OperationType.EXTRACT_PAGES)
    remove = tool_spec_for_operation(OperationType.REMOVE_PAGES)
    insert = tool_spec_for_operation(OperationType.INSERT_PDF_PAGES)

    assert split.output_mode == "directory"
    assert split.input_mode == "range_groups"
    assert split.output_label_key == "output.none_dir"

    assert reorder.input_mode == "complete_order"
    assert reorder.ranges_label_key == "label.page_order"
    assert reorder.page_range_placeholder == "3,1,2,4-6"
    assert reorder.help_key == "page.reorder.help"

    assert rotate.requires_rotation_angle
    assert extract.default_output_suffix == "_extrait"
    assert remove.default_output_suffix == "_sans-pages"
    assert insert.input_kind == "pdf_multiple"
    assert insert.allows_multiple_inputs


def test_merge_spec_uses_canonical_operation_type_only() -> None:
    merge = tool_spec_for_operation(OperationType.MERGE_PDFS)

    assert merge.operation is OperationType.MERGE_PDFS
    assert merge.allows_multiple_inputs
    assert not hasattr(OperationType, "MERGE_PDF")


def test_tool_specs_are_unique_ordered_and_route_addressable() -> None:
    keys = [spec.key for spec in TOOL_SPECS]
    routes = [spec.route_key for spec in TOOL_SPECS]
    orders = [spec.order for spec in TOOL_SPECS]

    assert len(keys) == len(set(keys))
    assert len(routes) == len(set(routes))
    assert orders == sorted(orders)
    assert TOOL_SPECS_BY_KEY["view"].view_kind == "viewer"
    assert TOOL_SPECS_BY_KEY["view"].input_kind == "pdf_single"


def test_pending_specs_do_not_define_pdf_operations() -> None:
    pending = [spec for spec in TOOL_SPECS if spec.status == "pending"]

    pending_keys = {spec.key for spec in pending}
    assert "compress" in pending_keys
    assert "ocr_pdf" in pending_keys
    assert "sign_pdf" in pending_keys
    assert "summarize_pdf_ai" in pending_keys
    assert "searchable_scan" in pending_keys
    assert "visual_signature" in pending_keys
    assert all(spec.operation is None for spec in pending)
    assert all(spec.view_kind == "pending" for spec in pending)
    assert all(not spec.available for spec in pending)


def test_dashboard_catalog_is_limited_to_ilovepdf_categories() -> None:
    available = [spec for spec in TOOL_SPECS if spec.status == "available"]
    pending_dashboard = [
        spec for spec in TOOL_SPECS if spec.dashboard_visibility == "pending_dashboard"
    ]
    roadmap_only = [spec for spec in TOOL_SPECS if spec.dashboard_visibility == "roadmap_only"]
    hidden = [spec for spec in TOOL_SPECS if spec.dashboard_visibility == "hidden"]

    assert {spec.key for spec in available} == {
        "view",
        "merge",
        "split",
        "extract",
        "remove",
        "rotate",
        "reorder",
        "insert",
        "blank_page",
    }
    assert all(spec.dashboard_visibility == "primary" for spec in available)
    assert {spec.key for spec in pending_dashboard} == {
        "scan_to_pdf",
        "compress",
        "repair_pdf",
        "ocr_pdf",
        "jpg_to_pdf",
        "word_to_pdf",
        "powerpoint_to_pdf",
        "excel_to_pdf",
        "html_to_pdf",
        "pdf_to_jpg",
        "pdf_to_word",
        "pdf_to_powerpoint",
        "pdf_to_excel",
        "pdf_to_pdfa",
        "page_numbers",
        "watermark",
        "crop",
        "edit_pdf",
        "pdf_forms",
        "unlock_pdf",
        "protect",
        "sign_pdf",
        "redact_pdf",
        "compare_pdf",
    }
    assert {spec.key for spec in roadmap_only} == {
        "summarize_pdf_ai",
        "translate_pdf_ai",
        "create_from_pages",
    }
    assert {"batch_operations", "text_to_pdf", "searchable_scan"}.issubset(
        {spec.key for spec in hidden}
    )
    assert all(spec.status == "pending" for spec in pending_dashboard + roadmap_only + hidden)
    assert all(spec.dashboard_group for spec in TOOL_SPECS)


def test_ocr_and_signature_wording_avoid_duplicate_or_legal_promise() -> None:
    assert TOOL_SPECS_BY_KEY["ocr_pdf"].dashboard_visibility == "pending_dashboard"
    assert TOOL_SPECS_BY_KEY["searchable_scan"].dashboard_visibility == "hidden"

    sign = TOOL_SPECS_BY_KEY["sign_pdf"]
    assert sign.dashboard_visibility == "pending_dashboard"
    assert "signature électronique" in i18n.tr(sign.description_key, "fr")
    assert TOOL_SPECS_BY_KEY["visual_signature"].dashboard_visibility == "hidden"
    assert TOOL_SPECS_BY_KEY["digital_signature"].dashboard_visibility == "hidden"


def test_dashboard_helpers_exclude_hidden_and_roadmap_only_tools() -> None:
    available_keys = {spec.key for spec in _available_dashboard_specs()}
    pending_keys = {spec.key for _group, specs in _pending_dashboard_groups() for spec in specs}

    assert available_keys == {
        "view",
        "merge",
        "split",
        "extract",
        "remove",
        "rotate",
        "reorder",
        "insert",
        "blank_page",
    }
    assert "summarize_pdf_ai" not in pending_keys
    assert "translate_pdf_ai" not in pending_keys
    assert "searchable_scan" not in pending_keys
    assert "batch_operations" not in pending_keys
    assert _planned_dashboard_groups() == _pending_dashboard_groups()


def test_compose_pdf_is_a_later_non_executable_planned_item() -> None:
    compose = TOOL_SPECS_BY_KEY["create_from_pages"]

    assert compose.status == "pending"
    assert compose.dashboard_visibility == "roadmap_only"
    assert compose.roadmap_stage == "later"
    assert compose.operation is None
    assert compose.view_kind == "pending"
    assert i18n.tr(compose.title_key, "fr") == "COMPOSER UN PDF"
    assert i18n.tr(compose.title_key, "en") == "COMPOSE A PDF"
    assert "Composer un PDF" in i18n.tr(
        "dashboard.planned.item",
        "fr",
        title="Composer un PDF",
        stage="plus tard",
        description="Description",
    )


def test_dashboard_ready_actions_are_contextual_and_available_only() -> None:
    assert _ready_primary_action_key(1) == "view"
    assert _ready_secondary_action_keys(1) == ("extract", "remove", "rotate", "reorder")
    assert _ready_action_keys(1) == ("view", "extract", "remove", "rotate", "reorder")
    assert _ready_available_action_keys(1) == ("view", "extract", "remove", "rotate", "reorder")
    assert "add_files" not in _ready_action_keys(1)

    assert _ready_primary_action_key(2) == "merge"
    assert _ready_secondary_action_keys(2) == ("insert", "view")
    assert _ready_action_keys(2) == ("merge", "insert", "view")
    assert _ready_available_action_keys(2) == ("merge", "insert", "view")

    assert "reorder" not in _ready_action_keys(2)
    assert "add_files" not in _ready_action_keys(2)
    assert all(TOOL_SPECS_BY_KEY[key].available for key in _ready_available_action_keys(2))
    assert not any(
        TOOL_SPECS_BY_KEY[key].status == "pending" for key in _ready_available_action_keys(1)
    )


def test_dashboard_ready_file_summary_marks_selection_and_known_pages(tmp_path) -> None:
    path = tmp_path / "contrat.pdf"
    document = WorkspaceDocument(
        document_id="doc-1",
        path=path,
        resolved_path=path,
        page_count=3,
        page_count_status="ready",
    )

    assert _document_summary_text(document, True, "fr") == "contrat.pdf - sélectionné - 3 pages"
    assert _document_summary_text(document, False, "en") == "contrat.pdf - 3 pages"

    unknown_pages = WorkspaceDocument(
        document_id="doc-2",
        path=tmp_path / "annexe.pdf",
        resolved_path=tmp_path / "annexe.pdf",
    )
    assert _document_summary_text(unknown_pages, False, "fr") == "annexe.pdf"


def test_dashboard_ready_i18n_labels_exist_in_fr_and_en() -> None:
    keys = {
        "dashboard.ready.single_title",
        "dashboard.ready.multi_title",
        "dashboard.ready.help",
        "dashboard.ready.privacy",
        "dashboard.ready.file_selection",
        "dashboard.ready.recommended_action",
        "dashboard.ready.other_actions",
        "dashboard.ready.other_actions_single",
        "dashboard.ready.other_actions_multi",
        "dashboard.ready.view_selected",
        "dashboard.ready.view_selected.tooltip",
        "dashboard.ready.selected_file",
        "dashboard.ready.page_count_one",
        "dashboard.ready.page_count_many",
        "dashboard.ready.remove_file",
        "dashboard.ready.remove_file.tooltip",
        "dashboard.ready.add_files",
        "dashboard.ready.add_files.tooltip",
        "dashboard.open_files",
        "dashboard.open_files.tooltip",
        "dashboard.search.placeholder",
        "dashboard.search.accessible",
        "dashboard.catalog.show",
        "dashboard.catalog.show.tooltip",
        "dashboard.catalog.hide",
        "dashboard.catalog.hide.tooltip",
        "dashboard.planned.show",
        "dashboard.planned.show.tooltip",
        "dashboard.planned.hide",
        "dashboard.planned.hide.tooltip",
        "dashboard.planned.intro",
        "dashboard.planned.stage.planned",
        "dashboard.planned.stage.later",
    }

    for locale in ("fr", "en"):
        for key in keys:
            assert i18n.tr(key, locale, count=2) != key


def test_tool_specs_have_translated_titles_and_descriptions() -> None:
    for spec in TOOL_SPECS:
        assert i18n.tr(spec.title_key, "en") != spec.title_key
        assert i18n.tr(spec.description_key, "en") != spec.description_key
        assert i18n.tr(spec.title_key, "fr") != spec.title_key
        assert i18n.tr(spec.description_key, "fr") != spec.description_key


def test_available_tool_specs_have_executable_routes_and_input_contracts() -> None:
    available = [spec for spec in TOOL_SPECS if spec.status == "available"]

    for spec in available:
        assert spec.available
        assert TOOL_SPECS_BY_KEY[spec.route_key] is spec
        assert spec.category in VISIBLE_CATEGORIES
        assert spec.input_kind in INPUT_KINDS
        assert spec.dashboard_visibility == "primary"
        if spec.view_kind == "viewer":
            assert spec.operation is None
            assert spec.route_key == "view"
        else:
            assert spec.view_kind == "operation"
            assert spec.operation in TOOL_SPECS_BY_OPERATION
            assert tool_spec_for_operation(spec.operation) is spec
            assert spec.action_button_key


def test_available_operation_types_are_all_exposed_once() -> None:
    expected_operations = {
        OperationType.MERGE_PDFS,
        OperationType.EXTRACT_PAGES,
        OperationType.REMOVE_PAGES,
        OperationType.SPLIT_BY_RANGES,
        OperationType.ROTATE_PAGES,
        OperationType.REORDER_PAGES,
        OperationType.INSERT_PDF_PAGES,
        OperationType.INSERT_BLANK_PAGE,
    }

    assert set(TOOL_SPECS_BY_OPERATION) == expected_operations
    assert {
        spec.operation for spec in TOOL_SPECS if spec.status == "available" and spec.operation
    } == expected_operations


def test_tool_spec_rejects_incoherent_operation_contracts() -> None:
    with pytest.raises(ValueError, match="operation route"):
        ToolSpec(
            key="merge",
            title_key="tool.merge.title",
            description_key="tool.merge.description",
            category="organize",
            status="available",
            view_kind="operation",
            route_key="extract",
            input_kind="pdf_multiple",
            order=1,
            icon="merge_pages",
            role="primary",
            operation=OperationType.MERGE_PDFS,
            action_button_key="button.merge",
        )

    with pytest.raises(ValueError, match="pending tools must not declare"):
        ToolSpec(
            key="compress",
            title_key="tool.compress.title",
            description_key="tool.compress.description",
            category="optimize",
            status="pending",
            view_kind="pending",
            route_key="compress",
            input_kind="pdf_single",
            order=2,
            icon="compress_inward",
            role="info",
            operation=OperationType.MERGE_PDFS,
            dashboard_visibility="pending_dashboard",
        )


def test_visible_pending_tools_remain_non_executable_with_coherent_badges() -> None:
    visible_pending = [
        spec
        for spec in TOOL_SPECS
        if spec.status == "pending" and spec.dashboard_visibility != "hidden"
    ]

    assert visible_pending
    for spec in visible_pending:
        assert spec.operation is None
        assert spec.view_kind == "pending"
        assert spec.category in VISIBLE_CATEGORIES | {"intelligence"}
        assert not spec.available
        assert i18n.tr("pending.badge", "fr") == "EN ATTENTE"
        assert i18n.tr("pending.badge", "en") == "COMING SOON"


def test_visible_conversion_labels_use_extensions_not_office_brands() -> None:
    forbidden_terms = ("Word", "Excel", "PowerPoint")
    expected_fragments = (
        "DOC/DOCX/ODT",
        "XLS/XLSX/ODS",
        "PPT/PPTX/ODP",
        "PDF TO DOCX/ODT",
        "PDF TO XLSX/ODS",
        "PDF TO PPTX/ODP",
    )
    visible_specs = [
        spec for spec in TOOL_SPECS if spec.dashboard_visibility in {"primary", "pending_dashboard"}
    ]
    visible_text = "\n".join(
        "\n".join(
            (
                i18n.tr(spec.title_key, "en"),
                i18n.tr(spec.description_key, "en"),
                i18n.tr(spec.title_key, "fr"),
                i18n.tr(spec.description_key, "fr"),
            )
        )
        for spec in visible_specs
    )

    assert not any(term in visible_text for term in forbidden_terms)
    for fragment in expected_fragments:
        assert fragment in visible_text


def test_visible_tool_icons_are_dedicated_by_tool_id_and_shape() -> None:
    visible_specs = [
        spec for spec in TOOL_SPECS if spec.dashboard_visibility in {"primary", "pending_dashboard"}
    ]
    signatures = [tool_icon_signature(spec.icon) for spec in visible_specs]

    assert all(spec.key in TOOL_ICON_BY_ID for spec in visible_specs)
    assert all(spec.icon == TOOL_ICON_BY_ID[spec.key] for spec in visible_specs)
    assert len(signatures) == len(set(signatures))
