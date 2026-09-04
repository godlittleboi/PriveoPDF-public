from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from pdfmod.ui.components import PdfDropZone, PrimaryButton, SecondaryButton, SurfacePanel, ToolCard
from pdfmod.ui.i18n import Locale, tr
from pdfmod.ui.theme.tokens import SPACING
from pdfmod.ui.tool_specs import TOOL_SPECS, TOOL_SPECS_BY_KEY, ToolSpec
from pdfmod.ui.workspace_state import WorkspaceDocument

_SINGLE_DOCUMENT_SECONDARY_ACTION_KEYS = ("extract", "remove", "rotate", "reorder")
_MULTI_DOCUMENT_SECONDARY_ACTION_KEYS = ("insert", "view")


class Dashboard(QWidget):
    tool_requested = Signal(str)
    workspace_files_added = Signal(list)
    workspace_document_remove_requested = Signal(str)

    def __init__(self, locale: Locale = "en") -> None:
        super().__init__()
        self.setObjectName("Dashboard")
        self._locale = locale
        self._cards: dict[str, ToolCard] = {}
        self._workspace_documents: tuple[WorkspaceDocument, ...] = ()
        self._selected_document_id: str | None = None
        self._catalog_expanded_with_documents = False
        self._planned_rows: list[tuple[QLabel, ToolSpec]] = []

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        scroll.setWidget(content)

        self._dropzone = PdfDropZone(locale=locale)
        self._dropzone.files_dropped.connect(self._handle_files)
        self._dropzone.browse_requested.connect(self._browse_files)
        self._open_files_button = PrimaryButton()
        self._open_files_button.setObjectName("DashboardOpenFilesButton")
        self._open_files_button.clicked.connect(self._browse_files)

        self._ready_panel = SurfacePanel(role="success")
        self._ready_panel.setObjectName("DashboardReadyPanel")
        ready_layout = QVBoxLayout(self._ready_panel)
        ready_layout.setContentsMargins(18, 18, 18, 18)
        ready_layout.setSpacing(12)
        self._ready_title = QLabel()
        self._ready_title.setObjectName("SectionTitle")
        self._ready_help = QLabel()
        self._ready_help.setObjectName("HelpText")
        self._ready_help.setWordWrap(True)
        self._ready_privacy = QLabel()
        self._ready_privacy.setObjectName("HelpText")
        self._ready_privacy.setWordWrap(True)
        self._ready_files_host = QWidget()
        self._ready_files_layout = QVBoxLayout(self._ready_files_host)
        self._ready_files_layout.setContentsMargins(0, 0, 0, 0)
        self._ready_files_layout.setSpacing(8)
        self._ready_actions_host = QWidget()
        self._ready_actions_layout = QVBoxLayout(self._ready_actions_host)
        self._ready_actions_layout.setContentsMargins(0, 0, 0, 0)
        self._ready_actions_layout.setSpacing(10)
        self._add_files_button = SecondaryButton()
        self._add_files_button.clicked.connect(self._browse_files)
        self._show_all_tools_button = SecondaryButton()
        self._show_all_tools_button.clicked.connect(self._toggle_available_catalog)
        ready_layout.addWidget(self._ready_title)
        ready_layout.addWidget(self._ready_help)
        ready_layout.addWidget(self._ready_privacy)
        ready_layout.addWidget(self._ready_files_host)
        ready_layout.addWidget(self._ready_actions_host)
        ready_layout.addWidget(self._show_all_tools_button, 0, Qt.AlignmentFlag.AlignLeft)
        self._ready_panel.setVisible(False)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 24, 32, 32)
        layout.setSpacing(24)
        layout.addWidget(self._open_files_button, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self._dropzone)
        layout.addWidget(self._ready_panel)

        self._catalog_host = QWidget()
        catalog_layout = QVBoxLayout(self._catalog_host)
        catalog_layout.setContentsMargins(0, 0, 0, 0)
        catalog_layout.setSpacing(12)
        self._available_title = QLabel()
        self._available_title.setObjectName("SectionTitle")
        self._search_input = QLineEdit()
        self._search_input.setObjectName("DashboardToolSearch")
        self._search_input.setClearButtonEnabled(True)
        self._search_input.textChanged.connect(self._filter_available_tools)
        catalog_layout.addWidget(self._available_title)
        catalog_layout.addWidget(self._search_input)
        catalog_layout.addLayout(self._build_grid(_available_dashboard_specs()))
        layout.addWidget(self._catalog_host)

        self._planned_toggle = SecondaryButton()
        self._planned_toggle.setObjectName("DashboardPlannedToggle")
        self._planned_toggle.clicked.connect(self._toggle_planned_panel)
        layout.addWidget(self._planned_toggle, 0, Qt.AlignmentFlag.AlignLeft)
        self._planned_panel = SurfacePanel(soft=True, role="neutral")
        self._planned_panel.setObjectName("DashboardPlannedPanel")
        planned_layout = QVBoxLayout(self._planned_panel)
        planned_layout.setContentsMargins(*(SPACING["lg"],) * 4)
        planned_layout.setSpacing(SPACING["sm"])
        self._planned_intro = QLabel()
        self._planned_intro.setObjectName("HelpText")
        self._planned_intro.setWordWrap(True)
        planned_layout.addWidget(self._planned_intro)
        for group_key, specs in _planned_dashboard_groups():
            group_label = QLabel()
            group_label.setObjectName("SectionTitle")
            group_label.setProperty("groupKey", group_key)
            planned_layout.addWidget(group_label)
            for spec in specs:
                row = QLabel()
                row.setObjectName("HelpText")
                row.setWordWrap(True)
                row.setProperty("toolKey", spec.key)
                planned_layout.addWidget(row)
                self._planned_rows.append((row, spec))
        self._planned_panel.setVisible(False)
        layout.addWidget(self._planned_panel)
        layout.addStretch(1)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.addWidget(scroll)
        self.set_locale(locale)

    def _build_card(self, spec: ToolSpec) -> ToolCard:
        return ToolCard(
            spec.key,
            tr(spec.title_key, self._locale),
            tr(spec.description_key, self._locale),
            spec.icon,
            spec.role,
        )

    def _build_grid(self, specs: tuple[ToolSpec, ...]) -> QGridLayout:
        grid = QGridLayout()
        grid.setSpacing(16)
        columns = 2
        for index, spec in enumerate(specs):
            card = self._build_card(spec)
            card.activated.connect(self.tool_requested.emit)
            self._cards[spec.key] = card
            grid.addWidget(card, index // columns, index % columns)
        return grid

    def _handle_files(self, files: list) -> None:
        self.workspace_files_added.emit(files)

    def _browse_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            tr("pdf_input.dialog_multi", self._locale),
            "",
            "PDF (*.pdf)",
        )
        pdfs = [Path(file) for file in files if Path(file).suffix.lower() == ".pdf"]
        if pdfs:
            self.workspace_files_added.emit(pdfs)

    def set_workspace_documents(
        self,
        documents: tuple[WorkspaceDocument, ...],
        selected_document_id: str | None = None,
    ) -> None:
        had_documents = bool(self._workspace_documents)
        self._workspace_documents = documents
        self._selected_document_id = selected_document_id
        if not documents or not had_documents:
            self._catalog_expanded_with_documents = False
        self._refresh_ready_panel()
        self._refresh_dashboard_state()

    def set_locale(self, locale: Locale) -> None:
        self._locale = locale
        self._available_title.setText(tr("dashboard.tools.available", locale))
        self._open_files_button.setText(tr("dashboard.open_files", locale))
        self._open_files_button.setToolTip(tr("dashboard.open_files.tooltip", locale))
        self._search_input.setPlaceholderText(tr("dashboard.search.placeholder", locale))
        self._search_input.setAccessibleName(tr("dashboard.search.accessible", locale))
        self._planned_intro.setText(tr("dashboard.planned.intro", locale))
        self._dropzone.set_locale(locale)
        self._add_files_button.setText(tr("dashboard.ready.add_files", locale))
        self._add_files_button.setToolTip(tr("dashboard.ready.add_files.tooltip", locale))
        self._refresh_ready_panel()
        for label in self.findChildren(QLabel):
            group_key = label.property("groupKey")
            if isinstance(group_key, str):
                label.setText(tr(group_key, locale))
        for spec in TOOL_SPECS:
            card = self._cards.get(spec.key)
            if card is None:
                continue
            card.set_text(
                tr(spec.title_key, locale),
                tr(spec.description_key, locale),
            )
        for row, spec in self._planned_rows:
            stage = tr(f"dashboard.planned.stage.{spec.roadmap_stage}", locale)
            row.setText(
                tr(
                    "dashboard.planned.item",
                    locale,
                    title=tr(spec.title_key, locale),
                    description=tr(spec.description_key, locale),
                    stage=stage,
                )
            )
        self._filter_available_tools(self._search_input.text())
        self._refresh_dashboard_state()
        self._refresh_planned_toggle()

    def _refresh_ready_panel(self) -> None:
        documents = self._workspace_documents
        self._ready_panel.setVisible(bool(documents))
        self._clear_layout(self._ready_files_layout)
        self._clear_layout(self._ready_actions_layout)
        if not documents:
            return

        count = len(documents)
        title_key = "dashboard.ready.single_title" if count == 1 else "dashboard.ready.multi_title"
        self._ready_title.setText(tr(title_key, self._locale, count=count))
        self._ready_help.setText(tr("dashboard.ready.help", self._locale))
        self._ready_privacy.setText(tr("dashboard.ready.privacy", self._locale))

        self._ready_files_layout.addWidget(
            _section_label(tr("dashboard.ready.file_selection", self._locale))
        )
        for document in documents:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(8)
            file_text = _document_summary_text(
                document,
                document.document_id == self._selected_document_id,
                self._locale,
            )
            name = QLabel(file_text)
            name.setObjectName("HelpText")
            name.setToolTip(str(document.path))
            remove_button = SecondaryButton(tr("dashboard.ready.remove_file", self._locale))
            remove_button.setToolTip(tr("dashboard.ready.remove_file.tooltip", self._locale))
            remove_button.clicked.connect(
                lambda _checked=False, doc_id=document.document_id: (
                    self.workspace_document_remove_requested.emit(doc_id)
                )
            )
            row_layout.addWidget(name, 1)
            row_layout.addWidget(remove_button)
            self._ready_files_layout.addWidget(row)

        file_controls = QWidget()
        file_controls_layout = QHBoxLayout(file_controls)
        file_controls_layout.setContentsMargins(0, 0, 0, 0)
        file_controls_layout.setSpacing(8)
        file_controls_layout.addStretch(1)
        file_controls_layout.addWidget(self._add_files_button)
        self._ready_files_layout.addWidget(file_controls)

        primary_key = _ready_primary_action_key(count)
        primary_spec = TOOL_SPECS_BY_KEY.get(primary_key)
        if primary_spec is not None and primary_spec.available:
            self._ready_actions_layout.addWidget(
                _section_label(tr("dashboard.ready.recommended_action", self._locale))
            )
            self._ready_actions_layout.addWidget(self._action_button(primary_spec, primary=True))

        secondary_buttons = [
            self._action_button(spec, primary=False, document_count=count)
            for spec in _ready_secondary_action_specs(count)
        ]
        if secondary_buttons:
            self._ready_actions_layout.addWidget(
                _section_label(tr(_ready_secondary_section_key(count), self._locale))
            )
            secondary_host = QWidget()
            secondary_layout = QHBoxLayout(secondary_host)
            secondary_layout.setContentsMargins(0, 0, 0, 0)
            secondary_layout.setSpacing(8)
            for button in secondary_buttons:
                secondary_layout.addWidget(button)
            secondary_layout.addStretch(1)
            self._ready_actions_layout.addWidget(secondary_host)

    def _refresh_dashboard_state(self) -> None:
        has_documents = bool(self._workspace_documents)
        self._open_files_button.setVisible(not has_documents)
        self._dropzone.setVisible(not has_documents)
        self._catalog_host.setVisible(not has_documents or self._catalog_expanded_with_documents)
        self._show_all_tools_button.setVisible(has_documents)
        catalog_key = (
            "dashboard.catalog.hide"
            if self._catalog_expanded_with_documents
            else "dashboard.catalog.show"
        )
        self._show_all_tools_button.setText(tr(catalog_key, self._locale))
        self._show_all_tools_button.setToolTip(tr(f"{catalog_key}.tooltip", self._locale))

    def _toggle_available_catalog(self) -> None:
        self._catalog_expanded_with_documents = not self._catalog_expanded_with_documents
        self._refresh_dashboard_state()

    def _filter_available_tools(self, query: str) -> None:
        normalized = query.strip().casefold()
        for spec in _available_dashboard_specs():
            card = self._cards[spec.key]
            searchable = " ".join(
                (
                    tr(spec.title_key, self._locale),
                    tr(spec.description_key, self._locale),
                )
            ).casefold()
            card.setVisible(not normalized or normalized in searchable)

    def _toggle_planned_panel(self) -> None:
        self._planned_panel.setHidden(not self._planned_panel.isHidden())
        self._refresh_planned_toggle()

    def _refresh_planned_toggle(self) -> None:
        key = (
            "dashboard.planned.hide"
            if not self._planned_panel.isHidden()
            else "dashboard.planned.show"
        )
        self._planned_toggle.setText(tr(key, self._locale))
        self._planned_toggle.setToolTip(tr(f"{key}.tooltip", self._locale))

    def _action_button(
        self,
        spec: ToolSpec,
        *,
        primary: bool,
        document_count: int = 1,
    ) -> PrimaryButton | SecondaryButton:
        button = PrimaryButton() if primary else SecondaryButton()
        if spec.key == "view" and document_count >= 2:
            button.setText(tr("dashboard.ready.view_selected", self._locale))
            button.setToolTip(tr("dashboard.ready.view_selected.tooltip", self._locale))
        else:
            button.setText(tr(spec.title_key, self._locale))
            button.setToolTip(tr(spec.description_key, self._locale))
        button.clicked.connect(
            lambda _checked=False, tool_key=spec.key: self.tool_requested.emit(tool_key)
        )
        return button

    def _clear_layout(self, layout: QVBoxLayout | QHBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                if widget is self._add_files_button:
                    widget.setParent(None)
                else:
                    if self._add_files_button in widget.findChildren(QWidget):
                        self._add_files_button.setParent(None)
                    widget.deleteLater()


def _available_dashboard_specs() -> tuple[ToolSpec, ...]:
    return tuple(
        spec
        for spec in sorted(TOOL_SPECS, key=lambda item: item.order)
        if spec.status == "available" and spec.dashboard_visibility == "primary"
    )


def _planned_dashboard_groups() -> tuple[tuple[str, tuple[ToolSpec, ...]], ...]:
    groups: dict[str, list[ToolSpec]] = {}
    for spec in sorted(TOOL_SPECS, key=lambda item: item.order):
        if spec.status != "pending":
            continue
        if spec.dashboard_visibility == "roadmap_only" and spec.category == "intelligence":
            continue
        if spec.dashboard_visibility not in {"pending_dashboard", "roadmap_only"}:
            continue
        groups.setdefault(spec.dashboard_group, []).append(spec)
    return tuple((group, tuple(specs)) for group, specs in groups.items())


def _pending_dashboard_groups() -> tuple[tuple[str, tuple[ToolSpec, ...]], ...]:
    """Compatibility alias for registry-level contracts predating the compact list."""

    return _planned_dashboard_groups()


def _ready_action_keys(document_count: int) -> tuple[str, ...]:
    # Ready-panel tool recommendations stay separate from file-selection controls.
    return (
        _ready_primary_action_key(document_count),
        *_ready_secondary_action_keys(document_count),
    )


def _ready_primary_action_key(document_count: int) -> str:
    if document_count >= 2:
        return "merge"
    return "view"


def _ready_secondary_action_keys(document_count: int) -> tuple[str, ...]:
    if document_count >= 2:
        return _MULTI_DOCUMENT_SECONDARY_ACTION_KEYS
    return _SINGLE_DOCUMENT_SECONDARY_ACTION_KEYS


def _ready_secondary_section_key(document_count: int) -> str:
    if document_count >= 2:
        return "dashboard.ready.other_actions_multi"
    return "dashboard.ready.other_actions_single"


def _ready_secondary_action_specs(document_count: int) -> tuple[ToolSpec, ...]:
    return tuple(
        spec
        for key in _ready_secondary_action_keys(document_count)
        if (spec := TOOL_SPECS_BY_KEY.get(key)) is not None and spec.available
    )


def _ready_available_action_keys(document_count: int) -> tuple[str, ...]:
    return tuple(
        spec.key
        for key in _ready_action_keys(document_count)
        if (spec := TOOL_SPECS_BY_KEY.get(key)) is not None and spec.available
    )


def _document_summary_text(
    document: WorkspaceDocument,
    selected: bool,
    locale: Locale,
) -> str:
    details: list[str] = []
    if selected:
        details.append(tr("dashboard.ready.selected_file", locale))
    if document.page_count is not None:
        page_count_key = (
            "dashboard.ready.page_count_one"
            if document.page_count == 1
            else "dashboard.ready.page_count_many"
        )
        details.append(tr(page_count_key, locale, count=document.page_count))
    if not details:
        return document.display_name
    return f"{document.display_name} - {' - '.join(details)}"


def _section_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("MutedText")
    return label
