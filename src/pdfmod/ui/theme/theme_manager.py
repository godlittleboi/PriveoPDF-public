from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from PySide6.QtCore import QObject, Qt, Signal, Slot
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from pdfmod.ui.theme.styles import build_stylesheet
from pdfmod.ui.theme.tokens import (
    DEFAULT_THEME_PRESET,
    PALETTES,
    SELECTABLE_THEME_PRESETS,
    ThemeBrightness,
    ThemePreference,
    ThemePreset,
    ThemeTokens,
    ThemeVisualStyle,
)

SystemSchemeReader = Callable[[], ThemeBrightness | None]

_BRIGHTNESS_TOGGLES: dict[ThemePreference, ThemePreference] = {
    "system": "system",
    "dark_pro": "light_pro",
    "light_pro": "dark_pro",
    "dark_pixel": "light_pixel",
    "light_pixel": "dark_pixel",
    # There is no light high-contrast palette; leave that specialized mode
    # through the canonical light professional palette.
    "dark_contrast": "light_pro",
}
_VISUAL_STYLE_TOGGLES: dict[ThemePreference, ThemePreference] = {
    "system": "system",
    "dark_pro": "dark_pixel",
    "light_pro": "light_pixel",
    "dark_pixel": "dark_pro",
    "light_pixel": "light_pro",
    "dark_contrast": "dark_contrast",
}


class ThemeManager(QObject):
    theme_changed = Signal(str)

    def __init__(
        self,
        preset: ThemePreference = DEFAULT_THEME_PRESET,
        reduce_motion: bool = False,
        settings: Any | None = None,
        system_scheme_reader: SystemSchemeReader | None = None,
    ) -> None:
        super().__init__()
        self._settings = settings
        preference = settings.theme_preset() if settings is not None else preset
        self._preference = _validated_preference(preference)
        self._system_scheme_reader = system_scheme_reader or _qt_system_scheme
        self._preset = resolve_theme_preference(
            self._preference,
            self._system_scheme_reader(),
        )
        self._reduce_motion = settings.reduce_motion() if settings is not None else reduce_motion
        self._connect_system_scheme_signal()

    @property
    def preference(self) -> ThemePreference:
        return self._preference

    @property
    def preset(self) -> ThemePreset:
        return self._preset

    @property
    def mode(self) -> ThemeBrightness:
        return self.tokens.brightness

    @property
    def visual_style(self) -> ThemeVisualStyle:
        return self.tokens.visual_style

    @property
    def tokens(self) -> ThemeTokens:
        return PALETTES[self._preset]

    @property
    def reduce_motion(self) -> bool:
        return self._reduce_motion

    def set_reduce_motion(self, reduce_motion: bool) -> None:
        self._reduce_motion = reduce_motion
        if self._settings is not None:
            self._settings.set_reduce_motion(reduce_motion)
        app = QApplication.instance()
        if app is not None:
            app.setProperty("priveopdf_reduce_motion", reduce_motion)

    def apply(self) -> None:
        if self._preference == "system":
            self._preset = resolve_theme_preference(
                self._preference,
                self._system_scheme_reader(),
            )
        app = QApplication.instance()
        if app is not None:
            app.setProperty("priveopdf_theme_preference", self._preference)
            app.setProperty("priveopdf_theme_preset", self._preset)
            app.setProperty("priveopdf_theme_mode", self.mode)
            app.setProperty("priveopdf_visual_style", self.visual_style)
            app.setProperty("priveopdf_reduce_motion", self._reduce_motion)
            app.setPalette(_palette_for_tokens(self.tokens))
            app.setStyleSheet(build_stylesheet(self.tokens))

    def set_preset(self, preset: ThemePreference) -> None:
        preference = _validated_preference(preset)
        previous_preference = self._preference
        previous_preset = self._preset
        self._preference = preference
        self._preset = resolve_theme_preference(
            preference,
            self._system_scheme_reader(),
        )
        if preference == previous_preference and self._preset == previous_preset:
            return
        if self._settings is not None and preference != previous_preference:
            self._settings.set_theme_preset(preference)
        self.apply()
        if self._preset != previous_preset:
            self.theme_changed.emit(self._preset)

    def set_mode(self, mode: ThemeBrightness) -> None:
        if self._preference == "system":
            return
        if mode == "light":
            target: ThemePreference = (
                "light_pixel" if self._preference == "dark_pixel" else "light_pro"
            )
        else:
            target = "dark_pixel" if self._preference == "light_pixel" else "dark_pro"
        self.set_preset(target)

    def toggle(self) -> ThemePreference:
        return self.toggle_brightness()

    def toggle_brightness(self) -> ThemePreference:
        next_preference = _BRIGHTNESS_TOGGLES[self._preference]
        self.set_preset(next_preference)
        return next_preference

    def toggle_visual_style(self) -> ThemePreference:
        next_preference = _VISUAL_STYLE_TOGGLES[self._preference]
        self.set_preset(next_preference)
        return next_preference

    def _connect_system_scheme_signal(self) -> None:
        app = QApplication.instance()
        if app is None:
            return
        signal = getattr(app.styleHints(), "colorSchemeChanged", None)
        if signal is not None:
            signal.connect(self._system_color_scheme_changed)

    @Slot()
    @Slot(object)
    def _system_color_scheme_changed(self, _scheme: object | None = None) -> None:
        if self._preference != "system":
            return
        previous_preset = self._preset
        self._preset = resolve_theme_preference(
            self._preference,
            self._system_scheme_reader(),
        )
        if self._preset == previous_preset:
            return
        self.apply()
        self.theme_changed.emit(self._preset)


def resolve_theme_preference(
    preference: ThemePreference,
    system_scheme: ThemeBrightness | None,
) -> ThemePreset:
    if preference == "system":
        return "light_pro" if system_scheme == "light" else "dark_pro"
    return cast("ThemePreset", preference)


def _validated_preference(value: str) -> ThemePreference:
    if value in SELECTABLE_THEME_PRESETS:
        return cast("ThemePreference", value)
    return DEFAULT_THEME_PRESET


def _qt_system_scheme() -> ThemeBrightness | None:
    app = QApplication.instance()
    if app is None:
        return None
    color_scheme = getattr(app.styleHints(), "colorScheme", None)
    if color_scheme is None:
        return None
    try:
        scheme = color_scheme()
    except TypeError:
        return None
    if scheme == Qt.ColorScheme.Light:
        return "light"
    if scheme == Qt.ColorScheme.Dark:
        return "dark"
    return None


def _palette_for_tokens(tokens: ThemeTokens) -> QPalette:
    palette = QApplication.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(tokens.color_bg_main))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(tokens.color_text_main))
    palette.setColor(QPalette.ColorRole.Base, QColor(tokens.color_bg_surface))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(tokens.color_bg_alt))
    palette.setColor(QPalette.ColorRole.Text, QColor(tokens.color_text_main))
    palette.setColor(QPalette.ColorRole.Button, QColor(tokens.color_bg_surface))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(tokens.color_text_main))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(tokens.color_info_bg))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(tokens.color_text_main))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(tokens.color_bg_surface))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(tokens.color_text_main))
    return palette
