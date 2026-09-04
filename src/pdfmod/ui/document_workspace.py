from __future__ import annotations

from pathlib import Path
from typing import Literal

from PySide6.QtCore import QPointF, Qt, QUrl, Signal
from PySide6.QtGui import QAction, QDesktopServices, QKeySequence
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from pdfmod.app.settings import DEFAULT_PDF_OPENING_MODE, PdfOpeningMode, normalize_pdf_opening_mode
from pdfmod.domain.document_context import DocumentContext
from pdfmod.engine.document_inspection import DocumentInspection
from pdfmod.ui.components import (
    DocumentPagesPanel,
    GhostButton,
    IconButton,
    InspectorPanel,
    PdfInputPanel,
    PrimaryButton,
    SecondaryButton,
    StatusPill,
    SurfacePanel,
    set_button_role,
)
from pdfmod.ui.components.document_pages_panel import (
    DOCUMENT_PAGES_FIRST_PAGE_PANEL_HEIGHT,
)
from pdfmod.ui.i18n import Locale, tr
from pdfmod.ui.theme.tokens import SIZES
from pdfmod.ui.tool_pages.view_pdf_page import ReaderPdfView
from pdfmod.ui.tool_specs import TOOL_SPECS_BY_KEY
from pdfmod.ui.workspace_state import WorkspaceDocument
from pdfmod.workers.document_inspection_runner import (
    DocumentInspectionResult,
    QtDocumentInspectionRunner,
)

_VIEWER_NAV_BUTTON_MIN_WIDTH = SIZES["button_primary"] + 32
_VIEWER_ZOOM_VALUE_MIN_WIDTH = 56
_VIEWER_FIT_BUTTON_MIN_WIDTH = SIZES["button_primary"] + 40
_VIEWER_PAGE_LABEL_MIN_WIDTH = 96
_VIEWER_TOOLBAR_SPACING = 4
_VIEWER_TOOLBAR_MIN_WIDTH = (
    (_VIEWER_NAV_BUTTON_MIN_WIDTH * 2)
    + (40 * 2)
    + _VIEWER_ZOOM_VALUE_MIN_WIDTH
    + _VIEWER_FIT_BUTTON_MIN_WIDTH
    + _VIEWER_PAGE_LABEL_MIN_WIDTH
    + (_VIEWER_TOOLBAR_SPACING * 6)
)
_VIEWER_PANEL_MIN_WIDTH = _VIEWER_TOOLBAR_MIN_WIDTH + 20
_DOCUMENT_HEADER_BUTTON_MIN_WIDTH = SIZES["button_primary"] + 24
_PAGE_NUMBER_INPUT_MIN_WIDTH = _VIEWER_PAGE_LABEL_MIN_WIDTH
_PAGE_NUMBER_INPUT_MAX_WIDTH = 120


