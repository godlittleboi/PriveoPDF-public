from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal, NotRequired, TypedDict, Unpack

from pdfmod.domain.jobs import OperationType

OutputMode = Literal["file", "directory"]
PageInputMode = Literal["ranges", "range_groups", "complete_order"]
ToolCategory = Literal[
    "base",
    "organize",
    "optimize",
    "convert_to_pdf",
    "convert_from_pdf",
    "edit",
    "security",
    "intelligence",
    "hidden",
]
ToolInputKind = Literal["none", "pdf_single", "pdf_multiple", "images", "folder"]
ToolRole = Literal["primary", "info", "warning", "danger", "success"]
ToolStatus = Literal["available", "pending"]
ToolViewKind = Literal["viewer", "operation", "pending"]
DashboardVisibility = Literal["primary", "pending_dashboard", "roadmap_only", "hidden"]
RoadmapStage = Literal["mvp", "planned", "later", "hidden"]

_OPERATION_ROUTE_BY_OPERATION: Final[dict[OperationType, str]] = {
    OperationType.MERGE_PDFS: "merge",
    OperationType.EXTRACT_PAGES: "extract",
    OperationType.REMOVE_PAGES: "remove",
    OperationType.SPLIT_BY_RANGES: "split",
    OperationType.ROTATE_PAGES: "rotate",
    OperationType.REORDER_PAGES: "reorder",
    OperationType.INSERT_PDF_PAGES: "insert",
    OperationType.INSERT_BLANK_PAGE: "blank_page",
}

_OUTPUT_MODES: Final[frozenset[str]] = frozenset(("file", "directory"))
_PAGE_INPUT_MODES: Final[frozenset[str]] = frozenset(("ranges", "range_groups", "complete_order"))
_TOOL_CATEGORIES: Final[frozenset[str]] = frozenset(
    (
        "base",
        "organize",
        "optimize",
        "convert_to_pdf",
        "convert_from_pdf",
        "edit",
        "security",
        "intelligence",
        "hidden",
    )
)
_TOOL_INPUT_KINDS: Final[frozenset[str]] = frozenset(
    ("none", "pdf_single", "pdf_multiple", "images", "folder")
)
_TOOL_ROLES: Final[frozenset[str]] = frozenset(("primary", "info", "warning", "danger", "success"))
_TOOL_STATUSES: Final[frozenset[str]] = frozenset(("available", "pending"))
_TOOL_VIEW_KINDS: Final[frozenset[str]] = frozenset(("viewer", "operation", "pending"))
_DASHBOARD_VISIBILITIES: Final[frozenset[str]] = frozenset(
    ("primary", "pending_dashboard", "roadmap_only", "hidden")
)
_ROADMAP_STAGES: Final[frozenset[str]] = frozenset(("mvp", "planned", "later", "hidden"))


