from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Literal

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen
from PySide6.QtWidgets import QApplication, QWidget

from pdfmod.app.app_info import is_beta_runtime, is_dev_runtime
from pdfmod.ui.theme.tokens import PALETTES, ThemeTokens

WordmarkVariant = Literal["full", "compact"]

PIXEL_GLYPHS = {
    "[": ("110", "100", "100", "100", "100", "100", "110"),
    "]": ("011", "001", "001", "001", "001", "001", "011"),
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "I": ("111", "010", "010", "010", "010", "010", "111"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "V": ("10001", "10001", "10001", "10001", "01010", "01010", "00100"),
}

APP_ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)


@dataclass(frozen=True)
class WordmarkLayout:
    unit: int
    x: int
    y: int
    layer_offset: int
    badge_text_scale: int

    @property
    def badge_gap(self) -> int:
        return self.unit * 3

    @property
    def badge_width(self) -> int:
        return self.unit * 14

    @property
    def badge_height(self) -> int:
        return self.unit * 7

    @property
    def badge_y_offset(self) -> int:
        return self.unit * 2


class PixelWordmark(QWidget):
    def __init__(
        self,
        variant: WordmarkVariant = "full",
        parent: QWidget | None = None,
        *,
        compact: bool | None = None,
        show_beta: bool | None = None,
        show_dev: bool | None = None,
    ) -> None:
        super().__init__(parent)
        if compact is not None:
            variant = "compact" if compact else "full"
        self._variant: WordmarkVariant = variant
        self._show_beta = is_beta_runtime() if show_beta is None else show_beta
        self._show_dev = is_dev_runtime() if show_dev is None else show_dev
        if self._show_beta:
            self._show_dev = False
        marker = " [BETA]" if self._show_beta else " [DEV]" if self._show_dev else ""
        self.setAccessibleName(f"PriveoPDF{marker}")
        self.setMinimumSize(self.sizeHint())

    @property
    def shows_beta_marker(self) -> bool:
        return self._show_beta

    @property
    def shows_dev_marker(self) -> bool:
        return self._show_dev

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(172, 54) if self._variant == "compact" else QSize(360, 88)

    def paintEvent(self, event) -> None:  # noqa: ANN001
        del event
        tokens = current_tokens()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        draw_wordmark(
            painter,
            self._variant,
            tokens,
            show_beta=self._show_beta,
            show_dev=self._show_dev,
        )


def current_tokens() -> ThemeTokens:
    app = QApplication.instance()
    preset = app.property("priveopdf_theme_preset") if app is not None else "dark_pro"
    if isinstance(preset, str):
        return PALETTES.get(preset, PALETTES["dark_pro"])
    mode = app.property("priveopdf_theme_mode") if app is not None else "dark"
    return PALETTES.get(mode, PALETTES["dark_pro"])


def app_icon_path(size: int = 256) -> Path:
    if size not in APP_ICON_SIZES:
        size = 256
    return Path(str(files("pdfmod.assets.icons").joinpath(f"app_icon_{size}.png")))


def beta_app_icon_path(size: int = 256) -> Path:
    if size not in APP_ICON_SIZES:
        size = 256
    return Path(str(files("pdfmod.assets.icons").joinpath(f"app_icon_beta_{size}.png")))


def dev_app_icon_path() -> Path:
    return Path(str(files("pdfmod.assets.icons").joinpath("app_icon_dev.svg")))


def build_app_icon() -> QIcon:
    icon = QIcon()
    if is_beta_runtime():
        for size in APP_ICON_SIZES:
            path = beta_app_icon_path(size)
            if path.exists():
                icon.addFile(str(path), QSize(size, size))
        return icon
    if is_dev_runtime():
        path = dev_app_icon_path()
        if path.exists():
            icon.addFile(str(path))
            return icon
    for size in APP_ICON_SIZES:
        path = app_icon_path(size)
        if path.exists():
            icon.addFile(str(path), QSize(size, size))
    return icon