class DocumentWorkspace(QWidget):
    home_requested = Signal()
    tool_requested = Signal(str)
    workspace_files_added = Signal(list)
    reading_mode_changed = Signal(bool)
    page_count_ready = Signal(object, int)
    page_count_failed = Signal(object)

    def __init__(
        self,
        locale: Locale = "en",
        pdf_opening_mode: PdfOpeningMode = DEFAULT_PDF_OPENING_MODE,
    ) -> None:
        super().__init__()
        self.setObjectName("DocumentWorkspace")
        self._locale: Locale = locale
        self._pdf_opening_mode = (
            normalize_pdf_opening_mode(pdf_opening_mode) or DEFAULT_PDF_OPENING_MODE
        )
        self._context: DocumentContext | None = None
        self._current_path: Path | None = None
        self._known_page_count: int | None = None
        self._inspection: DocumentInspection | None = None
        self._queued_inspection_path: Path | None = None
        self._drawer_view: Literal["pages", "info"] | None = None
        self._reading_mode = False
        self._badges_available = False

        self._document = QPdfDocument(self)
        self._document.pageCountChanged.connect(self._update_page_status)
        self._inspection_runner = QtDocumentInspectionRunner(self)
        self._inspection_runner.finished.connect(self._inspection_finished)

        self._home_button = GhostButton()
        self._home_button.setVisible(False)
        self._home_button.clicked.connect(self.home_requested.emit)

        self._file_label = QLabel()
        self._file_label.setObjectName("SectionTitle")
        self._file_label.setWordWrap(True)
        self._meta_label = QLabel()
        self._meta_label.setObjectName("HelpText")
        self._meta_label.setWordWrap(True)

        self._badges_host = QWidget()
        self._badges_layout = QHBoxLayout(self._badges_host)
        self._badges_layout.setContentsMargins(0, 0, 0, 0)
        self._badges_layout.setSpacing(8)

        header = QHBoxLayout()
        self._header_layout = header
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(12)
        header.addWidget(self._file_label, 3)
        header.addWidget(self._meta_label, 1)
        self._pages_toggle_button = SecondaryButton()
        self._pages_toggle_button.setMinimumWidth(_DOCUMENT_HEADER_BUTTON_MIN_WIDTH)
        self._pages_toggle_button.clicked.connect(self._toggle_pages_panel)
        self._info_toggle_button = SecondaryButton()
        self._info_toggle_button.setMinimumWidth(_DOCUMENT_HEADER_BUTTON_MIN_WIDTH)
        self._info_toggle_button.clicked.connect(self._toggle_info_panel)

        self._use_with_button = PrimaryButton()
        self._use_with_button.setMinimumWidth(_DOCUMENT_HEADER_BUTTON_MIN_WIDTH + 48)
        self._use_with_menu = QMenu(self._use_with_button)
        self._use_with_button.setMenu(self._use_with_menu)
        self._use_with_actions: dict[str, QAction] = {}

        self._more_button = SecondaryButton()
        self._more_button.setMinimumWidth(_DOCUMENT_HEADER_BUTTON_MIN_WIDTH)
        self._more_menu = QMenu(self._more_button)
        self._more_button.setMenu(self._more_menu)
        self._reading_mode_action = QAction(self)
        self._reading_mode_action.setCheckable(True)
        self._reading_mode_action.setShortcut(QKeySequence("Ctrl+Shift+R"))
        self._reading_mode_action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self._reading_mode_action.triggered.connect(self.set_reading_mode)
        self.addAction(self._reading_mode_action)
        self._open_folder_action = QAction(self)
        self._open_folder_action.triggered.connect(
            lambda _checked=False: self._open_source_folder()
        )
        self._more_menu.addAction(self._reading_mode_action)
        self._more_menu.addSeparator()
        self._more_menu.addAction(self._open_folder_action)

        header.addWidget(self._badges_host)
        header.addWidget(self._pages_toggle_button)
        header.addWidget(self._info_toggle_button)
        header.addWidget(self._use_with_button)
        header.addWidget(self._more_button)

        self._pages_scroll_content = DocumentPagesPanel(
            locale=locale,
            max_cached_thumbnails=24,
            batch_size=8,
        )
        self._document_pages_panel = self._pages_scroll_content
        self._document_pages_panel.page_clicked.connect(self._jump_to_page)
        self._thumbnail_grid = self._document_pages_panel.thumbnail_grid()

        pages_panel = InspectorPanel(role="neutral")
        pages_panel.setMinimumHeight(0)
        pages_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._pages_panel = pages_panel
        self._thumbnails_panel = pages_panel
        self._thumbnails_title = pages_panel.title_label()
        self._pages_scroll = pages_panel.scroll_area()
        self._pages_scroll.setObjectName("DocumentPagesScroll")
        self._pages_scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._document_pages_panel.set_scroll_area(self._pages_scroll)
        pages_panel.set_content(self._document_pages_panel)

        self._pdf_view = ReaderPdfView()
        self._pdf_view.setDocument(self._document)
        self._pdf_view.setPageMode(QPdfView.PageMode.MultiPage)
        self._apply_opening_zoom_mode()
        self._pdf_view.setMinimumHeight(460)
        self._pdf_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._pdf_view.pageNavigator().currentPageChanged.connect(self._update_page_status)
        self._pdf_view.zoom_requested.connect(self._zoom_by)
        self._pdf_view.page_step_requested.connect(self._go_to_relative_page)

        self._previous_button = SecondaryButton()
        self._previous_button.clicked.connect(lambda: self._go_to_relative_page(-1))
        self._next_button = SecondaryButton()
        self._next_button.clicked.connect(lambda: self._go_to_relative_page(1))
        self._zoom_out_button = IconButton()
        self._zoom_out_button.clicked.connect(lambda: self._zoom_by(0.85))
        self._zoom_in_button = IconButton()
        self._zoom_in_button.clicked.connect(lambda: self._zoom_by(1.15))
        self._zoom_value_label = QLabel()
        self._zoom_value_label.setObjectName("ViewerZoomValue")
        self._zoom_value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._zoom_value_label.setMinimumWidth(_VIEWER_ZOOM_VALUE_MIN_WIDTH)
        self._zoom_value_label.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self._fit_button = SecondaryButton()
        self._fit_button.setMinimumWidth(_VIEWER_FIT_BUTTON_MIN_WIDTH)
        self._fit_button.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self._fit_menu = QMenu(self._fit_button)
        self._fit_page_action = QAction(self)
        self._fit_page_action.triggered.connect(lambda _checked=False: self._fit_page())
        self._fit_width_action = QAction(self)
        self._fit_width_action.triggered.connect(lambda _checked=False: self._fit_width())
        self._fit_menu.addAction(self._fit_page_action)
        self._fit_menu.addAction(self._fit_width_action)
        self._fit_button.setMenu(self._fit_menu)
        for button in (self._previous_button, self._next_button):
            button.setMinimumWidth(_VIEWER_NAV_BUTTON_MIN_WIDTH)
            button.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self._page_number_input = QSpinBox()
        self._page_number_input.setObjectName("PageNumberSpinBox")
        self._page_number_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._page_number_input.setKeyboardTracking(False)
        self._page_number_input.setMinimumWidth(_PAGE_NUMBER_INPUT_MIN_WIDTH)
        self._page_number_input.setMaximumWidth(_PAGE_NUMBER_INPUT_MAX_WIDTH)
        self._page_number_input.setSizePolicy(
            QSizePolicy.Policy.Minimum,
            QSizePolicy.Policy.Fixed,
        )
        self._page_number_input.valueChanged.connect(self._jump_to_page)

        viewer_toolbar = QHBoxLayout()
        self._viewer_toolbar_layout = viewer_toolbar
        viewer_toolbar.setContentsMargins(0, 0, 0, 0)
        viewer_toolbar.setSpacing(_VIEWER_TOOLBAR_SPACING)
        for widget in (
            self._previous_button,
            self._page_number_input,
            self._next_button,
            self._zoom_out_button,
            self._zoom_value_label,
            self._zoom_in_button,
            self._fit_button,
        ):
            viewer_toolbar.addWidget(widget)
        viewer_toolbar.addStretch(1)
        self._pdf_view.zoomFactorChanged.connect(self._refresh_zoom_value)

        self._status_label = QLabel()
        self._status_label.setObjectName("StatusText")
        self._status_label.setWordWrap(True)

        self._input_panel = PdfInputPanel(multiple=False, locale=locale)
        self._input_panel.paths_selected.connect(self.workspace_files_added.emit)

        viewer_panel = SurfacePanel(role="primary")
        self._viewer_panel = viewer_panel
        viewer_panel.setMinimumWidth(_VIEWER_PANEL_MIN_WIDTH)
        viewer_layout = QVBoxLayout(viewer_panel)
        viewer_layout.setContentsMargins(10, 10, 10, 10)
        viewer_layout.setSpacing(8)
        viewer_layout.addLayout(viewer_toolbar)
        viewer_layout.addWidget(self._pdf_view, 1)
        viewer_layout.addWidget(self._status_label)

        info_content = QWidget()
        self._info_content = info_content
        info_layout = QVBoxLayout(info_content)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(8)
        info_panel = InspectorPanel(role="neutral", content=info_content)
        info_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._info_panel = info_panel
        self._info_title = info_panel.title_label()
        self._info_scroll = info_panel.scroll_area()
        self._info_scroll.setObjectName("DocumentInfoScroll")
        self._info_name = QLabel()
        self._info_name.setObjectName("HelpText")
        self._info_name.setWordWrap(True)
        self._info_pages = QLabel()
        self._info_pages.setObjectName("HelpText")
        self._info_size = QLabel()
        self._info_size.setObjectName("HelpText")
        self._info_diagnostic = QLabel()
        self._info_diagnostic.setObjectName("StatusText")
        self._info_diagnostic.setWordWrap(True)
        self._source_note = QLabel()
        self._source_note.setObjectName("HelpText")
        self._source_note.setWordWrap(True)
        info_layout.addWidget(self._info_name)
        info_layout.addWidget(self._info_pages)
        info_layout.addWidget(self._info_size)
        info_layout.addWidget(self._info_diagnostic)
        info_layout.addWidget(_separator())
        info_layout.addWidget(self._source_note)
        info_layout.addStretch(1)

        right_column = QWidget()
        right_column.setObjectName("DocumentRightColumn")
        right_column.setMinimumWidth(232)
        right_column.setMaximumWidth(300)
        right_column.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self._right_column = right_column
        right_layout = QVBoxLayout(right_column)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        self._drawer_stack = QStackedWidget()
        self._drawer_stack.setObjectName("DocumentDrawerStack")
        self._drawer_stack.addWidget(pages_panel)
        self._drawer_stack.addWidget(info_panel)
        right_layout.addWidget(self._drawer_stack, 1)
        self._right_column_layout = right_layout

        content_row = QHBoxLayout()
        content_row.setContentsMargins(0, 0, 0, 0)
        content_row.setSpacing(10)
        content_row.addWidget(viewer_panel, 1)
        content_row.addWidget(right_column, 0)
        self._content_row = content_row

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 18)
        layout.setSpacing(10)
        layout.addWidget(self._input_panel)
        layout.addLayout(header)
        layout.addLayout(content_row, 1)
        self.set_locale(locale)
        self._set_empty_state()
        self._apply_layout_state()

    def set_workspace_document(self, document: WorkspaceDocument | None) -> None:
        if document is None:
            self._set_empty_state()
            return
        context = DocumentContext(
            source_path=document.path,
            display_name=document.display_name,
            source_kind="workspace",
        )
        self.set_document_context(context, page_count=document.page_count)

    def set_document_context(
        self,
        context: DocumentContext | None,
        *,
        page_count: int | None = None,
    ) -> None:
        if context is None:
            self._set_empty_state()
            return
        self._context = context
        if self._current_path != context.source_path:
            self.load_document(context.source_path, page_count=page_count)
            return
        if page_count is not None:
            self._known_page_count = page_count
        self._refresh_document_labels()

    def load_document(self, path: Path, *, page_count: int | None = None) -> None:
        candidate = Path(path)
        self._input_panel.set_loaded(True)
        self._input_panel.setVisible(False)
        self._viewer_panel.setVisible(True)
        self._current_path = candidate
        self._known_page_count = page_count
        self._inspection = None
        self._document.close()
        self._document_pages_panel.clear_document()
        error = self._document.load(str(candidate))
        if error != QPdfDocument.Error.None_:
            self._input_panel.set_loaded(False)
            self._input_panel.setVisible(True)
            self._status_label.setText(tr("viewer.load_error", self._locale))
            self._status_label.setVisible(True)
            self._sync_page_number_input(None)
            self._set_diagnostic_badges(
                [(tr("document.badge.analysis_unavailable", self._locale), "warning")]
            )
            self.page_count_failed.emit(candidate)
            self._refresh_document_labels()
            return

        self._apply_opening_zoom_mode()
        loaded_count = self._document.pageCount()
        if loaded_count > 0:
            self._known_page_count = loaded_count
            self.page_count_ready.emit(candidate, loaded_count)
            self._document_pages_panel.set_document(candidate, loaded_count)
            self._resize_thumbnail_area(loaded_count)
        self._status_label.setText(tr("viewer.loaded", self._locale, name=candidate.name))
        self._status_label.setVisible(False)
        self._update_page_status()
        self._start_inspection(candidate)
        self._refresh_document_labels()

    def set_locale(self, locale: Locale) -> None:
        self._locale = locale
        self._input_panel.set_locale(locale)
        self._home_button.setText(tr("button.home", locale))
        self._thumbnails_title.setText(tr("document.thumbnails", locale))
        self._previous_button.setText(tr("viewer.previous_short", locale))
        self._previous_button.setToolTip(tr("viewer.previous", locale))
        self._next_button.setText(tr("viewer.next_short", locale))
        self._next_button.setToolTip(tr("viewer.next", locale))
        self._zoom_out_button.setText("-")
        self._zoom_out_button.setToolTip(tr("viewer.zoom_out", locale))
        self._zoom_out_button.setAccessibleName(tr("viewer.zoom_out", locale))
        self._zoom_in_button.setText("+")
        self._zoom_in_button.setToolTip(tr("viewer.zoom_in", locale))
        self._zoom_in_button.setAccessibleName(tr("viewer.zoom_in", locale))
        self._zoom_value_label.setAccessibleName(tr("viewer.zoom_value.accessible", locale))
        self._fit_button.setText(tr("viewer.fit_menu", locale))
        self._fit_button.setToolTip(tr("viewer.fit_menu.tooltip", locale))
        self._fit_button.setAccessibleName(tr("viewer.fit_menu.tooltip", locale))
        self._fit_page_action.setText(tr("viewer.fit_page", locale))
        self._fit_width_action.setText(tr("viewer.fit_width", locale))
        self._refresh_page_number_input_text()
        self._refresh_zoom_value()
        self._info_title.setText(tr("document.info.title", locale))
        self._source_note.setText(tr("document.source_intact", locale))
        self._document_pages_panel.set_locale(locale)
        self._rebuild_use_with_menu()
        self._refresh_layout_buttons()
        self._update_page_status()
        self._refresh_document_labels()
        self._refresh_diagnostic_view()

    def set_pdf_opening_mode(self, mode: str) -> None:
        self._pdf_opening_mode = normalize_pdf_opening_mode(mode) or DEFAULT_PDF_OPENING_MODE

    def _rebuild_use_with_menu(self) -> None:
        self._use_with_menu.clear()
        self._use_with_actions = {}
        compatible_specs = tuple(
            spec
            for spec in sorted(TOOL_SPECS_BY_KEY.values(), key=lambda item: item.order)
            if spec.available and spec.input_kind == "pdf_single" and spec.key != "view"
        )
        for spec in compatible_specs:
            action = QAction(tr(spec.title_key, self._locale), self._use_with_menu)
            action.setToolTip(tr(spec.description_key, self._locale))
            action.triggered.connect(
                lambda _checked=False, tool_key=spec.key: self.tool_requested.emit(tool_key)
            )
            self._use_with_menu.addAction(action)
            self._use_with_actions[spec.key] = action
        if compatible_specs:
            self._use_with_menu.addSeparator()
        all_tools_action = QAction(tr("tool_switcher.all", self._locale), self._use_with_menu)
        all_tools_action.triggered.connect(lambda _checked=False: self.home_requested.emit())
        self._use_with_menu.addAction(all_tools_action)
        self._use_with_actions["dashboard"] = all_tools_action

    def _start_inspection(self, path: Path) -> None:
        self._info_diagnostic.setText(tr("document.analysis.running", self._locale))
        self._info_diagnostic.setToolTip("")
        self._set_diagnostic_badges([])
        if self._inspection_runner.is_running():
            self._queued_inspection_path = path
            return
        self._inspection_runner.start(path)

    def _inspection_finished(self, result: DocumentInspectionResult) -> None:
        queued_path = self._queued_inspection_path
        self._queued_inspection_path = None
        if self._current_path == result.pdf_path:
            self._inspection = result.inspection
            if result.inspection.page_count is not None:
                self._known_page_count = result.inspection.page_count
                self.page_count_ready.emit(result.pdf_path, result.inspection.page_count)
            self._refresh_document_labels()
            self._refresh_diagnostic_view()
        if queued_path is not None and queued_path != result.pdf_path:
            self._start_inspection(queued_path)

    def _refresh_diagnostic_view(self) -> None:
        inspection = self._inspection
        if inspection is None:
            if self._current_path is None:
                self._info_diagnostic.setText(tr("document.analysis.empty", self._locale))
            return

        badges: list[tuple[str, str]] = []
        if not inspection.can_open or "analysis_failed" in inspection.warnings:
            badges.append((tr("document.badge.analysis_unavailable", self._locale), "warning"))
            self._info_diagnostic.setText(tr("document.analysis.unavailable", self._locale))
            self._info_diagnostic.setToolTip("")
        else:
            if inspection.has_extractable_text:
                badges.append((tr("document.badge.selectable_text", self._locale), "success"))
            if inspection.scan_likelihood in {"medium", "high"}:
                badges.append((tr("document.badge.probable_scan.compact", self._locale), "warning"))
            if inspection.is_encrypted:
                badges.append((tr("document.badge.protected_pdf", self._locale), "warning"))
            self._info_diagnostic.setText(
                tr(
                    f"document.scan_likelihood.{inspection.scan_likelihood}",
                    self._locale,
                )
            )
            tooltip_key = f"document.scan_likelihood.{inspection.scan_likelihood}.tooltip"
            tooltip = tr(tooltip_key, self._locale)
            self._info_diagnostic.setToolTip("" if tooltip == tooltip_key else tooltip)
        self._set_diagnostic_badges(badges)

    def _set_diagnostic_badges(self, badges: list[tuple[str, str]]) -> None:
        while self._badges_layout.count():
            item = self._badges_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for text, status in badges:
            pill = StatusPill(text, status, compact=True, icon=None)
            if text == tr("document.badge.selectable_text", self._locale):
                pill.setToolTip(tr("document.badge.selectable_text.tooltip", self._locale))
            elif text == tr("document.badge.probable_scan.compact", self._locale):
                pill.setToolTip(tr("document.badge.probable_scan.tooltip", self._locale))
            self._badges_layout.addWidget(pill)
        self._badges_layout.addStretch(1)
        self._badges_available = bool(badges)
        self._apply_layout_state()

    def _refresh_document_labels(self) -> None:
        context = self._context
        if context is None or self._current_path is None:
            self._file_label.setText(tr("document.empty.title", self._locale))
            self._meta_label.setText(tr("document.empty.meta", self._locale))
            self._info_name.setText(tr("document.empty.title", self._locale))
            self._info_pages.setText(tr("page_count.empty", self._locale))
            self._info_size.setText(tr("document.size.unknown", self._locale))
            self._info_diagnostic.setToolTip("")
            self._set_document_controls_enabled(False)
            return

        page_text = (
            tr("page_count.value", self._locale, count=self._known_page_count)
            if self._known_page_count is not None
            else tr("page_count.empty", self._locale)
        )
        size_text = _format_size(self._current_path, self._locale)
        self._file_label.setText(context.display_name)
        self._file_label.setToolTip(str(context.source_path))
        self._meta_label.setText(tr("document.meta", self._locale, pages=page_text, size=size_text))
        self._info_name.setText(context.display_name)
        self._info_name.setToolTip(str(context.source_path))
        self._info_pages.setText(page_text)
        self._info_size.setText(size_text)
        self._set_document_controls_enabled(True)

    def _set_document_controls_enabled(self, enabled: bool) -> None:
        self._pages_toggle_button.setEnabled(enabled)
        self._info_toggle_button.setEnabled(enabled)
        self._use_with_button.setEnabled(enabled)
        self._reading_mode_action.setEnabled(enabled)
        self._open_folder_action.setEnabled(enabled)
        for action in self._use_with_actions.values():
            action.setEnabled(enabled)

    def _set_empty_state(self) -> None:
        self._input_panel.set_loaded(False)
        self._input_panel.setVisible(True)
        self._viewer_panel.setVisible(False)
        self._context = None
        self._current_path = None
        self._known_page_count = None
        self._inspection = None
        self._queued_inspection_path = None
        self._document.close()
        self._document_pages_panel.clear_document()
        self._resize_thumbnail_area(None)
        self._drawer_view = None
        if self._reading_mode:
            self._reading_mode = False
            self.reading_mode_changed.emit(False)
        self._status_label.setText(tr("viewer.no_pdf", self._locale))
        self._status_label.setVisible(True)
        self._sync_page_number_input(None)
        self._set_diagnostic_badges([])
        self._refresh_document_labels()
        self._refresh_diagnostic_view()

    def _go_to_relative_page(self, offset: int) -> None:
        page_count = self._document.pageCount()
        if page_count <= 0:
            return
        navigator = self._pdf_view.pageNavigator()
        target = max(0, min(page_count - 1, navigator.currentPage() + offset))
        navigator.jump(target, QPointF(), self._pdf_view.zoomFactor())
        self._document_pages_panel.set_active_page(target + 1)
        self._update_page_status()

    def _jump_to_page(self, page_number: int) -> None:
        page_count = self._document.pageCount()
        if page_count <= 0:
            return
        target = max(0, min(page_count - 1, int(page_number) - 1))
        self._pdf_view.pageNavigator().jump(target, QPointF(), self._pdf_view.zoomFactor())
        self._update_page_status()

    def _sync_page_number_input(
        self,
        page_count: int | None,
        current_page: int | None = None,
    ) -> None:
        signals_were_blocked = self._page_number_input.blockSignals(True)
        try:
            if page_count is None or page_count <= 0:
                self._page_number_input.setEnabled(False)
                self._page_number_input.setSpecialValueText(
                    tr("viewer.page_number.empty", self._locale)
                )
                self._page_number_input.setRange(0, 0)
                self._page_number_input.setValue(0)
            else:
                self._page_number_input.setSpecialValueText("")
                self._page_number_input.setRange(1, page_count)
                self._page_number_input.setValue(max(1, min(page_count, current_page or 1)))
                self._page_number_input.setEnabled(True)
        finally:
            self._page_number_input.blockSignals(signals_were_blocked)
        self._refresh_page_number_input_text()

    def _refresh_page_number_input_text(self) -> None:
        self._page_number_input.setAccessibleName(tr("viewer.page_number.accessible", self._locale))
        page_count = self._document.pageCount()
        if page_count > 0:
            self._page_number_input.setPrefix(tr("viewer.page_number.prefix", self._locale))
            self._page_number_input.setSuffix(f" / {page_count}")
            tooltip = tr(
                "viewer.page_number.tooltip",
                self._locale,
                total=page_count,
            )
        else:
            self._page_number_input.setPrefix("")
            self._page_number_input.setSuffix("")
            tooltip = tr("viewer.page_number.unavailable", self._locale)
            self._page_number_input.setSpecialValueText(
                tr("viewer.page_number.empty", self._locale)
            )
        self._page_number_input.setToolTip(tooltip)
        self._page_number_input.setAccessibleDescription(tooltip)

    def _zoom_by(self, factor: float) -> None:
        self._pdf_view.setZoomMode(QPdfView.ZoomMode.Custom)
        zoom = max(0.25, min(4.0, self._pdf_view.zoomFactor() * factor))
        self._pdf_view.setZoomFactor(zoom)
        self._refresh_zoom_value(zoom)

    def _refresh_zoom_value(self, zoom: float | None = None) -> None:
        current_zoom = self._pdf_view.zoomFactor() if zoom is None else float(zoom)
        percent = max(1, round(current_zoom * 100))
        self._zoom_value_label.setText(f"{percent} %")
        self._zoom_value_label.setToolTip(
            tr("viewer.zoom_value.tooltip", self._locale, percent=percent)
        )

    def _fit_page(self) -> None:
        self._pdf_view.setZoomMode(QPdfView.ZoomMode.FitInView)
        self._refresh_zoom_value()

    def _fit_width(self) -> None:
        self._pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        self._refresh_zoom_value()

    def _apply_opening_zoom_mode(self) -> None:
        if self._pdf_opening_mode == "fit_width":
            self._pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
            return
        self._pdf_view.setZoomMode(QPdfView.ZoomMode.FitInView)

    def _toggle_pages_panel(self) -> None:
        if self._reading_mode:
            self.set_reading_mode(False)
        self._drawer_view = None if self._drawer_view == "pages" else "pages"
        self._apply_layout_state()

    def _toggle_info_panel(self) -> None:
        if self._reading_mode:
            self.set_reading_mode(False)
        self._drawer_view = None if self._drawer_view == "info" else "info"
        self._apply_layout_state()

    def _toggle_reading_mode(self) -> None:
        self.set_reading_mode(not self._reading_mode)

    def set_reading_mode(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if self._reading_mode == enabled:
            return
        self._reading_mode = enabled
        if enabled:
            self._pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
            self._refresh_zoom_value()
        self._apply_layout_state()
        self.reading_mode_changed.emit(enabled)

    def reading_mode(self) -> bool:
        return self._reading_mode

    def _apply_layout_state(self) -> None:
        if self._drawer_view == "pages":
            self._drawer_stack.setCurrentWidget(self._pages_panel)
        elif self._drawer_view == "info":
            self._drawer_stack.setCurrentWidget(self._info_panel)
        drawer_visible = self._drawer_view is not None and not self._reading_mode
        self._right_column.setVisible(drawer_visible)
        compact_header = self._reading_mode
        self._meta_label.setVisible(not compact_header)
        self._badges_host.setVisible(self._badges_available and not compact_header)
        self._pages_toggle_button.setVisible(not compact_header)
        self._info_toggle_button.setVisible(not compact_header)
        self._use_with_button.setVisible(not compact_header)
        self._refresh_layout_buttons()

    def _refresh_layout_buttons(self) -> None:
        pages_key = (
            "document.layout.hide_pages"
            if self._drawer_view == "pages" and not self._reading_mode
            else "document.layout.show_pages"
        )
        info_key = (
            "document.layout.hide_info"
            if self._drawer_view == "info" and not self._reading_mode
            else "document.layout.show_info"
        )
        reading_key = (
            "document.layout.exit_reading" if self._reading_mode else "document.layout.reading_mode"
        )
        self._pages_toggle_button.setText(tr("document.layout.pages_compact", self._locale))
        self._pages_toggle_button.setToolTip(tr(pages_key, self._locale))
        self._info_toggle_button.setText(tr("document.layout.info_compact", self._locale))
        self._info_toggle_button.setToolTip(tr(info_key, self._locale))
        self._use_with_button.setText(tr("document.use_with.button", self._locale))
        self._use_with_button.setToolTip(tr("document.use_with.tooltip", self._locale))
        self._more_button.setText(tr("document.more.button", self._locale))
        self._more_button.setToolTip(tr("document.more.tooltip", self._locale))
        self._reading_mode_action.setText(tr(reading_key, self._locale))
        self._reading_mode_action.setChecked(self._reading_mode)
        self._open_folder_action.setText(tr("document.open_folder", self._locale))
        self._open_folder_action.setToolTip(tr("document.open_folder.tooltip", self._locale))
        set_button_role(
            self._pages_toggle_button,
            "primary" if self._drawer_view == "pages" and not self._reading_mode else "secondary",
        )
        set_button_role(
            self._info_toggle_button,
            "primary" if self._drawer_view == "info" and not self._reading_mode else "secondary",
        )

    def _resize_thumbnail_area(self, page_count: int | None) -> None:
        del page_count
        self._pages_panel.setMinimumHeight(DOCUMENT_PAGES_FIRST_PAGE_PANEL_HEIGHT)
        self._pages_panel.setMaximumHeight(self.maximumHeight())

    def _update_page_status(self, *args: object) -> None:
        del args
        page_count = self._document.pageCount()
        if page_count <= 0:
            self._sync_page_number_input(None)
            return
        current_page = self._pdf_view.pageNavigator().currentPage() + 1
        self._sync_page_number_input(page_count, current_page)
        self._document_pages_panel.set_active_page(current_page)

    def _open_source_folder(self) -> None:
        if self._current_path is None:
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._current_path.parent)))


def _separator() -> QFrame:
    separator = QFrame()
    separator.setFrameShape(QFrame.Shape.HLine)
    separator.setFrameShadow(QFrame.Shadow.Plain)
    separator.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    return separator


def _format_size(path: Path, locale: Locale) -> str:
    try:
        size_bytes = path.stat().st_size
    except OSError:
        return tr("document.size.unknown", locale)
    if size_bytes < 1024:
        return tr("document.size.bytes", locale, size=size_bytes)
    if size_bytes < 1024 * 1024:
        return tr("document.size.kb", locale, size=size_bytes / 1024)
    return tr("document.size.mb", locale, size=size_bytes / (1024 * 1024))