@dataclass(frozen=True)
class ToolSpec:
    key: str
    title_key: str
    description_key: str
    category: ToolCategory
    status: ToolStatus
    view_kind: ToolViewKind
    route_key: str
    input_kind: ToolInputKind
    order: int
    icon: str
    role: ToolRole
    operation: OperationType | None = None
    dashboard_group: str = "dashboard.group.organize_pdf"
    dashboard_visibility: DashboardVisibility = "primary"
    roadmap_stage: RoadmapStage = "mvp"
    input_mode: PageInputMode = "ranges"
    output_mode: OutputMode = "file"
    output_label_key: str = "output.none_file"
    output_button_key: str = "button.choose_output"
    action_button_key: str = ""
    ranges_label_key: str = "label.page_ranges"
    page_range_placeholder: str = "1-3,5,8-10"
    help_key: str = ""
    requires_page_range: bool = True
    allows_multiple_inputs: bool = False
    requires_rotation_angle: bool = False
    default_output_suffix: str = ""
    success_title: str = ""
    progress_message: str = ""

    def __post_init__(self) -> None:
        _require_non_empty_string(self.key, "key")
        _require_non_empty_string(self.title_key, "title_key")
        _require_non_empty_string(self.description_key, "description_key")
        _require_non_empty_string(self.route_key, "route_key")
        _require_non_empty_string(self.icon, "icon")
        _require_non_empty_string(self.dashboard_group, "dashboard_group")
        _require_non_empty_string(self.output_label_key, "output_label_key")
        _require_non_empty_string(self.output_button_key, "output_button_key")
        _require_non_empty_string(self.ranges_label_key, "ranges_label_key")
        _require_non_empty_string(self.page_range_placeholder, "page_range_placeholder")
        _require_literal(self.category, _TOOL_CATEGORIES, "category")
        _require_literal(self.status, _TOOL_STATUSES, "status")
        _require_literal(self.view_kind, _TOOL_VIEW_KINDS, "view_kind")
        _require_literal(self.input_kind, _TOOL_INPUT_KINDS, "input_kind")
        _require_literal(self.role, _TOOL_ROLES, "role")
        _require_literal(self.dashboard_visibility, _DASHBOARD_VISIBILITIES, "dashboard_visibility")
        _require_literal(self.roadmap_stage, _ROADMAP_STAGES, "roadmap_stage")
        _require_literal(self.input_mode, _PAGE_INPUT_MODES, "input_mode")
        _require_literal(self.output_mode, _OUTPUT_MODES, "output_mode")
        if not isinstance(self.order, int) or isinstance(self.order, bool) or self.order < 0:
            raise ValueError("order must be a positive or zero integer")
        for field_name in (
            "requires_page_range",
            "allows_multiple_inputs",
            "requires_rotation_angle",
        ):
            if not isinstance(getattr(self, field_name), bool):
                raise TypeError(f"{field_name} must be a bool")
        if self.operation is not None and not isinstance(self.operation, OperationType):
            raise TypeError("operation must be an OperationType or None")
        if self.status == "pending":
            if self.view_kind != "pending":
                raise ValueError("pending tools must use the pending view")
            if self.operation is not None:
                raise ValueError("pending tools must not declare an operation")
            if self.dashboard_visibility == "primary":
                raise ValueError("pending tools must not be primary dashboard tools")
        if self.view_kind == "viewer":
            if self.status != "available":
                raise ValueError("viewer tools must be available")
            if self.operation is not None:
                raise ValueError("viewer tools must not declare an operation")
        if self.view_kind == "operation":
            if self.status != "available":
                raise ValueError("operation tools must be available")
            if self.operation is None:
                raise ValueError("operation tools must declare an operation")
            expected_route = _OPERATION_ROUTE_BY_OPERATION.get(self.operation)
            if self.route_key != expected_route:
                raise ValueError("operation route must match OperationType")
            _require_non_empty_string(self.action_button_key, "action_button_key")

    @property
    def available(self) -> bool:
        return self.status == "available"


