from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStyle,
    QStyleOptionButton,
    QVBoxLayout,
    QWidget,
)

from priveopdf.app.app_info import is_beta_runtime
from priveopdf.ui.branding import PixelWordmark, build_app_icon
from priveopdf.ui.components.buttons import GhostButton, set_button_role
from priveopdf.ui.components.cards import ElidedLabel, LineIcon, StatusPill, SurfacePanel
from priveopdf.ui.i18n import Locale, tr
from priveopdf.ui.theme.tokens import PALETTES, SELECTABLE_THEME_PRESETS, SIZES, ThemeTokens
from priveopdf.ui.tool_specs import ToolSpec
from priveopdf.ui.workspace_state import (
    DEFAULT_WORKSPACE_NAME_PREFIX,
    MAX_WORKSPACES,
    WorkspaceDocument,
    WorkspaceInfo,
)


@dataclass(frozen=True)
class NavigationEntry:
    key: str
    label_key: str
    icon: str
    available: bool = True
    status: str = "available"


def _refresh_style(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def _current_tokens() -> ThemeTokens:
    app = QApplication.instance()
    preset = app.property("priveopdf_theme_preset") if app is not None else "dark_pro"
    if isinstance(preset, str):
        return PALETTES.get(preset, PALETTES["dark_pro"])
    mode = app.property("priveopdf_theme_mode") if app is not None else "dark"
    return PALETTES.get(mode, PALETTES["dark_pro"])


def _unisolated() -> bool:
    """F03: the explicit development switch removes the isolation; the promise
    block says so instead of "Privacy by design"."""
    from priveopdf.workers.process_supervisor import _unsandboxed_development_allowed

    return _unsandboxed_development_allowed()


def _privacy_badge(locale: Locale) -> tuple[str, str]:
    if _unisolated():
        return tr("local.badge_unisolated", locale), "warning"
    return tr("local.badge", locale), "success"


def _compact_privacy_text(locale: Locale) -> str:
    return _privacy_badge(locale)[0].replace(" BY ", "\nBY ").replace(" (", "\n(")


def _attach_centered_line_icon(
    button: QPushButton,
    icon_name: str,
    accent_role: str,
) -> LineIcon:
    icon = LineIcon(icon_name, accent_role, button)
    icon.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
    layout = QHBoxLayout(button)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    layout.addWidget(icon, 0, Qt.AlignmentFlag.AlignCenter)
    icon.setVisible(False)
    return icon


class UpdateStatusButton(QPushButton):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        set_button_role(self, "updateStatus")
        self._compact = False
        self._status_text = ""
        self._compact_icon = _attach_centered_line_icon(self, "refresh", "info")

    def set_status(self, text: str, status: str, tooltip: str) -> None:
        self._status_text = text
        self.setProperty("status", status)
        self._compact_icon.set_icon("refresh", status)
        self.setToolTip(tooltip)
        self._sync_display()

    def set_compact(self, compact: bool) -> None:
        self._compact = compact
        self.setProperty("compact", compact)
        self._sync_display()

    def _sync_display(self) -> None:
        self.setText("" if self._compact else self._status_text)
        self._compact_icon.setVisible(self._compact)
        _refresh_style(self)


class SidebarHandleButton(GhostButton):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent=parent)
        set_button_role(self, "sidebarToggle")
        self.setText("")
        self.setFixedSize(18, 64)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def paintEvent(self, event) -> None:  # noqa: ANN001
        super().paintEvent(event)
        tokens = _current_tokens()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        active = self.underMouse() or self.hasFocus()
        grip_color = QColor(tokens.color_text_secondary if active else tokens.color_text_muted)
        seam_color = QColor(tokens.color_border_active if active else tokens.color_border_default)
        painter.fillRect(self.width() - 2, 6, 2, max(0, self.height() - 12), seam_color)
        grip_width = max(6, self.width() - 9)
        x = max(3, (self.width() - grip_width) // 2)
        center_y = self.height() // 2
        for offset in (-10, 0, 10):
            painter.fillRect(x, center_y + offset, grip_width, 2, grip_color)


class WorkspaceDocumentItem(QWidget):
    selected = Signal(str)
    remove_requested = Signal(str)

    def __init__(
        self,
        document: WorkspaceDocument,
        active: bool,
        locale: Locale,
        parent: QWidget | None = None,
        *,
        show_folder: bool = False,
    ) -> None:
        super().__init__(parent)
        self._document_id = document.document_id
        self._locale = locale
        self._active = active
        self.setObjectName("WorkspaceDocumentItem")
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.DefaultContextMenu)

        self._button = _ElidedDocumentButton(*_workspace_button_parts(document, locale))
        set_button_role(self._button, "workspaceItem")
        self._button.setProperty("active", active)
        # Two PDFs of the same name from two folders stay distinguishable (E3).
        tooltip = document.display_name
        if show_folder:
            tooltip = f"{tooltip}\n{document.path.parent}"
        self._button.setToolTip(tooltip)
        self._button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._button.clicked.connect(lambda: self.selected.emit(self._document_id))
        self._button.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._button.customContextMenuRequested.connect(self._open_button_context_menu)

        self._remove_button = QPushButton("X")
        set_button_role(self._remove_button, "workspaceRemove")
        self._remove_button.setToolTip(tr("workspace.remove", locale))
        self._remove_button.clicked.connect(lambda: self.remove_requested.emit(self._document_id))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self._button, 1)
        layout.addWidget(self._remove_button)
        self._refresh_remove_visibility(False)

    def set_locale(self, locale: Locale) -> None:
        self._locale = locale
        self._remove_button.setToolTip(tr("workspace.remove", locale))

    def enterEvent(self, event) -> None:  # noqa: ANN001
        self._refresh_remove_visibility(True)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: ANN001
        self._refresh_remove_visibility(False)
        super().leaveEvent(event)

    def contextMenuEvent(self, event) -> None:  # noqa: ANN001, N802
        self._show_context_menu(event.globalPos())

    def _open_button_context_menu(self, pos) -> None:  # noqa: ANN001
        self._show_context_menu(self._button.mapToGlobal(pos))

    def _show_context_menu(self, global_pos) -> None:  # noqa: ANN001
        menu = QMenu(self)
        remove_action = menu.addAction(tr("workspace.remove", self._locale))
        selected_action = menu.exec(global_pos)
        if selected_action is remove_action:
            self.remove_requested.emit(self._document_id)

    def _refresh_remove_visibility(self, hovered: bool) -> None:
        self._remove_button.setVisible(self._active or hovered)


