from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import cast

from PySide6.QtCore import QRect, QSize, Qt, QTimer
from PySide6.QtGui import QCloseEvent, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from pdfmod.app.app_info import get_display_version, get_runtime_display_name
from pdfmod.app.beta_diagnostics import (
    mark_diagnostic_notice_seen,
    pending_abnormal_diagnostic,
)
from pdfmod.app.beta_integration import load_integration_manifest
from pdfmod.app.settings import AppSettings, normalize_theme_preset
from pdfmod.app.update_checker import UpdateCheckResult
from pdfmod.domain.document_context import (
    DocumentContext,
    DocumentSourceKind,
    ToolLaunchContext,
    ToolLaunchSource,
)
from pdfmod.domain.jobs import JobResult, OperationType
from pdfmod.ui.about_dialog import AboutDialog
from pdfmod.ui.beta_integration_panel import BetaIntegrationPanel
from pdfmod.ui.branding import build_app_icon
from pdfmod.ui.community_page import CommunityPage
from pdfmod.ui.components import (
    NavigationEntry,
    Sidebar,
    TopBar,
    show_info,
    show_status_message,
)
from pdfmod.ui.controllers import (
    NavigationController,
    StartupCoordinator,
    UpdateController,
    WorkspaceController,
)
from pdfmod.ui.dashboard import Dashboard
from pdfmod.ui.document_workspace import DocumentWorkspace
from pdfmod.ui.first_run_dialog import FirstRunDialog
from pdfmod.ui.i18n import Locale, tr
from pdfmod.ui.job_registry import BusyDocumentRegistry
from pdfmod.ui.options_dialog import OptionsDialog
from pdfmod.ui.page_contracts import (
    LocalizedPage,
    ToolLaunchPage,
    WorkspaceDocumentPage,
    WorkspaceDocumentsPage,
)
from pdfmod.ui.theme import ThemeManager
from pdfmod.ui.tool_pages.insert_blank_page import InsertBlankPage
from pdfmod.ui.tool_pages.insert_pdf_pages_page import InsertPdfPagesPage
from pdfmod.ui.tool_pages.merge_pdf_page import MergePdfPage
from pdfmod.ui.tool_pages.page_operation_page import PageOperationPage
from pdfmod.ui.tool_pages.pending_tool_page import PendingToolPage
from pdfmod.ui.tool_pages.rotate_pdf_page import RotatePdfPage
from pdfmod.ui.tool_pages.visual_page_operation_page import VisualPageOperationPage
from pdfmod.ui.tool_specs import TOOL_SPECS, TOOL_SPECS_BY_KEY, ToolSpec
from pdfmod.ui.workspace_state import MAX_WORKSPACES, WorkspaceDocument

MIN_WINDOW_WIDTH = 1200
MIN_WINDOW_HEIGHT = 720


