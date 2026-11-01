from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from priveopdf.app.settings import AppSettings
from priveopdf.ui.components import (
    ElidedLabel,
    PdfDropZone,
    PrimaryButton,
    SecondaryButton,
    SurfacePanel,
    ToolCard,
)
from priveopdf.ui.components.pdf_input import choose_pdf_files
from priveopdf.ui.i18n import Locale, tr
from priveopdf.ui.theme.tokens import SPACING
from priveopdf.ui.tool_specs import TOOL_SPECS, TOOL_SPECS_BY_KEY, ToolSpec
from priveopdf.ui.workspace_state import WorkspaceDocument, preloads_open_documents

# Home grid: available tools fit without scrolling at 1366 x 768.
CATALOG_COLUMNS = 4


class Dashboard(QWidget):
    tool_requested = Signal(str)
    workspace_files_added = Signal(list)

    def __init__(self, locale: Locale = "en") -> None:
        super().__init__()
        self.setObjectName("Dashboard")
        self._locale = locale
        self._cards: dict[str, ToolCard] = {}
        self._group_hosts: dict[str, QWidget] = {}
        self._group_cards: dict[str, QGridLayout] = {}
        self._catalog_grid: QGridLayout | None = None
        self._workspace_documents: tuple[WorkspaceDocument, ...] = ()
        self._selected_document_id: str | None = None
        self._recommended_key: str | None = None
        self._planned_rows: list[tuple[QLabel, ToolSpec]] = []

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        scroll.setWidget(content)

        self._dropzone = PdfDropZone(locale=locale, compact=True)
        self._dropzone.files_dropped.connect(self._handle_files)
        self._dropzone.browse_requested.connect(self._browse_files)

        # Context of the open documents; the sidebar keeps the document list itself.
        self._ready_panel = SurfacePanel(role="success")
        self._ready_panel.setObjectName("DashboardReadyPanel")
        ready_layout = QVBoxLayout(self._ready_panel)
        ready_layout.setContentsMargins(*(SPACING["lg"],) * 4)
        ready_layout.setSpacing(SPACING["sm"])
        heading = QHBoxLayout()
        heading.setSpacing(SPACING["md"])
        self._ready_title = QLabel()
        self._ready_title.setObjectName("SectionTitle")
        self._ready_summary = ElidedLabel()
        self._ready_summary.setObjectName("HelpText")
        heading.addWidget(self._ready_title)
        heading.addWidget(self._ready_summary, 1)
        actions = QHBoxLayout()
        actions.setSpacing(SPACING["md"])
        self._recommended_label = QLabel()
        self._recommended_label.setObjectName("MutedText")
        self._recommended_button = PrimaryButton()
        self._recommended_button.clicked.connect(self._open_recommended_tool)
        self._add_files_button = SecondaryButton()
        self._add_files_button.clicked.connect(self._browse_files)
        actions.addWidget(self._recommended_label)
        actions.addWidget(self._recommended_button)
        actions.addStretch(1)
        actions.addWidget(self._add_files_button)
        ready_layout.addLayout(heading)
        ready_layout.addLayout(actions)
        self._ready_panel.setVisible(False)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(SPACING["xl"], SPACING["lg"], SPACING["xl"], SPACING["xl"])
        layout.setSpacing(SPACING["md"])
        layout.addWidget(self._dropzone)
        layout.addWidget(self._ready_panel)

        self._catalog_host = QWidget()
        catalog_layout = QVBoxLayout(self._catalog_host)
        catalog_layout.setContentsMargins(0, 0, 0, 0)
        catalog_layout.setSpacing(SPACING["sm"])
        catalog_header = QHBoxLayout()
        catalog_header.setSpacing(SPACING["md"])
        self._available_title = QLabel()
        self._available_title.setObjectName("SectionTitle")
        self._search_input = QLineEdit()
        self._search_input.setObjectName("DashboardToolSearch")
        self._search_input.setClearButtonEnabled(True)
        self._search_input.setMaximumWidth(360)
        self._search_input.textChanged.connect(self._filter_available_tools)
        catalog_header.addWidget(self._available_title)
        catalog_header.addStretch(1)
        catalog_header.addWidget(self._search_input, 1)
        catalog_layout.addLayout(catalog_header)
        catalog_layout.addLayout(self._build_catalog())
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
            planned_layout.addWidget(_group_label(group_key, "SectionTitle"))
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

    def _build_catalog(self) -> QGridLayout:
        """Registry groups packed in bands of CATALOG_COLUMNS equal columns."""

        grid = QGridLayout()
        self._catalog_grid = grid
        grid.setHorizontalSpacing(SPACING["md"])
        grid.setVerticalSpacing(SPACING["sm"])
        for column in range(CATALOG_COLUMNS):
            grid.setColumnStretch(column, 1)
        groups = _available_dashboard_groups()
        specs_by_group = dict(groups)
        placements = _catalog_placement(
            tuple((key, len(specs)) for key, specs in groups), CATALOG_COLUMNS
        )
        for group_key, row, column, span in placements:
            host = QWidget()
            host_layout = QVBoxLayout(host)
            host_layout.setContentsMargins(0, 0, 0, 0)
            host_layout.setSpacing(SPACING["sm"])
            host_layout.addWidget(_group_label(group_key, "MutedText"))
            cards = QGridLayout()
            cards.setHorizontalSpacing(SPACING["md"])
            cards.setVerticalSpacing(SPACING["sm"])
            for inner_column in range(span):
                cards.setColumnStretch(inner_column, 1)
            for index, spec in enumerate(specs_by_group[group_key]):
                card = ToolCard(
                    spec.key,
                    tr(spec.title_key, self._locale),
                    tr(spec.description_key, self._locale),
                    spec.icon,
                    spec.role,
                    compact=True,
                )
                card.activated.connect(self.tool_requested.emit)
                self._cards[spec.key] = card
                cards.addWidget(card, index // span, index % span)
            host_layout.addLayout(cards)
            host_layout.addStretch(1)
            self._group_hosts[group_key] = host
            self._group_cards[group_key] = cards
            grid.addWidget(host, row, column, 1, span)
        return grid

    def _handle_files(self, files: list) -> None:
        self.workspace_files_added.emit(files)

    def _browse_files(self) -> None:
        pdfs = choose_pdf_files(self, multiple=True, locale=self._locale, settings=AppSettings())
        if pdfs:
            self.workspace_files_added.emit(pdfs)

    def set_workspace_documents(
        self,
        documents: tuple[WorkspaceDocument, ...],
        selected_document_id: str | None = None,
    ) -> None:
        self._workspace_documents = documents
        self._selected_document_id = selected_document_id
        self._refresh_ready_panel()

    def set_locale(self, locale: Locale) -> None:
        self._locale = locale
        self._available_title.setText(tr("dashboard.tools.available", locale))
        self._search_input.setPlaceholderText(tr("dashboard.search.placeholder", locale))
        self._search_input.setAccessibleName(tr("dashboard.search.accessible", locale))
        self._planned_intro.setText(tr("dashboard.planned.intro", locale))
        self._dropzone.set_locale(locale)
        self._recommended_label.setText(tr("dashboard.ready.recommended_action", locale))
        self._add_files_button.setText(tr("dashboard.ready.add_files", locale))
        self._add_files_button.setToolTip(tr("dashboard.ready.add_files.tooltip", locale))
        for label in self.findChildren(QLabel):
            group_key = label.property("groupKey")
            if isinstance(group_key, str):
                label.setText(tr(group_key, locale))
        for spec in TOOL_SPECS:
            card = self._cards.get(spec.key)
            if card is not None:
                card.set_text(tr(spec.title_key, locale), tr(spec.description_key, locale))
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
        self._refresh_ready_panel()
        self._filter_available_tools(self._search_input.text())
        self._refresh_planned_toggle()

    def _refresh_ready_panel(self) -> None:
        documents = self._workspace_documents
        self._dropzone.setVisible(not documents)
        self._ready_panel.setVisible(bool(documents))
        if not documents:
            self._recommended_key = None
            return
        count = len(documents)
        title_key = "dashboard.ready.single_title" if count == 1 else "dashboard.ready.multi_title"
        self._ready_title.setText(tr(title_key, self._locale, count=count))
        selected = next(
            (item for item in documents if item.document_id == self._selected_document_id),
            documents[0],
        )
        self._ready_summary.setText(_document_summary_text(selected, count > 1, self._locale))
        self._recommended_key = _recommended_tool_key(documents, selected)
        spec = TOOL_SPECS_BY_KEY.get(self._recommended_key or "")
        self._recommended_label.setVisible(spec is not None)
        self._recommended_button.setVisible(spec is not None)
        if spec is not None:
            self._recommended_button.setText(tr(spec.title_key, self._locale))
            self._recommended_button.setToolTip(tr(spec.description_key, self._locale))

    def _open_recommended_tool(self) -> None:
        if self._recommended_key is not None:
            self.tool_requested.emit(self._recommended_key)

    def _filter_available_tools(self, query: str) -> None:
        """Show matching tools; the grid recompacts without empty cells (L7, B34)."""

        normalized = query.strip().casefold()
        shown: list[tuple[str, list[ToolSpec]]] = []
        for group_key, specs in _available_dashboard_groups():
            matching = []
            for spec in specs:
                searchable = " ".join(
                    (tr(spec.title_key, self._locale), tr(spec.description_key, self._locale))
                ).casefold()
                matches = not normalized or normalized in searchable
                self._cards[spec.key].setVisible(matches)
                if matches:
                    matching.append(spec)
            self._group_hosts[group_key].setVisible(bool(matching))
            if matching:
                shown.append((group_key, matching))
        self._place_catalog(shown)

    def _place_catalog(self, groups: list[tuple[str, list[ToolSpec]]]) -> None:
        grid = self._catalog_grid
        if grid is None:
            return
        for host in self._group_hosts.values():
            grid.removeWidget(host)
        placements = _catalog_placement(
            tuple((key, len(specs)) for key, specs in groups), CATALOG_COLUMNS
        )
        specs_by_group = dict(groups)
        for group_key, row, column, span in placements:
            cards = self._group_cards[group_key]
            for spec in specs_by_group[group_key]:
                cards.removeWidget(self._cards[spec.key])
            for index, spec in enumerate(specs_by_group[group_key]):
                cards.addWidget(self._cards[spec.key], index // span, index % span)
            for inner_column in range(CATALOG_COLUMNS):
                cards.setColumnStretch(inner_column, 1 if inner_column < span else 0)
            grid.addWidget(self._group_hosts[group_key], row, column, 1, span)

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


def _group_label(group_key: str, object_name: str) -> QLabel:
    label = QLabel()
    label.setObjectName(object_name)
    label.setProperty("groupKey", group_key)
    return label


def _available_dashboard_specs() -> tuple[ToolSpec, ...]:
    return tuple(
        spec
        for spec in sorted(TOOL_SPECS, key=lambda item: item.order)
        if spec.status == "available" and spec.dashboard_visibility == "primary"
    )


def _available_dashboard_groups() -> tuple[tuple[str, tuple[ToolSpec, ...]], ...]:
    """Available tools grouped by registry `dashboard_group`, in registry order."""

    groups: dict[str, list[ToolSpec]] = {}
    for spec in _available_dashboard_specs():
        groups.setdefault(spec.dashboard_group, []).append(spec)
    return tuple((group, tuple(specs)) for group, specs in groups.items())


def _catalog_placement(
    groups: tuple[tuple[str, int], ...], columns: int
) -> tuple[tuple[str, int, int, int], ...]:
    """Place each group as (key, band, first column, span) in rows of `columns` cells.

    A group spans as many columns as it has tools (at most `columns`) and wraps
    its cards inside that span; a group that does not fit in the current band
    starts the next one. Short groups therefore share a band.
    """

    placements: list[tuple[str, int, int, int]] = []
    band = column = 0
    for key, count in groups:
        span = max(1, min(count, columns))
        if column + span > columns:
            band += 1
            column = 0
        placements.append((key, band, column, span))
        column += span
    return tuple(placements)


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


def _recommended_tool_key(
    documents: tuple[WorkspaceDocument, ...], selected: WorkspaceDocument | None = None
) -> str | None:
    """The next step the open documents call for; reading one PDF by default.

    A protected selected PDF comes first: no other tool can read it before unlocking.
    The protection is known once a reader or a tool has tried to open the document.
    """

    if not documents:
        return None
    if selected is not None and selected.page_count_status == "locked":
        key = "unlock_pdf"
    elif preloads_open_documents(documents):
        # L5: Merge is suggested when it takes the open documents (2 to 4, readable).
        key = "merge"
    elif (selected or documents[0]).page_count_status == "error":
        # The recommendation opens the selected document: test that one.
        return None
    else:
        key = "view"
    spec = TOOL_SPECS_BY_KEY.get(key)
    return spec.key if spec is not None and spec.available else None


def _document_summary_text(
    document: WorkspaceDocument,
    selected: bool,
    locale: Locale,
) -> str:
    details: list[str] = []
    if selected:
        details.append(tr("dashboard.ready.selected_file", locale))
    if document.page_count_status == "locked":
        details.append(tr("document.status.locked", locale))
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