class _WorkspaceNameButton(QPushButton):
    double_clicked = Signal()

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: ANN001, N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.double_clicked.emit()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


class _WorkspaceNameEdit(QLineEdit):
    confirmed = Signal()
    cancelled = Signal()

    def keyPressEvent(self, event) -> None:  # noqa: ANN001, N802
        if event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
            self.confirmed.emit()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class WorkspaceCard(QFrame):
    selected = Signal(str)
    rename_requested = Signal(str, str)
    delete_requested = Signal(str)
    document_selected = Signal(str)
    document_remove_requested = Signal(str)

    def __init__(
        self,
        workspace: WorkspaceInfo,
        active: bool,
        locale: Locale,
        documents: tuple[WorkspaceDocument, ...] = (),
        selected_document_id: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._workspace_id = workspace.workspace_id
        self._workspace_name = workspace.name
        self._locale = locale
        self.setObjectName("WorkspaceCard")
        self.setProperty("active", active)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.DefaultContextMenu)

        self._button = _WorkspaceNameButton(_elide_name(workspace.name, 28))
        self._button.setMinimumWidth(1)
        set_button_role(self._button, "workspaceCard")
        self._button.setProperty("active", active)
        self._button.setToolTip(f"{workspace.name}\n{tr('workspace.card.tooltip', locale)}")
        self._button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._button.clicked.connect(lambda: self.selected.emit(self._workspace_id))
        self._button.double_clicked.connect(self._begin_edit)
        self._button.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._button.customContextMenuRequested.connect(self._open_button_context_menu)

        self._edit = _WorkspaceNameEdit(workspace.name)
        self._edit.setObjectName("WorkspaceNameEdit")
        self._edit.setVisible(False)
        self._edit.confirmed.connect(self._confirm_edit)
        self._edit.cancelled.connect(self._cancel_edit)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        layout.addWidget(self._button)
        layout.addWidget(self._edit)
        if active:
            if documents:
                name_counts = Counter(document.display_name for document in documents)
                for document in documents:
                    item = WorkspaceDocumentItem(
                        document,
                        document.document_id == selected_document_id,
                        locale,
                        show_folder=name_counts[document.display_name] > 1,
                    )
                    item.selected.connect(self.document_selected.emit)
                    item.remove_requested.connect(self.document_remove_requested.emit)
                    layout.addWidget(item)
            else:
                empty_label = QLabel(tr("sidebar.workspace.empty", locale))
                empty_label.setObjectName("WorkspaceEmpty")
                empty_label.setWordWrap(True)
                layout.addWidget(empty_label)

    def _begin_edit(self) -> None:
        self._edit.setText(self._workspace_name)
        self._button.setVisible(False)
        self._edit.setVisible(True)
        self._edit.setFocus(Qt.FocusReason.MouseFocusReason)
        self._edit.selectAll()

    def contextMenuEvent(self, event) -> None:  # noqa: ANN001, N802
        self._show_context_menu(event.globalPos())

    def _open_button_context_menu(self, pos) -> None:  # noqa: ANN001
        self._show_context_menu(self._button.mapToGlobal(pos))

    def _show_context_menu(self, global_pos) -> None:  # noqa: ANN001
        menu, rename_action, delete_action = self._build_context_menu()
        selected_action = menu.exec(global_pos)
        if selected_action is rename_action:
            self._begin_edit()
        elif selected_action is delete_action:
            self.delete_requested.emit(self._workspace_id)

    def _build_context_menu(self) -> tuple[QMenu, object, object]:
        menu = QMenu(self)
        rename_action = menu.addAction(tr("workspace.rename", self._locale))
        menu.addSeparator()
        delete_action = menu.addAction(tr("workspace.delete", self._locale))
        return menu, rename_action, delete_action

    def _confirm_edit(self) -> None:
        name = self._edit.text().strip() or self._workspace_name
        self._button.setVisible(True)
        self._edit.setVisible(False)
        self.rename_requested.emit(self._workspace_id, name)

    def _cancel_edit(self) -> None:
        self._edit.setText(self._workspace_name)
        self._button.setVisible(True)
        self._edit.setVisible(False)