def _require_non_empty_string(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


def _require_literal(value: str, allowed_values: frozenset[str], field_name: str) -> None:
    if value not in allowed_values:
        raise ValueError(f"{field_name} has an unsupported value")


class _OperationToolOptions(TypedDict):
    dashboard_group: NotRequired[str]
    roadmap_stage: NotRequired[RoadmapStage]
    input_mode: NotRequired[PageInputMode]
    output_mode: NotRequired[OutputMode]
    output_label_key: NotRequired[str]
    output_button_key: NotRequired[str]
    action_button_key: NotRequired[str]
    ranges_label_key: NotRequired[str]
    page_range_placeholder: NotRequired[str]
    help_key: NotRequired[str]
    requires_page_range: NotRequired[bool]
    allows_multiple_inputs: NotRequired[bool]
    requires_rotation_angle: NotRequired[bool]
    default_output_suffix: NotRequired[str]
    success_title: NotRequired[str]
    progress_message: NotRequired[str]


def _available_operation_tool(
    key: str,
    title_key: str,
    description_key: str,
    category: ToolCategory,
    route_key: str,
    input_kind: ToolInputKind,
    order: int,
    icon: str,
    role: ToolRole,
    operation: OperationType,
    **kwargs: Unpack[_OperationToolOptions],
) -> ToolSpec:
    return ToolSpec(
        key=key,
        title_key=title_key,
        description_key=description_key,
        category=category,
        status="available",
        view_kind="operation",
        route_key=route_key,
        input_kind=input_kind,
        order=order,
        icon=icon,
        role=role,
        operation=operation,
        dashboard_visibility="primary",
        **kwargs,
    )


def _pending_tool(
    key: str,
    title_key: str,
    description_key: str,
    category: ToolCategory,
    group_key: str,
    input_kind: ToolInputKind,
    order: int,
    icon: str,
    role: ToolRole,
    visibility: DashboardVisibility = "pending_dashboard",
    stage: RoadmapStage = "planned",
) -> ToolSpec:
    return ToolSpec(
        key=key,
        title_key=title_key,
        description_key=description_key,
        category=category,
        status="pending",
        view_kind="pending",
        route_key=key,
        input_kind=input_kind,
        order=order,
        icon=icon,
        role=role,
        dashboard_group=group_key,
        dashboard_visibility=visibility,
        roadmap_stage=stage,
        requires_page_range=False,
    )


def _hidden_tool(key: str, order: int, input_kind: ToolInputKind = "pdf_single") -> ToolSpec:
    return _pending_tool(
        key=key,
        title_key="tool.hidden.title",
        description_key="tool.hidden.description",
        category="hidden",
        group_key="dashboard.group.organize_pdf",
        input_kind=input_kind,
        order=order,
        icon="document",
        role="info",
        visibility="hidden",
        stage="hidden",
    )


TOOL_SPECS: tuple[ToolSpec, ...] = (
    ToolSpec(
        "view",
        "tool.view.title",
        "tool.view.description",
        "base",
        "available",
        "viewer",
        "view",
        "pdf_single",
        10,
        "view_page",
        "primary",
        dashboard_group="dashboard.group.organize_pdf",
    ),
    _available_operation_tool(
        "merge",
        "tool.merge.title",
        "tool.merge.description",
        "organize",
        "merge",
        "pdf_multiple",
        20,
        "merge_pages",
        "primary",
        OperationType.MERGE_PDFS,
        allows_multiple_inputs=True,
        requires_page_range=False,
        action_button_key="button.merge",
        default_output_suffix="_fusionne",
        success_title="Fusion terminee",
        progress_message="Fusion locale...",
    ),
    _available_operation_tool(
        "split",
        "tool.split.title",
        "tool.split.description",
        "organize",
        "split",
        "pdf_single",
        30,
        "split_cut",
        "info",
        OperationType.SPLIT_BY_RANGES,
        input_mode="range_groups",
        output_mode="directory",
        output_label_key="output.none_dir",
        output_button_key="button.choose_folder",
        action_button_key="button.split",
        success_title="Division terminee",
        progress_message="Division locale...",
    ),
    _available_operation_tool(
        "remove",
        "tool.remove.title",
        "tool.remove.description",
        "organize",
        "remove",
        "pdf_single",
        40,
        "remove_cross",
        "danger",
        OperationType.REMOVE_PAGES,
        action_button_key="button.remove_pages",
        default_output_suffix="_sans-pages",
        success_title="Suppression terminee",
        progress_message="Export en cours...",
    ),
    _available_operation_tool(
        "extract",
        "tool.extract.title",
        "tool.extract.description",
        "organize",
        "extract",
        "pdf_single",
        50,
        "extract_out",
        "warning",
        OperationType.EXTRACT_PAGES,
        action_button_key="button.extract",
        default_output_suffix="_extrait",
        success_title="Extraction terminee",
        progress_message="Preparation du PDF...",
    ),
    _available_operation_tool(
        "reorder",
        "tool.reorder.title",
        "tool.reorder.description",
        "organize",
        "reorder",
        "pdf_single",
        60,
        "reorder_grid",
        "primary",
        OperationType.REORDER_PAGES,
        input_mode="complete_order",
        action_button_key="button.reorder",
        ranges_label_key="label.page_order",
        page_range_placeholder="3,1,2,4-6",
        help_key="page.reorder.help",
        default_output_suffix="_reorganise",
        success_title="Reorganisation terminee",
        progress_message="Reorganisation locale...",
    ),
    _available_operation_tool(
        "insert",
        "tool.insert_pages.title",
        "tool.insert_pages.description",
        "organize",
        "insert",
        "pdf_multiple",
        65,
        "insert_pages",
        "info",
        OperationType.INSERT_PDF_PAGES,
        allows_multiple_inputs=True,
        action_button_key="button.insert_pages",
        default_output_suffix="_avec-pages",
        success_title="Insertion terminee",
        progress_message="Insertion locale...",
    ),
    _available_operation_tool(
        "blank_page",
        "tool.blank_page.title",
        "tool.blank_page.description",
        "organize",
        "blank_page",
        "pdf_single",
        67,
        "blank_page",
        "info",
        OperationType.INSERT_BLANK_PAGE,
        requires_page_range=False,
        action_button_key="button.blank_page",
        default_output_suffix="_avec-page-blanche",
        success_title="Page blanche ajoutee",
        progress_message="Insertion locale...",
    ),
    _available_operation_tool(
        "rotate",
        "tool.rotate.title",
        "tool.rotate.description",
        "edit",
        "rotate",
        "pdf_single",
        70,
        "rotate_arrow",
        "success",
        OperationType.ROTATE_PAGES,
        dashboard_group="dashboard.group.edit_pdf",
        action_button_key="button.rotate",
        requires_rotation_angle=True,
        default_output_suffix="_tourne",
        success_title="Rotation terminee",
        progress_message="Rotation locale...",
    ),
    _pending_tool(
        "scan_to_pdf",
        "tool.scan_to_pdf.title",
        "tool.scan_to_pdf.description",
        "organize",
        "dashboard.group.organize_pdf",
        "none",
        80,
        "scanner",
        "warning",
    ),
    _pending_tool(
        "compress",
        "tool.compress.title",
        "tool.compress.description",
        "optimize",
        "dashboard.group.optimize_pdf",
        "pdf_single",
        100,
        "compress_inward",
        "info",
    ),
    _pending_tool(
        "repair_pdf",
        "tool.repair_pdf.title",
        "tool.repair_pdf.description",
        "optimize",
        "dashboard.group.optimize_pdf",
        "pdf_single",
        110,
        "repair_tool",
        "warning",
    ),
    _pending_tool(
        "ocr_pdf",
        "tool.ocr_pdf.title",
        "tool.ocr_pdf.description",
        "optimize",
        "dashboard.group.optimize_pdf",
        "pdf_single",
        120,
        "ocr_target",
        "warning",
    ),
    _pending_tool(
        "jpg_to_pdf",
        "tool.jpg_to_pdf.title",
        "tool.jpg_to_pdf.description",
        "convert_to_pdf",
        "dashboard.group.convert_to_pdf",
        "images",
        140,
        "image_to_doc",
        "primary",
    ),
    _pending_tool(
        "word_to_pdf",
        "tool.word_to_pdf.title",
        "tool.word_to_pdf.description",
        "convert_to_pdf",
        "dashboard.group.convert_to_pdf",
        "none",
        150,
        "text_doc_to_pdf",
        "primary",
    ),
    _pending_tool(
        "powerpoint_to_pdf",
        "tool.powerpoint_to_pdf.title",
        "tool.powerpoint_to_pdf.description",
        "convert_to_pdf",
        "dashboard.group.convert_to_pdf",
        "none",
        160,
        "slide_to_pdf",
        "primary",
    ),
    _pending_tool(
        "excel_to_pdf",
        "tool.excel_to_pdf.title",
        "tool.excel_to_pdf.description",
        "convert_to_pdf",
        "dashboard.group.convert_to_pdf",
        "none",
        170,
        "sheet_to_pdf",
        "primary",
    ),
    _pending_tool(
        "html_to_pdf",
        "tool.html_to_pdf.title",
        "tool.html_to_pdf.description",
        "convert_to_pdf",
        "dashboard.group.convert_to_pdf",
        "none",
        180,
        "html_to_pdf",
        "primary",
    ),
    _pending_tool(
        "pdf_to_jpg",
        "tool.pdf_to_jpg.title",
        "tool.pdf_to_jpg.description",
        "convert_from_pdf",
        "dashboard.group.convert_from_pdf",
        "pdf_single",
        200,
        "doc_to_image",
        "primary",
    ),
    _pending_tool(
        "pdf_to_word",
        "tool.pdf_to_word.title",
        "tool.pdf_to_word.description",
        "convert_from_pdf",
        "dashboard.group.convert_from_pdf",
        "pdf_single",
        210,
        "pdf_to_text_doc",
        "info",
    ),
    _pending_tool(
        "pdf_to_powerpoint",
        "tool.pdf_to_powerpoint.title",
        "tool.pdf_to_powerpoint.description",
        "convert_from_pdf",
        "dashboard.group.convert_from_pdf",
        "pdf_single",
        220,
        "pdf_to_slide",
        "info",
    ),
    _pending_tool(
        "pdf_to_excel",
        "tool.pdf_to_excel.title",
        "tool.pdf_to_excel.description",
        "convert_from_pdf",
        "dashboard.group.convert_from_pdf",
        "pdf_single",
        230,
        "pdf_to_sheet",
        "info",
    ),
    _pending_tool(
        "pdf_to_pdfa",
        "tool.pdf_to_pdfa.title",
        "tool.pdf_to_pdfa.description",
        "convert_from_pdf",
        "dashboard.group.convert_from_pdf",
        "pdf_single",
        240,
        "archive_doc",
        "info",
    ),
    _pending_tool(
        "page_numbers",
        "tool.page_numbers.title",
        "tool.page_numbers.description",
        "edit",
        "dashboard.group.edit_pdf",
        "pdf_single",
        260,
        "page_numbers",
        "info",
    ),
    _pending_tool(
        "watermark",
        "tool.watermark.title",
        "tool.watermark.description",
        "edit",
        "dashboard.group.edit_pdf",
        "pdf_single",
        270,
        "watermark",
        "warning",
    ),
    _pending_tool(
        "crop",
        "tool.crop.title",
        "tool.crop.description",
        "edit",
        "dashboard.group.edit_pdf",
        "pdf_single",
        280,
        "crop_marks",
        "warning",
    ),
    _pending_tool(
        "edit_pdf",
        "tool.edit_pdf.title",
        "tool.edit_pdf.description",
        "edit",
        "dashboard.group.edit_pdf",
        "pdf_single",
        290,
        "edit_pen",
        "primary",
    ),
    _pending_tool(
        "pdf_forms",
        "tool.pdf_forms.title",
        "tool.pdf_forms.description",
        "edit",
        "dashboard.group.edit_pdf",
        "pdf_single",
        300,
        "form_fields",
        "primary",
    ),
    _pending_tool(
        "unlock_pdf",
        "tool.unlock_pdf.title",
        "tool.unlock_pdf.description",
        "security",
        "dashboard.group.security_pdf",
        "pdf_single",
        320,
        "unlock",
        "warning",
    ),
    _pending_tool(
        "protect",
        "tool.protect.title",
        "tool.protect.description",
        "security",
        "dashboard.group.security_pdf",
        "pdf_single",
        330,
        "lock",
        "success",
    ),
    _pending_tool(
        "sign_pdf",
        "tool.sign_pdf.title",
        "tool.sign_pdf.description",
        "security",
        "dashboard.group.security_pdf",
        "pdf_single",
        340,
        "pen_signature",
        "success",
    ),
    _pending_tool(
        "redact_pdf",
        "tool.redact_pdf.title",
        "tool.redact_pdf.description",
        "security",
        "dashboard.group.security_pdf",
        "pdf_single",
        350,
        "redact_bar",
        "danger",
    ),
    _pending_tool(
        "compare_pdf",
        "tool.compare_pdf.title",
        "tool.compare_pdf.description",
        "security",
        "dashboard.group.security_pdf",
        "pdf_multiple",
        360,
        "compare_pages",
        "info",
    ),
    _pending_tool(
        "summarize_pdf_ai",
        "tool.summarize_pdf_ai.title",
        "tool.summarize_pdf_ai.description",
        "intelligence",
        "dashboard.group.intelligence_pdf",
        "pdf_single",
        380,
        "ai_summary",
        "info",
        visibility="roadmap_only",
        stage="later",
    ),
    _pending_tool(
        "translate_pdf_ai",
        "tool.translate_pdf_ai.title",
        "tool.translate_pdf_ai.description",
        "intelligence",
        "dashboard.group.intelligence_pdf",
        "pdf_single",
        390,
        "translate_doc",
        "info",
        visibility="roadmap_only",
        stage="later",
    ),
    _hidden_tool("duplicate_pages", 500),
    _pending_tool(
        "create_from_pages",
        "tool.compose_pdf.title",
        "tool.compose_pdf.description",
        "organize",
        "dashboard.group.organize_pdf",
        "pdf_multiple",
        520,
        "merge_pages",
        "info",
        visibility="roadmap_only",
        stage="later",
    ),
    _hidden_tool("linearize", 530),
    _hidden_tool("reduce_images", 540),
    _hidden_tool("images_to_pdf", 550, "images"),
    _hidden_tool("text_to_pdf", 560, "none"),
    _hidden_tool("office_to_pdf", 570, "none"),
    _hidden_tool("pdf_to_images", 580),
    _hidden_tool("pdf_to_text", 590),
    _hidden_tool("pdf_to_office", 600),
    _hidden_tool("add_text", 610),
    _hidden_tool("add_image", 620),
    _hidden_tool("add_shapes", 630),
    _hidden_tool("annotate", 640),
    _hidden_tool("highlight", 650),
    _hidden_tool("flatten", 660),
    _hidden_tool("metadata", 670),
    _hidden_tool("unlock_known_password", 680),
    _hidden_tool("visual_signature", 690),
    _hidden_tool("real_redaction", 700),
    _hidden_tool("digital_signature", 710),
    _hidden_tool("ocr_local", 720),
    _hidden_tool("searchable_scan", 730),
    _hidden_tool("detect_orientation", 740),
    _hidden_tool("clean_scan", 750),
    _hidden_tool("local_scanner", 760, "none"),
    _hidden_tool("batch_operations", 770, "pdf_multiple"),
    _hidden_tool("presets", 780, "none"),
    _hidden_tool("processing_report", 790, "none"),
)

TOOL_SPECS_BY_KEY = {spec.route_key: spec for spec in TOOL_SPECS}
TOOL_SPECS_BY_OPERATION = {
    spec.operation: spec for spec in TOOL_SPECS if spec.operation is not None
}


def tool_spec_for_operation(operation: OperationType) -> ToolSpec:
    return TOOL_SPECS_BY_OPERATION[operation]