def draw_wordmark(
    painter: QPainter,
    variant: WordmarkVariant,
    tokens: ThemeTokens,
    x: int | None = None,
    y: int | None = None,
    *,
    show_beta: bool = False,
    show_dev: bool = False,
) -> None:
    layout = _wordmark_layout(variant, x, y)
    unit = layout.unit
    layers = (
        (tokens.color_pixel_red, -layout.layer_offset, layout.layer_offset),
        (tokens.color_pixel_yellow, 0, layout.layer_offset),
        (tokens.color_pixel_green, 0, layout.layer_offset + max(1, unit // 2)),
        (tokens.color_pixel_blue, layout.layer_offset, -layout.layer_offset),
    )
    for color, dx, dy in layers:
        draw_pixel_text(painter, "PRIVEO", layout.x + dx, layout.y + dy, unit, color)
    clear_pixel_text_holes(painter, "PRIVEO", layout.x, layout.y, unit, tokens.color_bg_main)
    draw_pixel_text(painter, "PRIVEO", layout.x, layout.y, unit, tokens.color_text_main)

    badge_rect = QRect(
        layout.x + pixel_text_width("PRIVEO", unit) + layout.badge_gap,
        layout.y + layout.badge_y_offset,
        layout.badge_width,
        layout.badge_height,
    )
    painter.fillRect(badge_rect, QColor(tokens.color_bg_main))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    badge_pen_width = max(1, unit // 3)
    painter.setPen(pixel_pen(tokens.color_pixel_red, badge_pen_width))
    painter.drawRect(badge_rect.translated(-layout.layer_offset, layout.layer_offset))
    painter.setPen(pixel_pen(tokens.color_pixel_yellow, badge_pen_width))
    painter.drawRect(badge_rect.translated(layout.layer_offset, layout.layer_offset))
    painter.setPen(pixel_pen(tokens.color_pixel_green, badge_pen_width))
    painter.drawRect(badge_rect.translated(0, layout.layer_offset * 2))
    painter.setPen(pixel_pen(tokens.color_pixel_blue, badge_pen_width))
    painter.drawRect(badge_rect)
    badge_text_width = pixel_text_width("PDF", layout.badge_text_scale)
    badge_text_x = badge_rect.left() + (badge_rect.width() - badge_text_width) // 2
    badge_text_y = badge_rect.top() + (badge_rect.height() - layout.badge_text_scale * 7) // 2
    draw_pixel_text(
        painter,
        "PDF",
        badge_text_x,
        badge_text_y,
        layout.badge_text_scale,
        tokens.color_text_main,
    )
    if show_beta:
        _draw_runtime_marker(
            painter,
            variant,
            layout,
            badge_rect.right(),
            text="[BETA]",
            foreground=tokens.color_danger,
            background=tokens.color_danger_bg,
        )
    elif show_dev:
        _draw_runtime_marker(
            painter,
            variant,
            layout,
            badge_rect.right(),
            text="[DEV]",
            foreground=tokens.color_info,
            background=tokens.color_info_bg,
        )


def _draw_beta_marker(
    painter: QPainter,
    variant: WordmarkVariant,
    tokens: ThemeTokens,
    layout: WordmarkLayout,
    wordmark_right: int,
) -> None:
    _draw_runtime_marker(
        painter,
        variant,
        layout,
        wordmark_right,
        text="[BETA]",
        foreground=tokens.color_danger,
        background=tokens.color_danger_bg,
    )


def _draw_runtime_marker(
    painter: QPainter,
    variant: WordmarkVariant,
    layout: WordmarkLayout,
    wordmark_right: int,
    *,
    text: str,
    foreground: str,
    background: str,
) -> None:
    scale = 1 if variant == "compact" else 2
    padding_x = scale * 2
    padding_y = scale
    width = pixel_text_width(text, scale) + 2 * padding_x
    height = 7 * scale + 2 * padding_y
    rect = QRect(
        wordmark_right - width + 1,
        layout.y + layout.unit * 9,
        width,
        height,
    )
    painter.fillRect(rect, QColor(background))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(pixel_pen(foreground, max(1, scale)))
    painter.drawRect(rect)
    draw_pixel_text(
        painter,
        text,
        rect.x() + padding_x,
        rect.y() + padding_y,
        scale,
        foreground,
    )


def _wordmark_layout(
    variant: WordmarkVariant,
    x: int | None,
    y: int | None,
) -> WordmarkLayout:
    if variant == "compact":
        return WordmarkLayout(
            unit=3,
            x=4 if x is None else x,
            y=7 if y is None else y,
            layer_offset=1,
            badge_text_scale=2,
        )
    return WordmarkLayout(
        unit=6,
        x=6 if x is None else x,
        y=10 if y is None else y,
        layer_offset=2,
        badge_text_scale=3,
    )


def draw_app_icon(painter: QPainter, size: int, tokens: ThemeTokens) -> None:
    if size <= 32:
        _draw_small_app_icon(painter, size, tokens)
        return

    painter.fillRect(QRect(0, 0, size, size), QColor(tokens.color_bg_main))
    unit = max(1, size // 32)
    margin = max(2, unit * 2)
    base_rect = QRect(margin, margin, size - 2 * margin, size - 2 * margin)
    painter.setPen(pixel_pen(tokens.color_pixel_red, max(1, unit)))
    painter.drawRect(base_rect.translated(-unit, unit))
    painter.setPen(pixel_pen(tokens.color_pixel_yellow, max(1, unit)))
    painter.drawRect(base_rect.translated(unit, unit))
    painter.setPen(pixel_pen(tokens.color_pixel_green, max(1, unit)))
    painter.drawRect(base_rect.translated(0, unit * 2))
    painter.setPen(pixel_pen(tokens.color_pixel_blue, max(1, unit)))
    painter.drawRect(base_rect)

    glyph_scale = max(1, size // 14)
    glyph_width = pixel_text_width("P", glyph_scale)
    glyph_height = 7 * glyph_scale
    x = (size - glyph_width) // 2
    y = (size - glyph_height) // 2
    if size >= 32:
        draw_pixel_text(painter, "P", x - unit, y + unit, glyph_scale, tokens.color_pixel_red)
        draw_pixel_text(painter, "P", x + unit, y - unit, glyph_scale, tokens.color_pixel_blue)
    draw_pixel_text(painter, "P", x, y, glyph_scale, tokens.color_text_main)


def _draw_small_app_icon(painter: QPainter, size: int, tokens: ThemeTokens) -> None:
    painter.fillRect(QRect(0, 0, size, size), QColor(tokens.color_bg_main))
    border_width = 1 if size == 16 else 2
    margin = 1 if size == 16 else 2
    base_rect = QRect(margin, margin, size - 2 * margin, size - 2 * margin)
    if size >= 24:
        painter.setPen(pixel_pen(tokens.color_pixel_red, border_width))
        painter.drawRect(base_rect.translated(-1, 1))
    if size >= 32:
        painter.setPen(pixel_pen(tokens.color_pixel_yellow, border_width))
        painter.drawRect(base_rect.translated(1, 1))
    painter.setPen(pixel_pen(tokens.color_pixel_blue, border_width))
    painter.drawRect(base_rect)

    glyph_scale = {16: 2, 24: 3, 32: 4}.get(size, max(1, size // 10))
    glyph_width = pixel_text_width("P", glyph_scale)
    glyph_height = 7 * glyph_scale
    x = (size - glyph_width) // 2
    y = max(1, (size - glyph_height) // 2)
    draw_pixel_text(painter, "P", x, y, glyph_scale, tokens.color_text_main)


def pixel_text_width(text: str, scale: int) -> int:
    width = 0
    for character in text:
        glyph = PIXEL_GLYPHS.get(character, PIXEL_GLYPHS["P"])
        width += len(glyph[0]) * scale + scale
    return max(0, width - scale)


def draw_pixel_text(
    painter: QPainter,
    text: str,
    x: int,
    y: int,
    scale: int,
    color: str,
) -> None:
    cursor_x = x
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(color))
    for character in text:
        glyph = PIXEL_GLYPHS.get(character)
        if glyph is None:
            cursor_x += scale * 4
            continue
        for row, line in enumerate(glyph):
            for column, pixel in enumerate(line):
                if pixel == "1":
                    painter.fillRect(
                        QRect(cursor_x + column * scale, y + row * scale, scale, scale),
                        QColor(color),
                    )
        cursor_x += (len(glyph[0]) + 1) * scale


def clear_pixel_text_holes(
    painter: QPainter,
    text: str,
    x: int,
    y: int,
    scale: int,
    color: str,
) -> None:
    cursor_x = x
    for character in text:
        glyph = PIXEL_GLYPHS.get(character)
        if glyph is None:
            cursor_x += scale * 4
            continue
        for row, line in enumerate(glyph):
            for column, pixel in enumerate(line):
                if pixel == "0":
                    painter.fillRect(
                        QRect(cursor_x + column * scale, y + row * scale, scale, scale),
                        QColor(color),
                    )
        cursor_x += (len(glyph[0]) + 1) * scale


def pixel_pen(color: str, width: int) -> QPen:
    pen = QPen(QColor(color), width)
    pen.setCapStyle(Qt.PenCapStyle.SquareCap)
    pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
    return pen