class Sidebar(QFrame):
    navigation_requested = Signal(str)
    community_requested = Signal()
    options_requested = Signal()
    update_check_requested = Signal()
    sidebar_collapsed_changed = Signal(bool)
    workspace_create_requested = Signal()
    workspace_requested = Signal(str)
    workspace_rename_requested = Signal(str, str)
    workspace_delete_requested = Signal(str)
    workspace_document_requested = Signal(str)
    workspace_document_remove_requested = Signal(str)
    workspace_tool_requested = Signal(str)

    def __init__(
        self,
        entries: list[NavigationEntry],
        locale: Locale,
        version_text: str,
        workspaces: tuple[WorkspaceInfo, ...] = (),
        active_workspace_id: str | None = None,
        workspace_documents: tuple[WorkspaceDocument, ...] = (),
        selected_document_id: str | None = None,
        collapsed: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self._entries = entries
        self._locale = locale
        self._version_text = version_text
        self._workspaces = workspaces
        self._active_workspace_id = active_workspace_id
        self._workspace_documents = workspace_documents
        self._selected_document_id = selected_document_id
        self._collapsed = False
        self._update_status = "not_verified"
        self._buttons: dict[str, QPushButton] = {}

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(18, 22, 18, 18)
        self._layout.setSpacing(12)

        brand_row = QHBoxLayout()
        brand_row.setContentsMargins(0, 0, 0, 0)
        brand_row.setSpacing(8)
        self._wordmark = PixelWordmark(compact=True)
        self._beta_runtime = is_beta_runtime()
        self._compact_logo = GhostButton()
        self._compact_logo.setObjectName("SidebarLogoCompact")
        self._compact_logo.setIcon(build_app_icon())
        self._compact_logo.setIconSize(QSize(SIZES["icon_button"], SIZES["icon_button"]))
        self._compact_logo.setCursor(Qt.CursorShape.PointingHandCursor)
        self._compact_logo.clicked.connect(self._expand_from_compact_action)
        self._set_compact_brand_accessibility(locale)
        self._toggle_button = SidebarHandleButton(self)
        self._toggle_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_button.clicked.connect(self._toggle_collapsed)
        brand_row.addWidget(self._wordmark, 1)
        brand_row.addWidget(self._compact_logo, 1)
        self._layout.addLayout(brand_row)

        self._layout.addSpacing(12)
        for entry in entries:
            button = QPushButton()
            set_button_role(button, "nav")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setProperty("active", False)
            button.setProperty("pending", False)
            button.clicked.connect(
                lambda checked=False, key=entry.key: self.navigation_requested.emit(key)
            )
            self._buttons[entry.key] = button
            self._layout.addWidget(button)

        workspace_title_row = QHBoxLayout()
        workspace_title_row.setContentsMargins(0, 0, 0, 0)
        workspace_title_row.setSpacing(8)
        self._workspace_title = QLabel()
        self._workspace_title.setObjectName("SidebarSectionTitle")
        self._new_workspace_button = QPushButton()
        set_button_role(self._new_workspace_button, "workspaceNew")
        self._new_workspace_button.clicked.connect(self.workspace_create_requested.emit)
        workspace_title_row.addWidget(self._workspace_title, 1)
        workspace_title_row.addWidget(self._new_workspace_button)
        self._layout.addLayout(workspace_title_row)

        self._workspace_panel = QWidget()
        self._workspace_panel.setObjectName("WorkspaceStack")
        self._workspace_panel.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        workspace_layout = QVBoxLayout(self._workspace_panel)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        workspace_layout.setSpacing(8)
        self._workspace_cards_host = QWidget()
        self._workspace_cards_host.setObjectName("WorkspaceCards")
        self._workspace_cards_host.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._workspace_cards_layout = QVBoxLayout(self._workspace_cards_host)
        self._workspace_cards_layout.setContentsMargins(0, 0, 0, 0)
        self._workspace_cards_layout.setSpacing(6)
        self._workspace_action_label = QLabel()
        self._workspace_action_label.setObjectName("MutedText")
        self._workspace_tool_combo = QComboBox()
        self._workspace_tool_combo.setObjectName("WorkspaceToolCombo")
        self._workspace_tool_combo.currentIndexChanged.connect(self._workspace_tool_index_changed)
        # L3: the cards keep their height and scroll; nothing is squeezed or overlaps.
        self._workspace_cards_host.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )
        self._workspace_scroll = QScrollArea()
        self._workspace_scroll.setObjectName("WorkspaceScroll")
        self._workspace_scroll.setWidgetResizable(True)
        self._workspace_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._workspace_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._workspace_scroll.setWidget(self._workspace_cards_host)
        self._workspace_scroll.viewport().setObjectName("WorkspaceScrollViewport")
        workspace_layout.addWidget(self._workspace_scroll, 1)
        workspace_layout.addWidget(self._workspace_action_label)
        workspace_layout.addWidget(self._workspace_tool_combo)
        # The list takes the free height; the stretch below only matters without it.
        self._layout.addWidget(self._workspace_panel, 100)

        self._workspace_compact_button = QPushButton()
        set_button_role(self._workspace_compact_button, "nav")
        self._workspace_compact_button.setAccessibleName(tr("sidebar.workspace.tooltip", locale))
        self._workspace_compact_button.clicked.connect(self._expand_from_compact_action)
        self._layout.addWidget(self._workspace_compact_button)

        self._layout.addStretch(1)

        meta_row = QHBoxLayout()
        meta_row.setContentsMargins(0, 0, 0, 0)
        meta_row.setSpacing(8)
        self._options_button = GhostButton()
        set_button_role(self._options_button, "meta")
        self._options_icon = _attach_centered_line_icon(
            self._options_button,
            "settings",
            "primary",
        )
        self._options_button.clicked.connect(self.options_requested.emit)
        self._version_label = QLabel(version_text)
        self._version_label.setObjectName("VersionText")
        self._version_label.setWordWrap(False)
        meta_row.addWidget(self._options_button)
        meta_row.addWidget(self._version_label, 1)

        self._community_button = GhostButton()
        set_button_role(self._community_button, "nav")
        self._community_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._community_button.clicked.connect(self.community_requested.emit)
        self._layout.addWidget(self._community_button)

        self._local_panel = SurfacePanel(soft=True, role="success")
        local_layout = QVBoxLayout(self._local_panel)
        local_layout.setContentsMargins(12, 12, 12, 12)
        local_layout.setSpacing(8)
        self._local_pill = StatusPill(*_privacy_badge(locale))
        local_layout.addWidget(self._local_pill)
        self._local_note = QLabel(tr("local.note", locale))
        self._local_note.setObjectName("HelpText")
        self._local_note.setWordWrap(True)
        local_layout.addWidget(self._local_note)
        self._layout.addWidget(self._local_panel)

        self._update_button = UpdateStatusButton()
        self._update_icon = self._update_button._compact_icon
        self._update_button.clicked.connect(self.update_check_requested.emit)
        self._update_button.setVisible(not self._beta_runtime)
        self._layout.addWidget(self._update_button)
        self._layout.addLayout(meta_row)

        self._local_compact_panel = SurfacePanel(soft=True, role="success")
        compact_local_layout = QVBoxLayout(self._local_compact_panel)
        compact_local_layout.setContentsMargins(6, 6, 6, 6)
        compact_local_layout.setSpacing(4)
        compact_local_layout.addWidget(
            LineIcon("shield", "success"),
            0,
            Qt.AlignmentFlag.AlignCenter,
        )
        self._local_compact_label = QLabel(_compact_privacy_text(locale))
        self._local_compact_label.setObjectName("StatusPillText")
        self._local_compact_label.setProperty("status", "success")
        self._local_compact_label.setProperty("compact", True)
        self._local_compact_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._local_compact_label.setWordWrap(True)
        self._local_compact_label.setAccessibleName(tr("local.badge", locale))
        compact_local_layout.addWidget(
            self._local_compact_label,
            0,
            Qt.AlignmentFlag.AlignCenter,
        )
        self._layout.addWidget(self._local_compact_panel)

        self.set_workspaces(workspaces, active_workspace_id)
        self.set_workspace_documents(workspace_documents, selected_document_id)
        self.set_locale(locale, version_text)
        self.set_collapsed(collapsed)

    def set_active(self, key: str) -> None:
        for entry_key, button in self._buttons.items():
            button.setProperty("active", entry_key == key)
            _refresh_style(button)
        self._community_button.setProperty("active", key == "community")
        _refresh_style(self._community_button)

    def set_update_status(self, status: str) -> None:
        self._update_status = status
        semantic_status = {
            "up_to_date": "success",
            "update_available": "warning",
            "checking": "info",
            "not_verified": "info",
            "disabled": "info",
            "not_configured": "info",
        }.get(status, "info")
        action_key = {
            "checking": "update.action.checking",
            "up_to_date": "update.action.up_to_date",
            "update_available": "update.action.available",
        }.get(status, "update.action.check")
        tooltip_key = {
            "checking": "update.manual.tooltip.checking",
            "up_to_date": "update.manual.tooltip.up_to_date",
            "update_available": "update.manual.tooltip.update_available",
            "not_configured": "update.manual.tooltip.not_configured",
        }.get(status, "update.manual.tooltip")
        text = tr(action_key, self._locale)
        self._update_button.set_status(
            text,
            semantic_status,
            tr(tooltip_key, self._locale),
        )
        self._update_button.setAccessibleName(text)
        self._update_button.setEnabled(not self._beta_runtime and status != "checking")

    def set_locale(self, locale: Locale, version_text: str) -> None:
        self._locale = locale
        self._version_text = version_text
        for entry in self._entries:
            button = self._buttons[entry.key]
            button.setToolTip(_navigation_tooltip(entry, locale))
        self._workspace_title.setText(tr("sidebar.workspace", locale))
        self._workspace_compact_button.setToolTip(tr("sidebar.workspace.tooltip", locale))
        self._workspace_compact_button.setAccessibleName(tr("sidebar.workspace.tooltip", locale))
        self._workspace_action_label.setText(tr("workspace.use_with", locale))
        self._new_workspace_button.setText("+")
        self._options_button.setToolTip(tr("options", locale))
        self._options_button.setAccessibleName(tr("options", locale))
        self._community_button.setToolTip(tr("sidebar.community.tooltip", locale))
        self._community_button.setAccessibleName(tr("community.title", locale))
        self._version_label.setText(version_text)
        badge, status = _privacy_badge(locale)
        self._local_pill.set_status(badge, status)
        self._local_note.setText(
            tr("local.note_unisolated" if _unisolated() else "local.note", locale)
        )
        self._local_compact_label.setText(_compact_privacy_text(locale))
        self._local_compact_label.setProperty("status", status)
        self._local_compact_label.setAccessibleName(badge)
        self.set_update_status(self._update_status)
        self._local_panel.setToolTip(tr("sidebar.local.tooltip", locale))
        self._local_compact_panel.setToolTip(tr("sidebar.local.tooltip", locale))
        self._set_compact_brand_accessibility(locale)
        self._apply_collapsed_texts()
        self.set_workspaces(self._workspaces, self._active_workspace_id)
        self.set_workspace_documents(self._workspace_documents, self._selected_document_id)

    def _set_compact_brand_accessibility(self, locale: Locale) -> None:
        brand_name = self._wordmark.accessibleName()
        self._compact_logo.setToolTip(f"{brand_name} — {tr('sidebar.expand', locale)}")
        self._compact_logo.setAccessibleName(brand_name)

    def set_workspaces(
        self,
        workspaces: tuple[WorkspaceInfo, ...],
        active_workspace_id: str | None,
    ) -> None:
        self._workspaces = workspaces
        self._active_workspace_id = active_workspace_id
        self._render_workspace_cards()
        self._refresh_workspace_create_state()
        self._refresh_workspace_visibility()

    def _render_workspace_cards(self, *, force: bool = False) -> None:
        # Each page count and every view refresh used to rebuild all cards, which
        # flickered with many documents (audit 26/10): rebuild only on a change.
        key = (
            self._workspaces,
            self._active_workspace_id,
            self._workspace_documents,
            self._selected_document_id,
            self._locale,
        )
        if not force and key == getattr(self, "_rendered_cards_key", None):
            return
        self._rendered_cards_key = key
        self._clear_workspace_cards()
        for workspace in self._workspaces:
            active = workspace.workspace_id == self._active_workspace_id
            card = WorkspaceCard(
                workspace,
                active,
                self._locale,
                self._workspace_documents if active else (),
                self._selected_document_id if active else None,
            )
            card.selected.connect(self.workspace_requested.emit)
            card.rename_requested.connect(self.workspace_rename_requested.emit)
            card.delete_requested.connect(self.workspace_delete_requested.emit)
            card.document_selected.connect(self.workspace_document_requested.emit)
            card.document_remove_requested.connect(self.workspace_document_remove_requested.emit)
            self._workspace_cards_layout.addWidget(card)
        self._workspace_cards_layout.addStretch(1)

    def set_workspace_documents(
        self,
        documents: tuple[WorkspaceDocument, ...],
        selected_document_id: str | None = None,
    ) -> None:
        self._workspace_documents = documents
        self._selected_document_id = selected_document_id
        self._render_workspace_cards()
        self._refresh_workspace_actions()
        self._refresh_workspace_visibility()

    def _refresh_workspace_visibility(self) -> None:
        has_documents = bool(self._workspace_documents) or any(
            workspace.documents for workspace in self._workspaces
        )
        has_useful_workspace = len(self._workspaces) > 1 or any(
            workspace.name != f"{DEFAULT_WORKSPACE_NAME_PREFIX} 1" for workspace in self._workspaces
        )
        show_workspaces = has_documents or has_useful_workspace
        expanded = show_workspaces and not self._collapsed
        self._workspace_title.setVisible(expanded)
        self._new_workspace_button.setVisible(expanded)
        self._workspace_panel.setVisible(expanded)
        self._workspace_compact_button.setVisible(show_workspaces and self._collapsed)

    def set_collapsed(self, collapsed: bool) -> None:
        self._collapsed = collapsed
        self.setProperty("collapsed", collapsed)
        self.setFixedWidth(SIZES["sidebar_collapsed"] if collapsed else SIZES["sidebar"])
        if collapsed:
            self._layout.setContentsMargins(8, 16, 36, 14)
            self._layout.setSpacing(10)
        else:
            self._layout.setContentsMargins(18, 22, 18, 18)
            self._layout.setSpacing(12)

        self._wordmark.setVisible(not collapsed)
        self._compact_logo.setVisible(collapsed)
        self._refresh_workspace_visibility()
        self._version_label.setVisible(not collapsed)
        self._local_panel.setVisible(not collapsed)
        self._local_compact_panel.setVisible(collapsed)
        self._apply_collapsed_texts()
        self._position_toggle_handle()
        _refresh_style(self)

    def resizeEvent(self, event) -> None:  # noqa: ANN001, N802
        super().resizeEvent(event)
        self._position_toggle_handle()

    def _toggle_collapsed(self) -> None:
        self.set_collapsed(not self._collapsed)
        self.sidebar_collapsed_changed.emit(self._collapsed)

    def _expand_from_compact_action(self) -> None:
        if self._collapsed:
            self.set_collapsed(False)
            self.sidebar_collapsed_changed.emit(False)

    def _apply_collapsed_texts(self) -> None:
        for entry in self._entries:
            button = self._buttons[entry.key]
            key = f"{entry.label_key}.compact" if self._collapsed else entry.label_key
            text = tr(key, self._locale)
            button.setText(text if self._collapsed else text.upper())
            button.setAccessibleName(_navigation_tooltip(entry, self._locale))
            button.setProperty("compact", self._collapsed)
            _refresh_style(button)

        self._toggle_button.setText("")
        self._toggle_button.setToolTip(
            tr("sidebar.expand" if self._collapsed else "sidebar.collapse", self._locale)
        )
        self._toggle_button.setAccessibleName(self._toggle_button.toolTip())
        self._toggle_button.setProperty("compact", self._collapsed)
        _refresh_style(self._toggle_button)

        self._options_button.setText("" if self._collapsed else tr("options", self._locale))
        self._options_icon.setVisible(self._collapsed)
        self._options_button.setProperty("compact", self._collapsed)
        _refresh_style(self._options_button)

        self._update_button.set_compact(self._collapsed)

        self._community_button.setText(
            tr(
                "sidebar.community.compact" if self._collapsed else "sidebar.community",
                self._locale,
            )
        )
        self._community_button.setProperty("compact", self._collapsed)
        _refresh_style(self._community_button)

        self._workspace_compact_button.setText(self._workspace_compact_text())
        self._workspace_compact_button.setToolTip(
            tr("sidebar.workspace.show_tooltip", self._locale)
        )
        self._workspace_compact_button.setAccessibleName(
            tr("sidebar.workspace.show_tooltip", self._locale)
        )
        self._workspace_compact_button.setProperty("compact", self._collapsed)
        _refresh_style(self._workspace_compact_button)

    def _position_toggle_handle(self) -> None:
        x = max(0, self.width() - self._toggle_button.width())
        y = 70 if self._collapsed else 82
        max_y = max(0, self.height() - self._toggle_button.height() - 18)
        self._toggle_button.move(x, min(y, max_y))
        self._toggle_button.raise_()

    def _workspace_document_count(self) -> int:
        return sum(len(workspace.documents) for workspace in self._workspaces)

    def _workspace_compact_text(self) -> str:
        count = self._workspace_document_count()
        key = "sidebar.workspace.compact_single" if count == 1 else "sidebar.workspace.compact"
        return tr(key, self._locale)

    def _clear_workspace_cards(self) -> None:
        while self._workspace_cards_layout.count():
            item = self._workspace_cards_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    def _refresh_workspace_actions(self) -> None:
        self._workspace_action_label.setVisible(False)
        self._workspace_tool_combo.setVisible(False)
        self._workspace_tool_combo.blockSignals(True)
        self._workspace_tool_combo.clear()
        self._workspace_tool_combo.addItem(tr("workspace.use_with.placeholder", self._locale), "")
        self._workspace_tool_combo.blockSignals(False)

    def _refresh_workspace_create_state(self) -> None:
        can_create = len(self._workspaces) < MAX_WORKSPACES
        self._new_workspace_button.setEnabled(can_create)
        tooltip_key = "workspace.new" if can_create else "workspace.limit_reached"
        self._new_workspace_button.setToolTip(
            tr(tooltip_key, self._locale, max_count=MAX_WORKSPACES)
        )

    def set_workspace_tools(self, specs: tuple[ToolSpec, ...]) -> None:
        current_data = self._workspace_tool_combo.currentData()
        self._workspace_tool_combo.blockSignals(True)
        self._workspace_tool_combo.clear()
        self._workspace_tool_combo.addItem(
            tr("workspace.use_with.placeholder", self._locale),
            "",
        )
        for spec in specs:
            self._workspace_tool_combo.addItem(tr(spec.title_key, self._locale), spec.route_key)
        if isinstance(current_data, str):
            for index in range(self._workspace_tool_combo.count()):
                if self._workspace_tool_combo.itemData(index) == current_data:
                    self._workspace_tool_combo.setCurrentIndex(index)
                    break
        self._workspace_tool_combo.blockSignals(False)
        self._workspace_action_label.setVisible(False)
        self._workspace_tool_combo.setVisible(False)

    def _workspace_tool_index_changed(self, index: int) -> None:
        key = self._workspace_tool_combo.itemData(index)
        if not isinstance(key, str) or not key:
            return
        self._workspace_tool_combo.blockSignals(True)
        self._workspace_tool_combo.setCurrentIndex(0)
        self._workspace_tool_combo.blockSignals(False)
        self.workspace_tool_requested.emit(key)


