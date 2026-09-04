from __future__ import annotations

from pdfmod.ui.theme.tokens import (
    BORDER_WIDTH_PIXEL,
    FONT_FAMILY,
    FONT_MONO,
    RADIUS,
    SIZES,
    SPACING,
    ThemeTokens,
)


def build_stylesheet(tokens: ThemeTokens) -> str:
    is_pixel = tokens.visual_style == "pixel"
    accent = tokens.color_border_active
    permanent_accent = tokens.color_pixel_blue if is_pixel else tokens.color_border_default
    primary_border = tokens.color_pixel_blue if is_pixel else accent
    primary_bottom = tokens.color_pixel_red if is_pixel else accent
    primary_right = tokens.color_pixel_yellow if is_pixel else accent
    active_left = tokens.color_pixel_red if is_pixel else accent
    active_bottom = tokens.color_pixel_yellow if is_pixel else tokens.color_border_default
    menu_bottom = tokens.color_pixel_yellow if is_pixel else tokens.color_border_default
    menu_right = tokens.color_pixel_blue if is_pixel else tokens.color_border_default
    selected_left = tokens.color_pixel_red if is_pixel else accent
    zoom_bottom = tokens.color_pixel_yellow if is_pixel else tokens.color_border_default
    zoom_right = tokens.color_pixel_blue if is_pixel else tokens.color_border_default
    required_border = tokens.color_pixel_blue if is_pixel else accent
    required_bottom = tokens.color_pixel_yellow if is_pixel else accent
    required_right = tokens.color_pixel_orange if is_pixel else accent
    return f"""
* {{
    font-family: {FONT_FAMILY};
    font-size: 14px;
    outline: none;
}}

QWidget {{
    background: {tokens.color_bg_main};
    color: {tokens.color_text_main};
}}

QMainWindow, #AppShell {{
    background: {tokens.color_bg_main};
}}

QLabel {{
    color: {tokens.color_text_secondary};
    background: transparent;
}}

QLabel#AppTitle, QLabel#PageTitle, QLabel#DashboardTitle {{
    color: {tokens.color_text_main};
    font-size: 24px;
    font-weight: 800;
    font-family: {FONT_MONO};
}}

QLabel#PageTitle {{
    font-size: 22px;
}}

QLabel#SectionTitle {{
    color: {tokens.color_text_main};
    font-size: 15px;
    font-weight: 800;
    font-family: {FONT_MONO};
}}

QLabel#OutputFileName {{
    color: {tokens.color_text_main};
    font-size: 15px;
    font-weight: 800;
}}

QLabel#MutedText, QLabel#HelpText {{
    color: {tokens.color_text_muted};
}}

QLabel#VersionText {{
    color: {tokens.color_text_muted};
    font-size: 10px;
    font-weight: 800;
    font-family: {FONT_MONO};
}}

QLabel#SidebarLogoCompact {{
    color: {tokens.color_text_main};
    background: {tokens.color_bg_surface};
    border: {BORDER_WIDTH_PIXEL}px solid {tokens.color_pixel_blue};
    border-bottom-color: {tokens.color_pixel_red};
    border-right-color: {tokens.color_pixel_yellow};
    font-size: 13px;
    font-weight: 800;
    padding: {SPACING["sm"]}px 0;
}}

QLabel#SidebarSectionTitle {{
    color: {tokens.color_text_muted};
    font-size: 12px;
    font-weight: 800;
    font-family: {FONT_MONO};
    padding-top: {SPACING["sm"]}px;
}}

QLabel#WorkspaceEmpty {{
    color: {tokens.color_text_muted};
    font-size: 12px;
    font-weight: 800;
}}

QLabel#PendingBadge {{
    color: {tokens.color_warning};
    background: {tokens.color_warning_bg};
    border: {BORDER_WIDTH_PIXEL}px solid {tokens.color_warning_border};
    border-radius: {RADIUS["none"]}px;
    padding: {SPACING["xs"]}px {SPACING["sm"]}px;
    font-size: 11px;
    font-weight: 800;
    font-family: {FONT_MONO};
}}

QLabel#StatusText {{
    color: {tokens.color_text_secondary};
    border-left: {BORDER_WIDTH_PIXEL}px solid {tokens.color_info_border};
    padding: {SPACING["sm"]}px {SPACING["md"]}px;
    background: {tokens.color_info_bg};
}}

QLabel#PdfPreviewCanvas {{
    color: {tokens.color_text_muted};
    background: {tokens.color_bg_alt};
    border: {BORDER_WIDTH_PIXEL}px solid {tokens.color_border_default};
    border-radius: {RADIUS["pixel"]}px;
    padding: {SPACING["md"]}px;
    font-weight: 800;
}}

QLabel#DropZoneState {{
    color: {tokens.color_text_muted};
    font-weight: 800;
}}

QLabel#DropZoneState[status="success"] {{
    color: {tokens.color_success};
}}

QLabel#DropZoneState[status="danger"] {{
    color: {tokens.color_danger};
}}

QLabel#DropZoneState[status="info"] {{
    color: {tokens.color_info};
}}

QLabel#ViewerZoomValue {{
    min-width: 56px;
    min-height: 32px;
    color: {tokens.color_text_secondary};
    background: {tokens.color_bg_alt};
    border: {BORDER_WIDTH_PIXEL}px solid {tokens.color_border_default};
    border-radius: {RADIUS["pixel"]}px;
    padding: {SPACING["xs"]}px {SPACING["sm"]}px;
    font-family: {FONT_MONO};
    font-weight: 800;
}}

QComboBox#ZoomPercentCombo {{
    color: {tokens.color_text_main};
    background: {tokens.color_bg_surface};
    border: {BORDER_WIDTH_PIXEL}px solid {tokens.color_border_default};
    border-bottom-color: {zoom_bottom};
    border-right-color: {zoom_right};
    border-radius: {RADIUS["pixel"]}px;
    padding: {SPACING["sm"]}px {SPACING["md"]}px;
    font-weight: 800;
    selection-background-color: {tokens.color_info_bg};
}}

QComboBox#RotationAngleCombo {{
    min-height: 32px;
    font-weight: 800;
}}

QSpinBox#PageNumberSpinBox {{
    min-width: 96px;
    max-width: 120px;
    min-height: 32px;
    padding: {SPACING["xs"]}px {SPACING["sm"]}px;
    font-weight: 800;
    font-family: {FONT_MONO};
}}

QSpinBox#PageNumberSpinBox:hover {{
    background: {tokens.color_bg_surface_hover};
    border-color: {accent};
}}

QSpinBox#PageNumberSpinBox:disabled {{
    color: {tokens.color_text_muted};
    background: {tokens.color_bg_alt};
    border-color: {tokens.color_border_default};
}}

QFrame#Sidebar {{
    background: {tokens.color_bg_rail};
    border-right: {BORDER_WIDTH_PIXEL}px solid {tokens.color_border_default};
}}

QFrame#Sidebar[collapsed="true"] {{
    border-right-color: {permanent_accent};
}}

QFrame#TopBar {{
    background: {tokens.color_bg_alt};
    border-bottom: {BORDER_WIDTH_PIXEL}px solid {tokens.color_border_default};
}}

QFrame#Panel, QFrame#PanelSoft, QFrame#TrustPanel, QFrame#ProgressOverlay {{
    background: {tokens.color_bg_surface};
    border: {BORDER_WIDTH_PIXEL}px solid {tokens.color_border_default};
    border-radius: {RADIUS["card"]}px;
}}

QFrame#PanelSoft {{
    background: {tokens.color_bg_rail};
}}

QWidget#WorkspaceStack {{
    background: transparent;
    border: none;
}}

QWidget#WorkspaceCards {{
    background: transparent;
    border: none;
}}

QAbstractButton#ToolCard {{
    background: {tokens.color_bg_surface};
    border: {BORDER_WIDTH_PIXEL}px solid {tokens.color_border_default};
    border-radius: {RADIUS["card"]}px;
}}

QAbstractButton#ToolCard[active="true"], QAbstractButton#ToolCard:hover,
QAbstractButton#ToolCard:focus, QAbstractButton#ToolCard:pressed {{
    background: {tokens.color_bg_surface_hover};
    border-color: {accent};
}}

QAbstractButton#ToolCard[disabled="true"] {{
    background: {tokens.color_bg_alt};
    border-color: {tokens.color_warning_border};
}}

QFrame#StatusPill {{
    background: {tokens.color_info_bg};
    border: {BORDER_WIDTH_PIXEL}px solid {tokens.color_info_border};
    border-radius: {RADIUS["pixel"]}px;
}}

QFrame#StatusPill[status="success"] {{
    background: {tokens.color_success_bg};
    border-color: {tokens.color_success_border};
}}

QFrame#StatusPill[status="warning"] {{
    background: {tokens.color_warning_bg};
    border-color: {tokens.color_warning_border};
}}

QFrame#StatusPill[status="danger"] {{
    background: {tokens.color_danger_bg};
    border-color: {tokens.color_danger_border};
}}

QFrame#StatusPill[status="info"] {{
    background: {tokens.color_info_bg};
    border-color: {tokens.color_info_border};
}}

QFrame#StatusPill[compact="true"] {{
    border-width: 1px;
}}

QLabel#StatusPillText {{
    color: {tokens.color_info};
    font-weight: 800;
}}

QLabel#StatusPillText[compact="true"] {{
    font-size: 11px;
}}

QLabel#StatusPillText[status="success"] {{
    color: {tokens.color_success};
}}

QLabel#StatusPillText[status="warning"] {{
    color: {tokens.color_warning};
}}

QLabel#StatusPillText[status="danger"] {{
    color: {tokens.color_danger};
}}

QLabel#StatusPillText[status="info"] {{
    color: {tokens.color_info};
}}

QFrame#DropZone {{
    background: {tokens.color_bg_surface};
    border: {BORDER_WIDTH_PIXEL}px dashed {accent};
    border-radius: {RADIUS["dropzone"]}px;
}}

QFrame#DropZone[dragOver="true"] {{
    background: {tokens.color_bg_surface_hover};
    border: {BORDER_WIDTH_PIXEL}px dashed {tokens.color_focus_secondary};
}}

QFrame#DropZone[accepted="true"] {{
    border-color: {tokens.color_success};
}}

QFrame#DropZone[rejected="true"] {{
    border-color: {tokens.color_danger};
}}

QPushButton {{
    min-height: {SIZES["button"]}px;
    padding: 0 {SPACING["lg"]}px;
    border-radius: {RADIUS["pixel"]}px;
    background: {tokens.color_bg_surface};
    color: {tokens.color_text_main};
    border: {BORDER_WIDTH_PIXEL}px solid {tokens.color_border_default};
    font-weight: 800;
    font-family: {FONT_MONO};
}}

QPushButton:hover {{
    background: {tokens.color_bg_surface_hover};
    border-color: {accent};
}}

QPushButton:focus {{
    border-color: {tokens.color_focus_primary};
    border-bottom-color: {tokens.color_focus_secondary};
    border-right-color: {tokens.color_focus_secondary};
}}

QPushButton:pressed {{
    background: {tokens.color_bg_surface_pressed};
    padding-top: {SPACING["xs"]}px;
    padding-left: {SPACING["lg"] + SPACING["xs"]}px;
}}

QPushButton:disabled {{
    color: {tokens.color_text_muted};
    background: {tokens.color_bg_alt};
    border-color: {tokens.color_border_default};
}}

QPushButton[role="primary"] {{
    min-height: {SIZES["button_primary"]}px;
    color: {tokens.color_text_main};
    background: {tokens.color_info_bg};
    border-color: {primary_border};
    border-bottom-color: {primary_bottom};
    border-right-color: {primary_right};
}}

QPushButton[role="primary"]:hover {{
    background: {tokens.color_bg_surface_hover};
    border-color: {tokens.color_focus_secondary};
    border-bottom-color: {primary_bottom};
    border-right-color: {primary_border};
}}

QPushButton[requiredStep="true"] {{
    background: {tokens.color_info_bg};
    border-color: {required_border};
    border-bottom-color: {required_bottom};
    border-right-color: {required_right};
    color: {tokens.color_text_main};
}}

QPushButton[requiredStep="true"]:hover {{
    background: {tokens.color_bg_surface_hover};
    border-color: {required_border};
    border-bottom-color: {required_right};
    border-right-color: {required_bottom};
}}

QPushButton[role="danger"] {{
    background: {tokens.color_danger_bg};
    color: {tokens.color_text_main};
    border-color: {tokens.color_danger_border};
    border-bottom-color: {tokens.color_danger_border};
    border-right-color: {tokens.color_danger_border};
}}

QPushButton[role="danger"]:hover {{
    background: {tokens.color_bg_surface_hover};
    color: {tokens.color_danger};
    border-color: {tokens.color_danger};
}}

QPushButton[role="ghost"] {{
    background: transparent;
    border-color: transparent;
}}

QPushButton[role="ghost"]:hover {{
    background: {tokens.color_bg_surface};
    border-color: {tokens.color_border_default};
}}

QPushButton[role="meta"] {{
    min-height: 28px;
    padding: 0 {SPACING["sm"]}px;
    background: transparent;
    border-color: transparent;
    font-size: 11px;
}}

QPushButton[role="meta"]:hover {{
    background: {tokens.color_bg_surface};
    border-color: {tokens.color_border_default};
}}

QPushButton[role="updateStatus"] {{
    min-height: 32px;
    padding: 0 {SPACING["sm"]}px;
    background: {tokens.color_bg_surface};
    border-color: {tokens.color_border_default};
    color: {tokens.color_text_secondary};
    font-size: 11px;
    font-weight: 800;
}}

QPushButton[role="updateStatus"]:hover {{
    background: {tokens.color_bg_surface_hover};
    border-color: {tokens.color_border_active};
}}

QPushButton[role="updateStatus"][status="success"] {{
    color: {tokens.color_success};
}}

QPushButton[role="updateStatus"][status="warning"] {{
    color: {tokens.color_warning};
}}

QPushButton[role="sidebarToggle"] {{
    min-height: 64px;
    min-width: 18px;
    max-width: 18px;
    padding: 0;
    background: {tokens.color_bg_surface};
    border-color: {tokens.color_border_default};
    border-right-color: {tokens.color_border_default};
    font-size: 1px;
}}

QPushButton[role="sidebarToggle"]:hover {{
    background: {tokens.color_bg_surface_hover};
    border-color: {accent};
}}

QPushButton[role="workspaceItem"] {{
    text-align: left;
    min-height: 32px;
    padding: 0 {SPACING["sm"]}px;
    background: {tokens.color_bg_surface};
    color: {tokens.color_text_secondary};
    border: {BORDER_WIDTH_PIXEL}px solid {tokens.color_border_default};
    border-left: 4px solid {permanent_accent};
}}

QPushButton[role="workspaceItem"]:hover {{
    background: {tokens.color_bg_surface_hover};
    color: {tokens.color_text_main};
    border-color: {accent};
}}

QPushButton[role="workspaceItem"][active="true"] {{
    background: {tokens.color_info_bg};
    color: {tokens.color_text_main};
    border-color: {accent};
    border-left-color: {active_left};
}}

QFrame#WorkspaceCard {{
    background: {tokens.color_bg_surface};
    border: {BORDER_WIDTH_PIXEL}px solid {tokens.color_border_default};
    border-left: 4px solid {permanent_accent};
    border-radius: {RADIUS["card"]}px;
}}

QFrame#WorkspaceCard[active="true"] {{
    background: {tokens.color_info_bg};
    border-color: {accent};
    border-left-color: {active_left};
    border-bottom-color: {active_bottom};
}}

QPushButton[role="workspaceCard"] {{
    text-align: left;
    min-height: 42px;
    padding: 0;
    background: transparent;
    color: {tokens.color_text_secondary};
    border: none;
}}

QPushButton[role="workspaceCard"]:hover {{
    background: transparent;
    color: {tokens.color_text_main};
}}

QPushButton[role="workspaceCard"][active="true"] {{
    background: transparent;
    color: {tokens.color_text_main};
}}

QPushButton[role="workspaceNew"] {{
    text-align: center;
    min-height: 28px;
    min-width: 32px;
    max-width: 36px;
    padding: 0;
    background: transparent;
    color: {tokens.color_text_secondary};
    border: {BORDER_WIDTH_PIXEL}px solid {tokens.color_border_default};
    font-size: 16px;
}}

QPushButton[role="workspaceNew"]:hover {{
    background: {tokens.color_bg_surface};
    color: {tokens.color_text_main};
    border-color: {accent};
}}

QPushButton[role="workspaceRemove"] {{
    min-height: 32px;
    min-width: 32px;
    padding: 0;
    background: {tokens.color_danger_bg};
    color: {tokens.color_danger};
    border-color: {tokens.color_danger_border};
}}

QPushButton[role="workspaceRemove"]:hover {{
    background: {tokens.color_bg_surface_hover};
    border-color: {tokens.color_danger};
}}

QPushButton[role="nav"] {{
    text-align: left;
    min-height: 40px;
    background: transparent;
    border: {BORDER_WIDTH_PIXEL}px solid transparent;
    border-left: 4px solid transparent;
    color: {tokens.color_text_secondary};
}}

QPushButton[role="nav"]:hover {{
    background: {tokens.color_bg_surface};
    color: {tokens.color_text_main};
    border-color: {tokens.color_border_default};
    border-left-color: {accent};
}}

QPushButton[role="nav"][active="true"] {{
    background: {tokens.color_bg_surface_hover};
    color: {tokens.color_text_main};
    border-color: {tokens.color_border_default};
    border-left-color: {active_left};
    border-bottom-color: {active_bottom};
}}

QPushButton[role="nav"][pending="true"] {{
    color: {tokens.color_text_muted};
    border-left-color: {tokens.color_warning_border};
}}

QPushButton[role="nav"][pending="true"]:hover {{
    color: {tokens.color_warning};
    border-color: {tokens.color_warning_border};
}}

QPushButton[compact="true"] {{
    text-align: center;
    min-height: 40px;
    padding: 0 {SPACING["xs"]}px;
    font-size: 10px;
}}

QPushButton[role="nav"][compact="true"] {{
    min-height: 38px;
    border-left-width: {BORDER_WIDTH_PIXEL}px;
}}

QPushButton[role="meta"][compact="true"] {{
    min-height: 32px;
    padding: 0 {SPACING["xs"]}px;
    border-color: {tokens.color_border_default};
}}

QLineEdit, QComboBox, QSpinBox, QListWidget, QListView, QTreeWidget, QTreeView,
QTableWidget, QTableView {{
    background: {tokens.color_bg_surface};
    color: {tokens.color_text_main};
    border: {BORDER_WIDTH_PIXEL}px solid {tokens.color_border_default};
    border-radius: {RADIUS["pixel"]}px;
    padding: {SPACING["sm"]}px {SPACING["md"]}px;
    selection-background-color: {tokens.color_info_bg};
    selection-color: {tokens.color_text_main};
}}

QTextBrowser#CommunityBrowser {{
    background: {tokens.color_bg_surface};
    color: {tokens.color_text_main};
    border: {BORDER_WIDTH_PIXEL}px solid {tokens.color_border_default};
    border-radius: {RADIUS["pixel"]}px;
    padding: {SPACING["md"]}px;
    selection-background-color: {tokens.color_info_bg};
}}

QTextBrowser#CommunityBrowser:focus {{
    border-color: {tokens.color_focus_primary};
}}

QStatusBar {{
    color: {tokens.color_text_secondary};
    background: {tokens.color_bg_alt};
    border-top: {BORDER_WIDTH_PIXEL}px solid {tokens.color_border_default};
}}

QCheckBox {{
    color: {tokens.color_text_secondary};
    spacing: {SPACING["sm"]}px;
    font-weight: 800;
}}

QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    background: {tokens.color_bg_surface};
    border: {BORDER_WIDTH_PIXEL}px solid {tokens.color_border_default};
}}

QCheckBox::indicator:checked {{
    background: {tokens.color_success};
    border-color: {accent};
}}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QListWidget:focus, QListView:focus,
QTreeWidget:focus, QTreeView:focus, QTableWidget:focus, QTableView:focus {{
    border-color: {tokens.color_focus_primary};
    border-bottom-color: {tokens.color_focus_secondary};
}}

QMenu {{
    background: {tokens.color_bg_surface};
    color: {tokens.color_text_main};
    border: {BORDER_WIDTH_PIXEL}px solid {tokens.color_border_default};
    border-bottom-color: {menu_bottom};
    border-right-color: {menu_right};
    border-radius: {RADIUS["pixel"]}px;
    padding: {SPACING["xs"]}px;
}}

QMenu::item {{
    min-height: 28px;
    padding: {SPACING["sm"]}px {SPACING["xl"]}px {SPACING["sm"]}px {SPACING["md"]}px;
    background: transparent;
    color: {tokens.color_text_secondary};
    border: 1px solid transparent;
}}

QMenu::item:selected {{
    background: {tokens.color_bg_surface_hover};
    color: {tokens.color_text_main};
    border-color: {accent};
    border-left: 4px solid {selected_left};
}}

QMenu::item:disabled {{
    color: {tokens.color_text_muted};
    background: {tokens.color_bg_alt};
}}

QMenu::separator {{
    height: 1px;
    background: {tokens.color_border_default};
    margin: {SPACING["xs"]}px {SPACING["sm"]}px;
}}

QListWidget::item {{
    min-height: 34px;
    padding: {SPACING["sm"]}px;
    border: 1px solid transparent;
    border-radius: {RADIUS["none"]}px;
}}

QListWidget::item:selected,
QListWidget::item:selected:active,
QListWidget::item:selected:!active,
QListWidget::item:selected:hover,
QListView::item:selected,
QListView::item:selected:active,
QListView::item:selected:!active,
QListView::item:selected:hover,
QTreeWidget::item:selected,
QTreeWidget::item:selected:active,
QTreeWidget::item:selected:!active,
QTreeWidget::item:selected:hover,
QTreeView::item:selected,
QTreeView::item:selected:active,
QTreeView::item:selected:!active,
QTreeView::item:selected:hover,
QTableWidget::item:selected,
QTableWidget::item:selected:active,
QTableWidget::item:selected:!active,
QTableWidget::item:selected:hover,
QTableView::item:selected,
QTableView::item:selected:active,
QTableView::item:selected:!active,
QTableView::item:selected:hover {{
    background: {tokens.color_info_bg};
    color: {tokens.color_text_main};
    border-color: {accent};
}}

QToolButton#DocumentPageItem {{
    background: transparent;
    color: {tokens.color_text_secondary};
    border: {BORDER_WIDTH_PIXEL}px solid transparent;
    border-radius: {RADIUS["pixel"]}px;
    padding: {SPACING["xs"]}px;
    font-family: {FONT_MONO};
    font-size: 11px;
    font-weight: 800;
}}

QToolButton#DocumentPageItem:hover {{
    background: {tokens.color_bg_surface_hover};
    color: {tokens.color_text_main};
    border-color: {tokens.color_border_default};
}}

QToolButton#DocumentPageItem[active="true"] {{
    background: {tokens.color_info_bg};
    color: {tokens.color_text_main};
    border-color: {accent};
}}

QListWidget#ThumbnailList {{
    padding: {SPACING["sm"]}px;
}}

QListWidget#ThumbnailList::item {{
    min-width: 112px;
    min-height: 176px;
    padding: {SPACING["sm"]}px;
}}

QListWidget#PageOutputList {{
    background: {tokens.color_bg_alt};
    border: {BORDER_WIDTH_PIXEL}px dashed {tokens.color_border_default};
    padding: {SPACING["sm"]}px;
}}

QListWidget#PageOutputList::item {{
    min-width: 136px;
    min-height: 204px;
    padding: {SPACING["sm"]}px;
    border: {BORDER_WIDTH_PIXEL}px solid {tokens.color_border_default};
    background: {tokens.color_bg_surface};
    color: {tokens.color_text_main};
}}

QListWidget#PageOutputList::item:selected {{
    background: {tokens.color_info_bg};
    border-color: {accent};
}}

QProgressBar {{
    background: {tokens.color_bg_main};
    border: {BORDER_WIDTH_PIXEL}px solid {tokens.color_border_default};
    border-radius: {RADIUS["none"]}px;
    min-height: 14px;
    text-align: center;
    color: {tokens.color_text_muted};
}}

QProgressBar::chunk {{
    background: {tokens.color_success};
    width: 8px;
    margin: 1px;
}}

QMessageBox, QDialog {{
    background: {tokens.color_bg_surface};
    color: {tokens.color_text_main};
}}

QScrollArea {{
    border: none;
    background: transparent;
}}

QScrollBar:vertical {{
    background: {tokens.color_bg_rail};
    width: 12px;
    border-left: 1px solid {tokens.color_border_default};
}}

QScrollBar::handle:vertical {{
    background: {tokens.color_border_default};
    border: 1px solid {accent};
    border-radius: {RADIUS["none"]}px;
}}
"""
