from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from pdfmod.ui.components.tool_icons import LineIcon
from pdfmod.ui.theme.effects import apply_pixel_layers, set_pixel_raised
from pdfmod.ui.theme.tokens import PALETTES, PIXEL_LAYER_OFFSETS, ThemeTokens


def _current_tokens() -> ThemeTokens:
    app = QApplication.instance()
    preset = app.property("priveopdf_theme_preset") if app is not None else "dark_pro"
    if isinstance(preset, str):
        return PALETTES.get(preset, PALETTES["dark_pro"])
    mode = app.property("priveopdf_theme_mode") if app is not None else "dark"
    return PALETTES.get(mode, PALETTES["dark_pro"])


def _role_color(tokens: ThemeTokens, role: str) -> QColor:
    role_map = {
        "neutral": tokens.color_border_default,
        "primary": tokens.color_pixel_blue,
        "info": tokens.color_info,
        "success": tokens.color_success,
        "warning": tokens.color_warning,
        "danger": tokens.color_danger,
        "color_pixel_blue": tokens.color_pixel_blue,
        "color_pixel_yellow": tokens.color_pixel_yellow,
        "color_pixel_green": tokens.color_pixel_green,
        "color_pixel_red": tokens.color_pixel_red,
    }
    return QColor(role_map.get(role, tokens.color_pixel_blue))