class TopBar(QFrame):
    toggle_theme_requested = Signal()
    about_requested = Signal()
    tool_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("TopBar")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 14, 24, 14)
        layout.setSpacing(12)

        title_box = QVBoxLayout()
        title_box.setContentsMargins(0, 0, 0, 0)
        title_box.setSpacing(2)
        # A long file name is shortened in the middle; the full name stays in the tooltip.
        self._title = ElidedLabel("Accueil")
        self._title.setObjectName("PageTitle")
        title_box.addWidget(self._title)
        layout.addLayout(title_box, 1)

        self._tools_button = GhostButton()
        self._tools_button.clicked.connect(self.open_tools_menu)
        layout.addWidget(self._tools_button)

        self._about_button = GhostButton()
        self._about_button.clicked.connect(self.about_requested.emit)
        layout.addWidget(self._about_button)

        self._theme_button = GhostButton("MODE CLAIR")
        self._theme_button.clicked.connect(self.toggle_theme_requested.emit)
        layout.addWidget(self._theme_button)
        self._preset = "dark_pro"
        self._locale: Locale = "en"
        self._tool_specs: tuple[ToolSpec, ...] = ()

    def set_title(self, title: str, *, uppercase: bool = True) -> None:
        self._title.setText(title.upper() if uppercase else title)

    def set_theme_preset(self, preset: str) -> None:
        self._preset = preset if preset in _THEME_PRESETS else "dark_pro"
        brightness = "light" if self._preset.startswith("light_") else "dark"
        key = "mode.dark.action" if brightness == "light" else "mode.light.action"
        self._theme_button.setText(tr(key, self._locale))

    def set_theme_mode(self, mode: str) -> None:
        self.set_theme_preset("light_pro" if mode == "light" else "dark_pro")

    def set_locale(self, locale: Locale) -> None:
        self._locale = locale
        self._tools_button.setText(tr("tool_switcher.button", locale))
        self._tools_button.setToolTip(tr("tool_switcher.label", locale))
        self._tools_button.setAccessibleName(tr("tool_switcher.label", locale))
        self._about_button.setText(tr("about.title", locale))
        self._about_button.setToolTip(tr("about.tooltip", locale))
        self.set_theme_preset(self._preset)

    def set_tool_specs(self, specs: tuple[ToolSpec, ...]) -> None:
        self._tool_specs = specs

    def open_tools_menu(self) -> None:
        menu = QMenu(self)
        all_tools_action = menu.addAction(tr("tool_switcher.all", self._locale))
        all_tools_action.setData("dashboard")
        if self._tool_specs:
            menu.addSeparator()
        for spec in self._tool_specs:
            action = menu.addAction(tr(spec.title_key, self._locale).upper())
            action.setData(spec.route_key)

        selected_action = menu.exec(
            self._tools_button.mapToGlobal(self._tools_button.rect().bottomLeft())
        )
        if selected_action is None:
            return
        key = selected_action.data()
        if isinstance(key, str) and key:
            self.tool_requested.emit(key)