class MainWindow(QMainWindow):
    def __init__(
        self,
        initial_files: Sequence[Path] = (),
        *,
        settings: AppSettings | None = None,
    ) -> None:
        super().__init__()
        self._settings = settings or AppSettings()
        self._locale: Locale = self._settings.language()
        self._integration_manifest = load_integration_manifest()
        window_title = get_runtime_display_name()
        if self._integration_manifest is not None:
            window_title = tr(
                "beta.integration.window_title",
                self._locale,
                count=len(self._integration_manifest.pull_requests),
            )
        self.setWindowTitle(window_title)
        self.setObjectName("AppShell")
        self.setWindowFlags(
            self.windowFlags()
            | Qt.WindowType.Window
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        app_icon = build_app_icon()
        self.setWindowIcon(app_icon)
        app = QApplication.instance()
        if isinstance(app, QApplication):
            app.setWindowIcon(app_icon)
        self._apply_initial_window_geometry()
        self._theme_manager = ThemeManager(settings=self._settings)
        self._theme_manager.apply()
        self._workspace_controller = WorkspaceController(self._settings)
        self._restored_missing_paths = self._workspace_controller.restored_missing_paths
        self._store = self._workspace_controller.store
        self._is_closing = False

        self._stack = QStackedWidget()
        self._dashboard = Dashboard(self._locale)
        self._community_page = CommunityPage(self._locale)
        self._document_workspace = DocumentWorkspace(
            self._locale,
            self._settings.pdf_opening_mode(),
        )
        self._pages = self._build_pages()
        self._register_page_capabilities()
        for page in self._pages.values():
            self._stack.addWidget(page)

        self._sidebar = Sidebar(
            self._navigation_entries(),
            self._locale,
            get_display_version(self._locale),
            self._store.workspaces(),
            self._store.active_workspace_id(),
            self._store.documents(),
            self._store.selected_document_id(),
            self._settings.sidebar_collapsed(),
        )
        self._top_bar = TopBar()
        self._top_bar.set_locale(self._locale)
        self._top_bar.set_theme_preset(self._theme_manager.preset)
        self._top_bar.set_tool_specs(global_tool_switcher_specs())

        shell = QWidget()
        shell.setObjectName("AppShell")
        shell_layout = QHBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)
        shell_layout.addWidget(self._sidebar)

        content = QFrame()
        content.setObjectName("AppShell")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        content_layout.addWidget(self._top_bar)
        content_layout.addWidget(self._stack, 1)
        shell_layout.addWidget(content, 1)
        self._integration_panel = (
            BetaIntegrationPanel(self._integration_manifest, self._locale)
            if self._integration_manifest is not None
            else None
        )
        if self._integration_panel is not None:
            shell_layout.addWidget(self._integration_panel)
        self.setCentralWidget(shell)

        self._navigation_controller = NavigationController(
            stack=self._stack,
            sidebar=self._sidebar,
            top_bar=self._top_bar,
            pages=self._pages,
            tool_launch_pages=self._tool_launch_pages,
            store=self._store,
            sync_page=self._sync_page_workspace,
            page_title=self._page_title,
            reduce_motion=lambda: self._theme_manager.reduce_motion,
        )
        self._update_controller = UpdateController(
            parent=self,
            settings=self._settings,
            sidebar=self._sidebar,
            locale=lambda: self._locale,
            is_closing=lambda: self._is_closing,
        )
        self._update_runner = self._update_controller.runner
        self._startup_coordinator = StartupCoordinator(
            parent=self,
            settings=self._settings,
            selected_document_path=self._selected_document_path,
            show_dashboard=self._show_dashboard,
            open_initial_documents=self._open_initial_documents,
            show_invalid_message=lambda: show_status_message(
                self, tr("document.initial.invalid", self._locale)
            ),
            show_multiple_message=lambda: show_status_message(
                self, tr("document.initial.opened_first", self._locale)
            ),
            apply_initial_preferences=self._apply_initial_setup_preferences,
            refresh_updates=self._refresh_update_status,
            disable_updates=self._update_controller.set_disabled,
            is_closing=lambda: self._is_closing,
            first_run_dialog_factory=FirstRunDialog,
        )
        self._startup_timer = self._startup_coordinator.timer
        self._initial_classification_runner = self._startup_coordinator.classification_runner

        self._dashboard.tool_requested.connect(self._show_page)
        self._dashboard.workspace_files_added.connect(self._add_workspace_files)
        self._dashboard.workspace_document_remove_requested.connect(self._remove_workspace_document)
        self._sidebar.navigation_requested.connect(self._show_page)
        self._sidebar.community_requested.connect(lambda: self._show_page("community"))
        self._sidebar.options_requested.connect(self._open_options)
        self._sidebar.update_check_requested.connect(self._update_controller.request_manual_check)
        self._sidebar.sidebar_collapsed_changed.connect(self._set_sidebar_collapsed)
        self._sidebar.workspace_create_requested.connect(self._create_workspace)
        self._sidebar.workspace_requested.connect(self._activate_workspace)
        self._sidebar.workspace_rename_requested.connect(self._rename_workspace)
        self._sidebar.workspace_delete_requested.connect(self._delete_workspace)
        self._sidebar.workspace_document_requested.connect(self._activate_workspace_document)
        self._sidebar.workspace_document_remove_requested.connect(self._remove_workspace_document)
        self._sidebar.workspace_tool_requested.connect(self._show_workspace_tool)
        self._document_workspace.home_requested.connect(self._show_dashboard)
        self._document_workspace.workspace_files_added.connect(self._add_workspace_files)
        self._community_page.home_requested.connect(self._show_dashboard)
        self._document_workspace.tool_requested.connect(self._show_document_tool)
        self._document_workspace.reading_mode_changed.connect(self._set_document_reading_mode)
        self._top_bar.about_requested.connect(self._open_about)
        self._top_bar.toggle_theme_requested.connect(self._toggle_theme)
        self._top_bar.tool_requested.connect(self._show_global_tool)
        self._theme_manager.theme_changed.connect(self._theme_preset_changed)
        self._tool_switcher_shortcut = QShortcut(QKeySequence("Ctrl+K"), self)
        self._tool_switcher_shortcut.activated.connect(self._top_bar.open_tools_menu)
        self._connect_tool_pages()
        self._startup_coordinator.start(initial_files)
        if self._restored_missing_paths:
            show_status_message(
                self,
                tr(
                    "workspace.restore.missing",
                    self._locale,
                    count=len(self._restored_missing_paths),
                ),
            )
        if pending_abnormal_diagnostic() is not None:
            QTimer.singleShot(0, self._show_pending_diagnostic_notice)

    def _show_pending_diagnostic_notice(self) -> None:
        session = pending_abnormal_diagnostic()
        if session is None:
            return
        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Warning)
        dialog.setWindowTitle(tr("diagnostic.previous_crash.title", self._locale))
        dialog.setText(tr("diagnostic.previous_crash.message", self._locale))
        dialog.setTextFormat(Qt.TextFormat.PlainText)
        dialog.exec()
        mark_diagnostic_notice_seen(session)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        self._is_closing = True
        self._startup_coordinator.close()
        self._settings.set_window_geometry(self.saveGeometry())
        self._workspace_controller.close()
        super().closeEvent(event)

    def _apply_initial_window_geometry(self) -> None:
        screen = QApplication.primaryScreen()
        available = screen.availableGeometry() if screen is not None else QRect(0, 0, 1366, 768)
        # TODO: add responsive breakpoints before supporting smaller desktop windows.
        minimum = QSize(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)
        self.setMinimumSize(minimum)
        saved_geometry = self._settings.window_geometry()
        if saved_geometry is not None and self.restoreGeometry(saved_geometry):
            return
        size = QSize(
            max(minimum.width(), int(available.width() * 0.88)),
            max(minimum.height(), int(available.height() * 0.88)),
        )
        size.setWidth(min(size.width(), available.width()))
        size.setHeight(min(size.height(), available.height()))
        self.resize(size)
        frame = self.frameGeometry()
        frame.moveCenter(available.center())
        self.move(frame.topLeft())

    def _build_pages(self) -> dict[str, QWidget]:
        pages: dict[str, QWidget] = {
            "dashboard": self._dashboard,
            "community": self._community_page,
            "document": self._document_workspace,
        }
        for spec in sorted(TOOL_SPECS, key=lambda item: item.order):
            if spec.view_kind == "viewer":
                continue
            elif spec.view_kind == "operation" and spec.operation is OperationType.MERGE_PDFS:
                pages[spec.route_key] = MergePdfPage(self._locale, self._settings)
            elif spec.view_kind == "operation" and spec.operation is OperationType.ROTATE_PAGES:
                pages[spec.route_key] = RotatePdfPage(self._locale, self._settings)
            elif spec.view_kind == "operation" and spec.operation is OperationType.INSERT_PDF_PAGES:
                pages[spec.route_key] = InsertPdfPagesPage(self._locale, self._settings)
            elif (
                spec.view_kind == "operation" and spec.operation is OperationType.INSERT_BLANK_PAGE
            ):
                pages[spec.route_key] = InsertBlankPage(self._locale, self._settings)
            elif spec.view_kind == "operation" and spec.operation in {
                OperationType.SPLIT_BY_RANGES,
                OperationType.EXTRACT_PAGES,
                OperationType.REMOVE_PAGES,
            }:
                pages[spec.route_key] = VisualPageOperationPage(
                    cast(OperationType, spec.operation),
                    self._locale,
                    self._settings,
                )
            elif spec.view_kind == "operation" and spec.operation is not None:
                pages[spec.route_key] = PageOperationPage(
                    spec.operation,
                    self._locale,
                    self._settings,
                )
            elif spec.view_kind == "pending" and spec.key != "create_from_pages":
                pages[spec.route_key] = PendingToolPage(spec, self._locale)
        return pages

    def _register_page_capabilities(self) -> None:
        self._localized_pages = tuple(cast(LocalizedPage, page) for page in self._pages.values())
        self._workspace_document_pages: dict[QWidget, WorkspaceDocumentPage] = {}
        self._workspace_documents_pages: dict[QWidget, WorkspaceDocumentsPage] = {
            self._dashboard: cast(WorkspaceDocumentsPage, self._dashboard)
        }
        self._tool_launch_pages: dict[str, ToolLaunchPage] = {}
        self._busy_document_registry = BusyDocumentRegistry()

        for key, page in self._pages.items():
            if isinstance(page, MergePdfPage):
                self._workspace_documents_pages[page] = page
                self._tool_launch_pages[key] = page
                self._busy_document_registry.register(page)
            elif isinstance(
                page,
                (
                    PageOperationPage,
                    VisualPageOperationPage,
                    RotatePdfPage,
                    InsertPdfPagesPage,
                    InsertBlankPage,
                ),
            ):
                self._workspace_document_pages[page] = page
                self._tool_launch_pages[key] = page
                self._busy_document_registry.register(page)
                if isinstance(page, InsertPdfPagesPage):
                    self._workspace_documents_pages[page] = page

    def _connect_tool_pages(self) -> None:
        self._document_workspace.page_count_ready.connect(self._workspace_page_count_ready)
        self._document_workspace.page_count_failed.connect(self._workspace_page_count_failed)
        for page in self._pages.values():
            if isinstance(page, PendingToolPage):
                page.back_requested.connect(self._handle_tool_back_requested)
            elif isinstance(page, MergePdfPage):
                page.back_requested.connect(self._handle_tool_back_requested)
                page.workspace_files_added.connect(self._add_workspace_files)
                page.job_completed.connect(self._tool_job_finished)
                page.output_pdf_requested.connect(self._open_generated_pdf)
            elif isinstance(
                page,
                (
                    PageOperationPage,
                    VisualPageOperationPage,
                    RotatePdfPage,
                    InsertPdfPagesPage,
                    InsertBlankPage,
                ),
            ):
                page.back_requested.connect(self._handle_tool_back_requested)
                page.workspace_files_added.connect(self._add_workspace_files)
                page.page_count_ready.connect(self._workspace_page_count_ready)
                page.page_count_failed.connect(self._workspace_page_count_failed)
                page.job_completed.connect(self._tool_job_finished)

    def _show_page(
        self,
        key: str,
        launch_context: ToolLaunchContext | None = None,
    ) -> None:
        if key not in {"view", "document"} and self._document_workspace.reading_mode():
            self._document_workspace.set_reading_mode(False)
        if key == "view":
            self._open_document_workspace()
            return
        self._navigation_controller.show(key, launch_context)

    @property
    def _active_tool_launch_context(self) -> ToolLaunchContext | None:
        return self._navigation_controller.active_tool_launch_context

    @_active_tool_launch_context.setter
    def _active_tool_launch_context(self, context: ToolLaunchContext | None) -> None:
        self._navigation_controller.active_tool_launch_context = context

    def _show_dashboard(self) -> None:
        self._show_page("dashboard")

    def _handle_tool_back_requested(self) -> None:
        context = self._active_tool_launch_context
        if (
            context is not None
            and context.return_to_document
            and self._store.selected_document() is not None
        ):
            self._open_document_workspace()
            return
        self._show_dashboard()

    def _show_workspace_tool(self, key: str) -> None:
        if key == "view":
            self._open_document_workspace()
            return
        context = self._build_tool_launch_context(
            key,
            source="workspace_sidebar",
            return_to_document=False,
        )
        self._show_page(key, context)

    def _show_document_tool(self, key: str) -> None:
        if key == "view":
            self._open_document_workspace()
            return
        context = self._build_tool_launch_context(
            key,
            source="document_workspace",
            return_to_document=True,
        )
        self._show_page(key, context)

    def _show_global_tool(self, key: str) -> None:
        if key == "dashboard":
            self._show_dashboard()
            return
        if self._store.selected_document() is None:
            self._show_page(key)
            return
        if key == "merge" and len(self._store.documents()) >= 2:
            self._show_workspace_tool(key)
            return
        self._show_document_tool(key)

    def _toggle_theme(self) -> None:
        self._theme_manager.toggle_brightness()
        self._sync_store_preferences()

    def _theme_preset_changed(self, preset: str) -> None:
        self._top_bar.set_theme_preset(preset)
        self._sync_store_preferences()

    def _open_options(self) -> None:
        previous_locale = self._settings.language()
        dialog = OptionsDialog(self._settings, self._locale, self)
        dialog.preferences_changed.connect(self._apply_preferences)
        dialog.manual_update_check_requested.connect(
            lambda: self._start_manual_update_check(dialog)
        )
        result = dialog.exec()
        language_changed = self._settings.language() != previous_locale
        if result == QDialog.DialogCode.Accepted and language_changed:
            show_info(
                self,
                tr("options.restart_required.title", self._locale),
                tr("options.restart_required.message", self._locale),
            )

    def _open_about(self) -> None:
        dialog = AboutDialog(self._locale, self._update_status_text(), self)
        dialog.exec()

    def _set_sidebar_collapsed(self, collapsed: bool) -> None:
        self._settings.set_sidebar_collapsed(collapsed)
        self._settings.sync()

    def _set_document_reading_mode(self, enabled: bool) -> None:
        reading_document = enabled and self._stack.currentWidget() is self._document_workspace
        self._sidebar.setVisible(not reading_document)
        self._top_bar.setVisible(not reading_document)

    def _activate_workspace_document(self, document_id: str) -> None:
        if self._store.select_document(document_id):
            self._autosave_workspace_session()
            self._open_document_workspace()

    def _create_workspace(self) -> None:
        workspace = self._store.add_workspace()
        if workspace is None:
            show_status_message(
                self,
                tr("workspace.limit_reached", self._locale, max_count=MAX_WORKSPACES),
            )
            return
        self._refresh_workspace_views()
        self._autosave_workspace_session()

    def _activate_workspace(self, workspace_id: str) -> None:
        if self._store.select_workspace(workspace_id):
            self._refresh_workspace_views()
            self._autosave_workspace_session()

    def _rename_workspace(self, workspace_id: str, name: str) -> None:
        if self._store.rename_workspace(workspace_id, name):
            self._refresh_workspace_views()
            self._autosave_workspace_session()

    def _delete_workspace(self, workspace_id: str) -> None:
        workspace = next(
            (
                candidate
                for candidate in self._store.workspaces()
                if candidate.workspace_id == workspace_id
            ),
            None,
        )
        if workspace is None:
            return
        if len(self._store.workspaces()) <= 1:
            show_info(
                self,
                tr("workspace.delete.last.title", self._locale),
                tr("workspace.delete.last.message", self._locale),
            )
            return
        if workspace.documents and not self._confirm_workspace_delete(workspace.name):
            return
        removed = self._store.remove_workspace(workspace_id)
        if removed is None:
            return
        self._refresh_workspace_views()
        self._autosave_workspace_session()
        show_status_message(self, tr("workspace.deleted", self._locale))

    def _confirm_workspace_delete(self, workspace_name: str) -> bool:
        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Warning)
        dialog.setWindowTitle(tr("workspace.delete.confirm.title", self._locale))
        dialog.setText(tr("workspace.delete.confirm.message", self._locale, name=workspace_name))
        delete_button = dialog.addButton(
            tr("workspace.delete", self._locale),
            QMessageBox.ButtonRole.AcceptRole,
        )
        dialog.addButton(tr("options.close", self._locale), QMessageBox.ButtonRole.RejectRole)
        self._strip_message_box_button_icons(dialog)
        dialog.exec()
        return dialog.clickedButton() is delete_button

    def _remove_workspace_document(self, document_id: str) -> None:
        document = self._store.document_by_id(document_id)
        if document is None:
            return
        if self._workspace_document_is_busy(document.path):
            show_info(
                self,
                tr("workspace.remove.busy.title", self._locale),
                tr("workspace.remove.busy.message", self._locale),
            )
            return
        removed = self._store.remove_document(document_id)
        if removed is None:
            return
        self._refresh_workspace_views()
        self._autosave_workspace_session()
        show_status_message(self, tr("workspace.removed", self._locale))

    def _add_workspace_files(self, paths: list[Path], select_added: bool = True) -> None:
        added = self._add_documents_to_workspace(paths, source_kind="drop")
        if added and select_added:
            self._store.select_document(added[0].document_id)
        self._refresh_workspace_views()
        self._autosave_workspace_session()

    def _add_documents_to_workspace(
        self,
        paths: Sequence[Path],
        *,
        source_kind: DocumentSourceKind,
        last_output_path: Path | None = None,
    ) -> tuple[WorkspaceDocument, ...]:
        return self._workspace_controller.add_documents(
            paths,
            source_kind=source_kind,
            last_output_path=last_output_path,
        )

    def _open_document_workspace(
        self,
        paths: Sequence[Path] = (),
        *,
        source_kind: DocumentSourceKind = "workspace",
        selected_path: Path | None = None,
        last_output_path: Path | None = None,
    ) -> None:
        added = self._add_documents_to_workspace(
            paths,
            source_kind=source_kind,
            last_output_path=last_output_path,
        )
        if selected_path is None and added:
            selected_path = added[0].path
        if selected_path is not None:
            document = self._store.document_by_path(selected_path)
            if document is not None:
                self._store.select_document(document.document_id)
        self._refresh_workspace_views()
        self._show_page("document")
        self._autosave_workspace_session()

    def _workspace_page_count_ready(self, path: Path, page_count: int) -> None:
        if self._workspace_controller.set_page_count_ready(path, page_count):
            self._refresh_workspace_views()

    def _workspace_page_count_failed(self, path: Path) -> None:
        if self._workspace_controller.set_page_count_failed(path):
            self._refresh_workspace_views()

    def _refresh_workspace_views(self) -> None:
        self._sidebar.set_workspaces(
            self._store.workspaces(),
            self._store.active_workspace_id(),
        )
        self._sidebar.set_workspace_documents(
            self._store.documents(),
            self._store.selected_document_id(),
        )
        self._dashboard.set_workspace_documents(
            self._store.documents(),
            self._store.selected_document_id(),
        )
        self._sidebar.set_workspace_tools(self._workspace_tool_specs())
        current_page = self._stack.currentWidget()
        if current_page is not None:
            self._sync_page_workspace(current_page)

    def _autosave_workspace_session(self) -> None:
        self._persist_workspace_session()

    def _persist_workspace_session(self) -> None:
        self._workspace_controller.persist()

    def _workspace_tool_specs(self) -> tuple[ToolSpec, ...]:
        selected = self._store.selected_document()
        if selected is None:
            return ()
        return workspace_compatible_tool_specs(len(self._store.documents()))

    def _sync_page_workspace(self, page: QWidget) -> None:
        if page is self._document_workspace:
            self._sync_document_workspace()
            return
        documents_page = self._workspace_documents_pages.get(page)
        if documents_page is not None:
            documents_page.set_workspace_documents(self._store.documents())
        document_page = self._workspace_document_pages.get(page)
        if document_page is not None:
            document_page.set_workspace_document(self._store.selected_document())

    def _sync_document_workspace(self) -> None:
        document = self._store.selected_document()
        if document is None:
            self._document_workspace.set_document_context(None)
            return
        context = self._document_context_for_document(document)
        self._document_workspace.set_document_context(context, page_count=document.page_count)

    def _selected_document_path(self) -> Path | None:
        selected = self._store.selected_document()
        return selected.path if selected is not None else None

    def _open_initial_documents(
        self,
        paths: tuple[Path, ...],
        selected_path: Path,
    ) -> None:
        self._open_document_workspace(
            paths,
            source_kind="launcher" if paths else "workspace",
            selected_path=selected_path,
        )

    def _handle_initial_files(self, initial_files: tuple[Path, ...]) -> None:
        self._startup_coordinator.start(initial_files)

    def _classify_initial_files(
        self,
        initial_files: tuple[Path, ...],
    ) -> tuple[tuple[Path, ...], tuple[Path, ...]]:
        return self._startup_coordinator.classify_files_now(initial_files)

    def _remember_document_context(
        self,
        path: Path,
        source_kind: DocumentSourceKind,
        *,
        last_output_path: Path | None = None,
    ) -> None:
        self._workspace_controller.remember_document_context(
            path,
            source_kind,
            last_output_path=last_output_path,
        )

    def _document_context_for_document(
        self,
        document: WorkspaceDocument,
    ) -> DocumentContext:
        return self._workspace_controller.document_context_for(document)

    def _build_tool_launch_context(
        self,
        key: str,
        *,
        source: ToolLaunchSource,
        return_to_document: bool,
    ) -> ToolLaunchContext | None:
        return self._workspace_controller.build_tool_launch_context(
            key,
            source=source,
            return_to_document=return_to_document,
        )

    def _tool_job_finished(self, result: JobResult) -> None:
        context = self._active_tool_launch_context
        if context is None or not context.return_to_document:
            return
        if not result.success:
            return
        if len(result.output_files) != 1:
            return
        output_path = result.output_files[0]
        if output_path.suffix.lower() != ".pdf":
            return
        self._open_document_workspace(
            [output_path],
            source_kind="generated",
            selected_path=output_path,
            last_output_path=output_path,
        )

    def _open_generated_pdf(self, path: object) -> None:
        output_path = path if isinstance(path, Path) else Path(str(path))
        if output_path.suffix.lower() != ".pdf":
            return
        self._open_document_workspace(
            [output_path],
            source_kind="generated",
            selected_path=output_path,
            last_output_path=output_path,
        )

    def _workspace_document_is_busy(self, path: Path) -> bool:
        return self._busy_document_registry.is_busy(path)

    def _apply_preferences(
        self,
        locale: str,
        theme: str,
        reduce_motion: bool,
        update_checks: bool,
        pdf_opening_mode: str,
        open_last_pdf_on_startup: bool,
    ) -> None:
        del locale, pdf_opening_mode, open_last_pdf_on_startup
        self._theme_manager.set_reduce_motion(reduce_motion)
        normalized_theme = normalize_theme_preset(theme)
        if normalized_theme is not None:
            self._theme_manager.set_preset(normalized_theme)
        self._document_workspace.set_pdf_opening_mode(self._settings.pdf_opening_mode())
        self._sync_store_preferences()
        self._persist_workspace_session()
        if update_checks:
            self._refresh_update_status()
        else:
            self._update_controller.set_not_verified()

    def _finish_startup(self) -> None:
        self._startup_coordinator.finish_startup()

    def _apply_initial_setup_preferences(self, locale: str) -> None:
        self._locale = "fr" if locale == "fr" else "en"
        self._apply_locale()
        self._sync_store_preferences()

    def _sync_store_preferences(self) -> None:
        self._store.set_ui_preferences(
            locale=self._settings.language(),
            theme_preset=self._theme_manager.preference,
            reduce_motion=self._theme_manager.reduce_motion,
            update_checks_enabled=self._settings.automatic_update_checks(),
            pdf_opening_mode=self._settings.pdf_opening_mode(),
        )

    def _refresh_update_status(self) -> None:
        self._update_controller.refresh()

    def _start_manual_update_check(self, dialog: OptionsDialog) -> None:
        self._update_controller.start_manual_check(dialog)

    def _update_check_finished(self, result: UpdateCheckResult) -> None:
        self._update_controller.handle_finished(result)

    def _set_update_result(self, result: UpdateCheckResult) -> None:
        if self._is_closing:
            return
        self._latest_update_result = result
        self._sidebar.set_update_status(result.status)

    def _open_update_dialog(self) -> None:
        self._update_controller.open_dialog()

    def _strip_message_box_button_icons(self, dialog: QMessageBox) -> None:
        empty_icon = QIcon()
        for button in dialog.buttons():
            button.setIcon(empty_icon)

    def _update_status_text(self) -> str:
        return self._update_controller.status_text()

    def _update_result_text(self, result: UpdateCheckResult) -> str:
        return self._update_controller.result_text(result)

    @property
    def _latest_update_result(self) -> UpdateCheckResult | None:
        return self._update_controller.latest_result

    @_latest_update_result.setter
    def _latest_update_result(self, result: UpdateCheckResult | None) -> None:
        self._update_controller.set_latest_result(result)

    def _apply_locale(self) -> None:
        self._sidebar.set_locale(self._locale, get_display_version(self._locale))
        self._top_bar.set_locale(self._locale)
        for page in self._localized_pages:
            page.set_locale(self._locale)
        self._navigation_controller.refresh_title()

    def _current_key(self) -> str:
        return self._navigation_controller.current_key()

    def _page_title(self, key: str) -> str:
        if key == "dashboard":
            return tr("nav.dashboard", self._locale)
        if key == "community":
            return tr("community.title", self._locale)
        if key == "document":
            document = self._store.selected_document()
            if document is not None:
                return document.display_name
            return tr("document.title", self._locale)
        spec = TOOL_SPECS_BY_KEY[key]
        return tr(spec.title_key, self._locale)

    def _navigation_entries(self) -> list[NavigationEntry]:
        return [NavigationEntry("dashboard", "nav.dashboard", "document")]


def global_tool_switcher_specs() -> tuple[ToolSpec, ...]:
    return tuple(
        spec
        for spec in sorted(TOOL_SPECS, key=lambda item: item.order)
        if spec.status == "available"
    )


def workspace_compatible_tool_specs(document_count: int) -> tuple[ToolSpec, ...]:
    if document_count <= 0:
        return ()
    specs: list[ToolSpec] = []
    for spec in sorted(TOOL_SPECS, key=lambda item: item.order):
        if spec.status != "available":
            continue
        if spec.input_kind == "pdf_single" or (
            spec.input_kind == "pdf_multiple" and document_count >= 2
        ):
            specs.append(spec)
    return tuple(specs)