def _refresh_style(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def _paint_pixel_surface(widget: QWidget, role: str) -> None:
    tokens = _current_tokens()
    painter = QPainter(widget)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

    full_rect = widget.rect()
    painter.fillRect(full_rect, QColor(tokens.color_bg_main))
    inset = 6 if min(full_rect.width(), full_rect.height()) > 72 else 4
    base_rect = full_rect.adjusted(inset, inset, -inset - 1, -inset - 1)
    if base_rect.width() <= 0 or base_rect.height() <= 0:
        return

    interactive = isinstance(widget, QAbstractButton)
    raised = bool(widget.property("pixelRaised"))
    if interactive:
        raised = raised or widget.isDown() or widget.hasFocus()
    pixel_role = str(widget.property("pixelRole") or role)
    if tokens.visual_style == "pro":
        fill_color = tokens.color_bg_surface_hover if raised else tokens.color_bg_surface
        if widget.property("disabled") is True:
            fill_color = tokens.color_bg_alt
        border_color = (
            _role_color(tokens, pixel_role).name() if raised else tokens.color_border_default
        )
        painter.fillRect(base_rect.adjusted(1, 1, -1, -1), QColor(fill_color))
        painter.setPen(_pixel_pen(border_color, 1))
        painter.drawRect(base_rect)
        if interactive and widget.hasFocus():
            _draw_focus_outline(painter, base_rect, tokens)
        return

    offset_boost = 2 if raised else 0
    layer_specs = (
        ("red", tokens.color_pixel_red),
        ("yellow", tokens.color_pixel_yellow),
        ("green", tokens.color_pixel_green),
        ("blue", _role_color(tokens, pixel_role).name()),
    )
    for layer_key, color in layer_specs:
        dx, dy = PIXEL_LAYER_OFFSETS[layer_key]
        layer_rect = base_rect.translated(dx - offset_boost, dy + offset_boost)
        painter.setPen(_pixel_pen(color, 2))
        painter.drawRect(layer_rect)

    fill_color = tokens.color_bg_surface_hover if raised else tokens.color_bg_surface
    if widget.property("disabled") is True:
        fill_color = tokens.color_bg_alt
    painter.fillRect(base_rect.adjusted(1, 1, -1, -1), QColor(fill_color))
    painter.setPen(_pixel_pen(tokens.color_border_default, 2))
    painter.drawRect(base_rect)
    _draw_corner_blocks(painter, base_rect, tokens)
    if interactive and widget.hasFocus():
        _draw_focus_outline(painter, base_rect, tokens)


class PixelFrame(QFrame):
    def __init__(
        self,
        role: str = "primary",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._pixel_role = role
        self._pixel_raised = False
        apply_pixel_layers(self, _normalized_role(role), False)

    def set_pixel_role(self, role: str) -> None:
        self._pixel_role = role
        apply_pixel_layers(self, _normalized_role(role), self._pixel_raised)

    def set_pixel_raised(self, raised: bool) -> None:
        self._pixel_raised = raised
        set_pixel_raised(self, raised)

    def paintEvent(self, event) -> None:  # noqa: ANN001
        del event
        _paint_pixel_surface(self, self._pixel_role)


class StatusPill(PixelFrame):
    def __init__(
        self,
        text: str = "100 % LOCAL",
        status: str = "success",
        *,
        compact: bool = False,
        icon: str | None = "shield",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(status, parent)
        self.setObjectName("StatusPill")
        self.setProperty("status", status)
        self.setProperty("compact", compact)
        layout = QHBoxLayout(self)
        if compact:
            layout.setContentsMargins(8, 4, 8, 4)
        else:
            layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(6 if compact else 8)
        icon_role = _normalized_role(status)
        self._icon = LineIcon(icon, icon_role) if icon is not None else None
        if self._icon is not None:
            layout.addWidget(self._icon)
        label = QLabel(text.upper())
        label.setObjectName("StatusPillText")
        label.setProperty("status", status)
        label.setProperty("compact", compact)
        layout.addWidget(label)
        self._label = label

    def set_status(self, text: str, status: str = "info") -> None:
        self.setProperty("status", status)
        self._label.setProperty("status", status)
        self._label.setText(text.upper())
        if self._icon is not None:
            self._icon.set_icon("shield", _normalized_role(status))
        self.set_pixel_role(status)
        _refresh_style(self)
        _refresh_style(self._label)


class TrustPanel(PixelFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("success", parent)
        self.setObjectName("TrustPanel")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(18)
        for title, text, icon in (
            ("TRAITEMENT LOCAL", "Les fichiers restent sur l'appareil.", "shield"),
            ("AUCUN COMPTE", "Pas d'inscription pour utiliser les outils.", "document"),
            ("SANS CLOUD", "Aucun upload requis pour traiter un PDF.", "lock"),
        ):
            layout.addWidget(_TrustItem(title, text, icon), 1)


class _TrustItem(QWidget):
    def __init__(self, title: str, text: str, icon: str) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(LineIcon(icon, "success"))
        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)
        title_label = QLabel(title)
        title_label.setObjectName("SectionTitle")
        body_label = QLabel(text)
        body_label.setObjectName("HelpText")
        body_label.setWordWrap(True)
        text_layout.addWidget(title_label)
        text_layout.addWidget(body_label)
        layout.addLayout(text_layout)


class SurfacePanel(PixelFrame):
    def __init__(
        self,
        soft: bool = False,
        role: str = "neutral",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(role, parent)
        self.setObjectName("PanelSoft" if soft else "Panel")


class ElidedLabel(QLabel):
    """Single-line label that keeps its complete text available to the user."""

    def __init__(
        self,
        text: str = "",
        *,
        elide_mode: Qt.TextElideMode = Qt.TextElideMode.ElideMiddle,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._full_text = ""
        self._elide_mode = elide_mode
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setText(text)

    def setText(self, text: str) -> None:  # noqa: N802
        self._full_text = text
        self._refresh_elided_text()

    def full_text(self) -> str:
        return self._full_text

    def resizeEvent(self, event) -> None:  # noqa: ANN001, N802
        super().resizeEvent(event)
        self._refresh_elided_text()

    def changeEvent(self, event) -> None:  # noqa: ANN001, N802
        super().changeEvent(event)
        self._refresh_elided_text()

    def _refresh_elided_text(self) -> None:
        available_width = self.contentsRect().width()
        displayed_text = self._full_text
        if available_width > 0:
            displayed_text = self.fontMetrics().elidedText(
                self._full_text,
                self._elide_mode,
                available_width,
            )
        QLabel.setText(self, displayed_text)


class InspectorPanel(SurfacePanel):
    def __init__(
        self,
        title: str = "",
        *,
        content: QWidget | None = None,
        scrollable: bool = True,
        role: str = "neutral",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(role=role, parent=parent)
        self.setProperty("inspectorPanel", True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._content: QWidget | None = None
        self._scroll_area: QScrollArea | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        self._title_label = QLabel(title)
        self._title_label.setObjectName("SectionTitle")
        layout.addWidget(self._title_label)

        if scrollable:
            self._scroll_area = QScrollArea()
            self._scroll_area.setWidgetResizable(True)
            self._scroll_area.setFrameShape(QFrame.Shape.NoFrame)
            self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            layout.addWidget(self._scroll_area, 1)
        self._body_layout = layout
        if content is not None:
            self.set_content(content)

    def set_title(self, title: str) -> None:
        self._title_label.setText(title)

    def title_label(self) -> QLabel:
        return self._title_label

    def scroll_area(self) -> QScrollArea:
        if self._scroll_area is None:
            raise RuntimeError("InspectorPanel was created without a scroll area")
        return self._scroll_area

    def set_content(self, content: QWidget) -> None:
        if self._content is not None:
            self._content.setParent(None)
        self._content = content
        if self._scroll_area is not None:
            self._scroll_area.setWidget(content)
            return
        self._body_layout.addWidget(content, 1)

    def content_widget(self) -> QWidget | None:
        return self._content


class ToolCard(QAbstractButton):
    activated = Signal(str)

    def __init__(
        self,
        key: str,
        title: str,
        description: str,
        icon: str = "document",
        accent_role: str = "primary",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._key = key
        self._pixel_role = accent_role
        self._pixel_raised = False
        self._on_hover: Callable[[ToolCard], None] | None = None
        apply_pixel_layers(self, _normalized_role(accent_role), False)
        self.setObjectName("ToolCard")
        self.setProperty("active", False)
        self.setProperty("disabled", False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(124)
        self.clicked.connect(self._emit_activation)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)
        layout.addWidget(LineIcon(icon, accent_role))

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(8)
        self._title_label = QLabel(title.upper())
        self._title_label.setObjectName("SectionTitle")
        self._description_label = QLabel(description)
        self._description_label.setObjectName("HelpText")
        self._description_label.setWordWrap(True)
        text_layout.addWidget(self._title_label)
        text_layout.addWidget(self._description_label)
        layout.addLayout(text_layout, 1)
        self._set_accessible_text(title, description)

    @property
    def key(self) -> str:
        return self._key

    def set_active(self, active: bool) -> None:
        self.setProperty("active", active)
        self.set_pixel_raised(active)
        _refresh_style(self)

    def set_pixel_raised(self, raised: bool) -> None:
        self._pixel_raised = raised
        set_pixel_raised(self, raised)

    def set_text(
        self,
        title: str,
        description: str,
    ) -> None:
        self._title_label.setText(title.upper())
        self._description_label.setText(description)
        self._set_accessible_text(title, description)

    def set_hover_callback(self, callback: Callable[[ToolCard], None]) -> None:
        self._on_hover = callback

    def enterEvent(self, event) -> None:  # noqa: ANN001
        if self._on_hover is not None:
            self._on_hover(self)
        self.set_pixel_raised(True)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: ANN001
        self.set_pixel_raised(self.property("active") is True)
        super().leaveEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: ANN001, N802
        if event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
            if self.isEnabled() and not event.isAutoRepeat():
                self.click()
            event.accept()
            return
        super().keyPressEvent(event)

    def paintEvent(self, event) -> None:  # noqa: ANN001, N802
        del event
        _paint_pixel_surface(self, self._pixel_role)

    def _emit_activation(self) -> None:
        self.activated.emit(self._key)

    def _set_accessible_text(self, title: str, description: str) -> None:
        self.setAccessibleName(title)
        self.setAccessibleDescription(description)


def _normalized_role(role: str) -> str:
    if role in {"success", "warning", "danger", "info", "neutral", "primary"}:
        return role
    if role == "color_pixel_blue":
        return "primary"
    if role == "color_pixel_yellow":
        return "warning"
    if role == "color_pixel_green":
        return "success"
    if role == "color_pixel_red":
        return "danger"
    return "primary"


def _pixel_pen(color: str, width: int):
    from PySide6.QtGui import QPen

    pen = QPen(QColor(color), width)
    pen.setCapStyle(Qt.PenCapStyle.SquareCap)
    pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
    return pen


def _draw_focus_outline(
    painter: QPainter,
    rect: QRect,
    tokens: ThemeTokens,
) -> None:
    outer_rect = rect.adjusted(2, 2, -2, -2)
    inner_rect = rect.adjusted(5, 5, -5, -5)
    if inner_rect.width() <= 0 or inner_rect.height() <= 0:
        return
    painter.setPen(_pixel_pen(tokens.color_focus_primary, 2))
    painter.drawRect(outer_rect)
    painter.setPen(_pixel_pen(tokens.color_focus_secondary, 2))
    painter.drawRect(inner_rect)


def _draw_corner_blocks(painter: QPainter, rect: QRect, tokens: ThemeTokens) -> None:
    size = 6
    painter.fillRect(QRect(rect.left(), rect.top(), size, size), QColor(tokens.color_pixel_red))
    painter.fillRect(
        QRect(rect.right() - size + 1, rect.top(), size, size),
        QColor(tokens.color_pixel_yellow),
    )
    painter.fillRect(
        QRect(rect.left(), rect.bottom() - size + 1, size, size),
        QColor(tokens.color_pixel_green),
    )
    painter.fillRect(
        QRect(rect.right() - size + 1, rect.bottom() - size + 1, size, size),
        QColor(tokens.color_pixel_blue),
    )