def _elide_name(name: str, max_chars: int = 24) -> str:
    if len(name) <= max_chars:
        return name
    keep = max(4, (max_chars - 3) // 2)
    return f"{name[:keep]}...{name[-keep:]}"


def _workspace_button_parts(document: WorkspaceDocument, locale: Locale) -> tuple[str, str]:
    name = document.display_name
    if document.page_count_status == "ready" and document.page_count is not None:
        return name, f" [{document.page_count}p]"
    if document.page_count_status == "loading":
        return name, " [...]"
    if document.page_count_status == "locked":
        return name, f" [{tr('document.status.locked', locale)}]"
    if document.page_count_status == "error":
        return name, " [!]"
    return name, ""


def elide_file_name(name: str, width: int, advance: Callable[[str], int]) -> str:
    """Shorten a file name to `width` (L3): start and extension kept, the end favoured.

    Derived files share their start (`report.pdf`, `report_sans-pages.pdf`): the
    end of the stem, where tools add their suffix, gets three fifths of the room.
    """

    if advance(name) <= width:
        return name
    stem, dot, extension = name.rpartition(".")
    if not dot or not stem:
        stem, extension = name, ""
    tail_extension = f".{extension}" if extension else ""
    for visible in range(len(stem) - 1, 1, -1):
        end = max(1, (visible * 3 + 4) // 5)
        start = visible - end
        candidate = f"{stem[:start]}…{stem[-end:]}{tail_extension}"
        if advance(candidate) <= width:
            return candidate
    return f"…{tail_extension}" if advance(f"…{tail_extension}") <= width else "…"


class _ElidedDocumentButton(QPushButton):
    """Document name shortened to the real width; the page-count suffix stays visible."""

    def __init__(self, name: str, suffix: str, parent: QWidget | None = None) -> None:
        super().__init__(name + suffix, parent)
        self._name = name
        self._suffix = suffix
        self.setMinimumWidth(0)

    def full_text(self) -> str:
        return self._name + self._suffix

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        # L3: the name shortens to the column, so the button never widens it.
        hint = super().minimumSizeHint()
        metrics = self.fontMetrics()
        return QSize(metrics.horizontalAdvance(f"…{self._suffix}") + 24, hint.height())

    def resizeEvent(self, event) -> None:  # noqa: ANN001, N802
        super().resizeEvent(event)
        self._refresh_text()

    def changeEvent(self, event) -> None:  # noqa: ANN001, N802
        super().changeEvent(event)
        self._refresh_text()

    def _refresh_text(self) -> None:
        option = QStyleOptionButton()
        self.initStyleOption(option)
        contents = self.style().subElementRect(
            QStyle.SubElement.SE_PushButtonContents, option, self
        )
        metrics = self.fontMetrics()
        available = contents.width() - metrics.horizontalAdvance(self._suffix)
        name = elide_file_name(self._name, max(available, 0), metrics.horizontalAdvance)
        text = name + self._suffix
        if text != self.text():
            QPushButton.setText(self, text)


def _navigation_tooltip(entry: NavigationEntry, locale: Locale) -> str:
    tooltip_key = f"{entry.label_key}.tooltip"
    tooltip = tr(tooltip_key, locale)
    return tooltip if tooltip != tooltip_key else tr(entry.label_key, locale)


_THEME_PRESETS = set(SELECTABLE_THEME_PRESETS)
