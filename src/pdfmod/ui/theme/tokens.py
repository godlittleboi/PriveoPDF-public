from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal

ThemeBrightness = Literal["dark", "light"]
ThemeVisualStyle = Literal["pro", "pixel"]
ThemePreset = Literal[
    "dark_pro",
    "light_pro",
    "light_coral",
    "light_ocean",
    "light_sage",
    "light_lavender",
    "light_solar",
    "dark_midnight",
    "dark_forest",
    "dark_plum",
    "dark_graphite",
    "dark_contrast",
    "dark_pixel",
    "light_pixel",
]
ThemePreference = Literal[
    "system",
    "dark_pro",
    "light_pro",
    "dark_pixel",
    "light_pixel",
    "dark_contrast",
]
SELECTABLE_THEME_PRESETS: tuple[ThemePreference, ...] = (
    "system",
    "dark_pro",
    "light_pro",
    "dark_pixel",
    "light_pixel",
    "dark_contrast",
)
LEGACY_THEME_PRESET_MIGRATIONS: dict[str, ThemePreference] = {
    "light_coral": "light_pro",
    "light_ocean": "light_pro",
    "light_sage": "light_pro",
    "light_lavender": "light_pro",
    "light_solar": "light_pro",
    "dark_midnight": "dark_pro",
    "dark_forest": "dark_pro",
    "dark_plum": "dark_pro",
    "dark_graphite": "dark_pro",
}
ThemeMode = ThemeBrightness

DEFAULT_THEME_PRESET: ThemePreference = "dark_pro"


@dataclass(frozen=True)
class ThemeTokens:
    preset: ThemePreset
    brightness: ThemeBrightness
    visual_style: ThemeVisualStyle
    color_bg_main: str
    color_bg_alt: str
    color_bg_rail: str
    color_bg_surface: str
    color_bg_surface_hover: str
    color_bg_surface_pressed: str
    color_text_main: str
    color_text_secondary: str
    color_text_muted: str
    color_text_inverse: str
    color_pixel_red: str
    color_pixel_yellow: str
    color_pixel_green: str
    color_pixel_blue: str
    color_pixel_orange: str
    color_border_default: str
    color_border_active: str
    color_focus_primary: str
    color_focus_secondary: str
    color_success: str
    color_success_bg: str
    color_success_border: str
    color_warning: str
    color_warning_bg: str
    color_warning_border: str
    color_danger: str
    color_danger_bg: str
    color_danger_border: str
    color_info: str
    color_info_bg: str
    color_info_border: str


DARK_PIXEL_PALETTE = ThemeTokens(
    preset="dark_pixel",
    brightness="dark",
    visual_style="pixel",
    color_bg_main="#000000",
    color_bg_alt="#030303",
    color_bg_rail="#080808",
    color_bg_surface="#0D0D0D",
    color_bg_surface_hover="#121212",
    color_bg_surface_pressed="#050505",
    color_text_main="#F5F5F0",
    color_text_secondary="#B8B8B0",
    color_text_muted="#7E7E78",
    color_text_inverse="#000000",
    color_pixel_red="#FF2D20",
    color_pixel_yellow="#FFD43B",
    color_pixel_green="#7ED957",
    color_pixel_blue="#2BB7E5",
    color_pixel_orange="#FF8A1F",
    color_border_default="#242424",
    color_border_active="#2BB7E5",
    color_focus_primary="#2BB7E5",
    color_focus_secondary="#FFD43B",
    color_success="#7ED957",
    color_success_bg="#101A0C",
    color_success_border="#3F7D2A",
    color_warning="#FFD43B",
    color_warning_bg="#1F1805",
    color_warning_border="#8C6D11",
    color_danger="#FF2D20",
    color_danger_bg="#210704",
    color_danger_border="#8F1A12",
    color_info="#2BB7E5",
    color_info_bg="#051820",
    color_info_border="#17627A",
)

LIGHT_PIXEL_PALETTE = ThemeTokens(
    preset="light_pixel",
    brightness="light",
    visual_style="pixel",
    color_bg_main="#F7F3E8",
    color_bg_alt="#EFE7D4",
    color_bg_rail="#E7DEC8",
    color_bg_surface="#FFFDF4",
    color_bg_surface_hover="#F4EEDC",
    color_bg_surface_pressed="#E8DFC8",
    color_text_main="#121212",
    color_text_secondary="#353530",
    color_text_muted="#5C5C56",
    color_text_inverse="#FFFFFF",
    color_pixel_red="#FF2D20",
    color_pixel_yellow="#FFD43B",
    color_pixel_green="#4FAF2F",
    color_pixel_blue="#007EA8",
    color_pixel_orange="#D66A00",
    color_border_default="#2B2B28",
    color_border_active="#007EA8",
    color_focus_primary="#007EA8",
    color_focus_secondary="#B88900",
    color_success="#2F7D18",
    color_success_bg="#EAF6DF",
    color_success_border="#5F9A3C",
    color_warning="#876400",
    color_warning_bg="#FFF2BA",
    color_warning_border="#B88900",
    color_danger="#C21D14",
    color_danger_bg="#FFE2DA",
    color_danger_border="#C21D14",
    color_info="#006F94",
    color_info_bg="#DFF4FB",
    color_info_border="#007EA8",
)

DARK_PRO_PALETTE = ThemeTokens(
    preset="dark_pro",
    brightness="dark",
    visual_style="pro",
    color_bg_main="#101112",
    color_bg_alt="#151719",
    color_bg_rail="#181A1D",
    color_bg_surface="#202327",
    color_bg_surface_hover="#262A2F",
    color_bg_surface_pressed="#171A1D",
    color_text_main="#F4F5F6",
    color_text_secondary="#D2D5D8",
    color_text_muted="#8E959C",
    color_text_inverse="#0F1113",
    color_pixel_red="#D94A3A",
    color_pixel_yellow="#C79A24",
    color_pixel_green="#4E9C55",
    color_pixel_blue="#2F8AB8",
    color_pixel_orange="#C7772E",
    color_border_default="#343941",
    color_border_active="#3A91C9",
    color_focus_primary="#3A91C9",
    color_focus_secondary="#3A91C9",
    color_success="#57A85E",
    color_success_bg="#132018",
    color_success_border="#356D3C",
    color_warning="#D0A235",
    color_warning_bg="#241D0C",
    color_warning_border="#8A6A20",
    color_danger="#E15B4D",
    color_danger_bg="#271210",
    color_danger_border="#963A31",
    color_info="#4BA3D3",
    color_info_bg="#10202A",
    color_info_border="#2D6D91",
)

LIGHT_PRO_PALETTE = ThemeTokens(
    preset="light_pro",
    brightness="light",
    visual_style="pro",
    color_bg_main="#F5F7F8",
    color_bg_alt="#EEF2F4",
    color_bg_rail="#E7ECEF",
    color_bg_surface="#FFFFFF",
    color_bg_surface_hover="#F0F5F8",
    color_bg_surface_pressed="#E3E9ED",
    color_text_main="#15191D",
    color_text_secondary="#323A42",
    color_text_muted="#68727C",
    color_text_inverse="#FFFFFF",
    color_pixel_red="#B94336",
    color_pixel_yellow="#9B741A",
    color_pixel_green="#3F8547",
    color_pixel_blue="#2279A6",
    color_pixel_orange="#A96224",
    color_border_default="#C9D1D7",
    color_border_active="#2279A6",
    color_focus_primary="#2279A6",
    color_focus_secondary="#2279A6",
    color_success="#347D3D",
    color_success_bg="#E5F2E7",
    color_success_border="#82B887",
    color_warning="#8A6516",
    color_warning_bg="#FFF4D8",
    color_warning_border="#D3AA45",
    color_danger="#B83D32",
    color_danger_bg="#FCE7E3",
    color_danger_border="#D9837A",
    color_info="#2279A6",
    color_info_bg="#E2F2FA",
    color_info_border="#83BBD6",
)

LIGHT_CORAL_PALETTE = replace(
    LIGHT_PRO_PALETTE,
    preset="light_coral",
    color_bg_main="#FFF8F5",
    color_bg_alt="#FCEFEA",
    color_bg_rail="#F7E2DA",
    color_bg_surface_hover="#FFF0EB",
    color_bg_surface_pressed="#FADFD6",
    color_text_main="#2E1B17",
    color_text_secondary="#5A352E",
    color_text_muted="#765C56",
    color_pixel_red="#C74335",
    color_pixel_blue="#C74335",
    color_pixel_orange="#A8542D",
    color_border_default="#E5C8BF",
    color_border_active="#C74335",
    color_focus_primary="#C74335",
    color_focus_secondary="#9E2F25",
)

LIGHT_OCEAN_PALETTE = replace(
    LIGHT_PRO_PALETTE,
    preset="light_ocean",
    color_bg_main="#F3F8FF",
    color_bg_alt="#E7F1FC",
    color_bg_rail="#D9E9FA",
    color_bg_surface_hover="#EAF3FE",
    color_bg_surface_pressed="#D9EAFB",
    color_text_main="#11243A",
    color_text_secondary="#2C465F",
    color_text_muted="#5D7186",
    color_pixel_blue="#1261A0",
    color_border_default="#BED2E7",
    color_border_active="#1261A0",
    color_focus_primary="#1261A0",
    color_focus_secondary="#0B4D84",
    color_info="#1261A0",
    color_info_bg="#E3F1FF",
    color_info_border="#79A9D3",
)

LIGHT_SAGE_PALETTE = replace(
    LIGHT_PRO_PALETTE,
    preset="light_sage",
    color_bg_main="#F6F9F3",
    color_bg_alt="#EDF3E8",
    color_bg_rail="#E0EADB",
    color_bg_surface_hover="#ECF4E8",
    color_bg_surface_pressed="#DCEAD5",
    color_text_main="#1C2B1B",
    color_text_secondary="#3D523B",
    color_text_muted="#657363",
    color_pixel_green="#2F6B3B",
    color_pixel_blue="#2F6B3B",
    color_border_default="#C4D5BE",
    color_border_active="#2F6B3B",
    color_focus_primary="#2F6B3B",
    color_focus_secondary="#24552E",
    color_info="#2F6B3B",
    color_info_bg="#E6F3E5",
    color_info_border="#87B287",
)

LIGHT_LAVENDER_PALETTE = replace(
    LIGHT_PRO_PALETTE,
    preset="light_lavender",
    color_bg_main="#FAF7FF",
    color_bg_alt="#F1ECFA",
    color_bg_rail="#E7DFF4",
    color_bg_surface_hover="#F1EBFA",
    color_bg_surface_pressed="#E4DAF2",
    color_text_main="#261C33",
    color_text_secondary="#4A3A5D",
    color_text_muted="#71627F",
    color_pixel_blue="#6B3FA0",
    color_pixel_red="#A33E77",
    color_border_default="#D2C3E1",
    color_border_active="#6B3FA0",
    color_focus_primary="#6B3FA0",
    color_focus_secondary="#512C7F",
    color_info="#6B3FA0",
    color_info_bg="#F0E6FA",
    color_info_border="#B895D3",
)

LIGHT_SOLAR_PALETTE = replace(
    LIGHT_PRO_PALETTE,
    preset="light_solar",
    color_bg_main="#FFFBF0",
    color_bg_alt="#FFF4D9",
    color_bg_rail="#F7E8BF",
    color_bg_surface_hover="#FFF2CC",
    color_bg_surface_pressed="#F8E3A7",
    color_text_main="#292414",
    color_text_secondary="#51482C",
    color_text_muted="#746B50",
    color_pixel_yellow="#8A5A00",
    color_pixel_blue="#8A5A00",
    color_border_default="#DDC98E",
    color_border_active="#8A5A00",
    color_focus_primary="#8A5A00",
    color_focus_secondary="#6E4800",
    color_info="#795100",
    color_info_bg="#FFF1C7",
    color_info_border="#C99A37",
)

DARK_MIDNIGHT_PALETTE = replace(
    DARK_PRO_PALETTE,
    preset="dark_midnight",
    color_bg_main="#071321",
    color_bg_alt="#0B1B2D",
    color_bg_rail="#0F2238",
    color_bg_surface="#142B45",
    color_bg_surface_hover="#1A3656",
    color_bg_surface_pressed="#0C2035",
    color_text_main="#F2F7FC",
    color_text_secondary="#CAD9E8",
    color_text_muted="#90A8C0",
    color_text_inverse="#06111E",
    color_pixel_blue="#4CA6FF",
    color_border_default="#284765",
    color_border_active="#4CA6FF",
    color_focus_primary="#4CA6FF",
    color_focus_secondary="#7BC0FF",
    color_info="#63B4FF",
    color_info_bg="#0D2942",
    color_info_border="#347CB6",
)

DARK_FOREST_PALETTE = replace(
    DARK_PRO_PALETTE,
    preset="dark_forest",
    color_bg_main="#081711",
    color_bg_alt="#0D2118",
    color_bg_rail="#112A1F",
    color_bg_surface="#173528",
    color_bg_surface_hover="#1D4433",
    color_bg_surface_pressed="#0F291E",
    color_text_main="#F0F8F3",
    color_text_secondary="#C8DDCF",
    color_text_muted="#91AD9A",
    color_text_inverse="#07130D",
    color_pixel_green="#5BC98B",
    color_pixel_blue="#5BC98B",
    color_border_default="#2D5741",
    color_border_active="#5BC98B",
    color_focus_primary="#5BC98B",
    color_focus_secondary="#83DCAA",
    color_info="#6BD49A",
    color_info_bg="#113525",
    color_info_border="#398660",
)

DARK_PLUM_PALETTE = replace(
    DARK_PRO_PALETTE,
    preset="dark_plum",
    color_bg_main="#1A0E1B",
    color_bg_alt="#251227",
    color_bg_rail="#301832",
    color_bg_surface="#3A1F3D",
    color_bg_surface_hover="#4A2850",
    color_bg_surface_pressed="#2B162D",
    color_text_main="#FCF4FD",
    color_text_secondary="#E3CAE6",
    color_text_muted="#B592B9",
    color_text_inverse="#180B19",
    color_pixel_red="#D889E3",
    color_pixel_blue="#D889E3",
    color_border_default="#633C68",
    color_border_active="#D889E3",
    color_focus_primary="#D889E3",
    color_focus_secondary="#EEACEF",
    color_info="#E09AEA",
    color_info_bg="#3B1B40",
    color_info_border="#92539B",
)

DARK_GRAPHITE_PALETTE = replace(
    DARK_PRO_PALETTE,
    preset="dark_graphite",
    color_bg_main="#111214",
    color_bg_alt="#181A1D",
    color_bg_rail="#1F2226",
    color_bg_surface="#292D32",
    color_bg_surface_hover="#343940",
    color_bg_surface_pressed="#202328",
    color_text_main="#F7F5F2",
    color_text_secondary="#D8D2CB",
    color_text_muted="#A29A91",
    color_text_inverse="#14110D",
    color_pixel_orange="#F08A34",
    color_pixel_blue="#F08A34",
    color_border_default="#454B52",
    color_border_active="#F08A34",
    color_focus_primary="#F08A34",
    color_focus_secondary="#FFAB62",
    color_info="#F39A4D",
    color_info_bg="#332114",
    color_info_border="#A65E28",
)

DARK_CONTRAST_PALETTE = replace(
    DARK_PRO_PALETTE,
    preset="dark_contrast",
    color_bg_main="#000000",
    color_bg_alt="#080808",
    color_bg_rail="#101010",
    color_bg_surface="#181818",
    color_bg_surface_hover="#252525",
    color_bg_surface_pressed="#050505",
    color_text_main="#FFFFFF",
    color_text_secondary="#F2F2F2",
    color_text_muted="#C7C7C7",
    color_text_inverse="#000000",
    color_pixel_yellow="#FFD400",
    color_pixel_blue="#FFD400",
    color_border_default="#FFFFFF",
    color_border_active="#FFD400",
    color_focus_primary="#FFD400",
    color_focus_secondary="#00D5FF",
    color_success="#74E987",
    color_warning="#FFD400",
    color_danger="#FF6B6B",
    color_info="#00D5FF",
    color_info_bg="#00242B",
    color_info_border="#00A6C7",
)

DARK_PALETTE = DARK_PIXEL_PALETTE
LIGHT_PALETTE = LIGHT_PIXEL_PALETTE

PALETTES: dict[str, ThemeTokens] = {
    "dark_pro": DARK_PRO_PALETTE,
    "light_pro": LIGHT_PRO_PALETTE,
    "light_coral": LIGHT_CORAL_PALETTE,
    "light_ocean": LIGHT_OCEAN_PALETTE,
    "light_sage": LIGHT_SAGE_PALETTE,
    "light_lavender": LIGHT_LAVENDER_PALETTE,
    "light_solar": LIGHT_SOLAR_PALETTE,
    "dark_midnight": DARK_MIDNIGHT_PALETTE,
    "dark_forest": DARK_FOREST_PALETTE,
    "dark_plum": DARK_PLUM_PALETTE,
    "dark_graphite": DARK_GRAPHITE_PALETTE,
    "dark_contrast": DARK_CONTRAST_PALETTE,
    "dark_pixel": DARK_PIXEL_PALETTE,
    "light_pixel": LIGHT_PIXEL_PALETTE,
    "dark": DARK_PIXEL_PALETTE,
    "light": LIGHT_PIXEL_PALETTE,
}

FONT_UI = (
    '"Segoe UI", Inter, "Noto Sans", "DejaVu Sans", -apple-system, BlinkMacSystemFont, sans-serif'
)

FONT_MONO = (
    '"JetBrains Mono", "IBM Plex Mono", "Fira Code", "DejaVu Sans Mono", '
    '"Cascadia Mono", Consolas, monospace'
)
FONT_PIXEL = FONT_MONO
FONT_FAMILY = FONT_UI

SPACING = {
    "pixel": 4,
    "xs": 4,
    "sm": 8,
    "md": 12,
    "lg": 16,
    "xl": 24,
    "xxl": 32,
    "xxxl": 48,
}

RADIUS = {
    "none": 0,
    "pixel": 2,
    "block": 4,
    "card": 4,
    "dialog": 4,
    "dropzone": 4,
}

SIZES = {
    "button": 40,
    "button_primary": 48,
    "icon_button": 40,
    "sidebar": 288,
    "sidebar_collapsed": 112,
    "dropzone_min": 204,
}


@dataclass(frozen=True)
class DialogLayoutTokens:
    minimum_width: int
    details_minimum_height: int
    margin_horizontal: int
    margin_vertical: int
    spacing: int


UPDATE_DIALOG_LAYOUT = DialogLayoutTokens(
    minimum_width=520,
    details_minimum_height=192,
    margin_horizontal=SPACING["xl"],
    margin_vertical=SPACING["xl"],
    spacing=SPACING["lg"],
)


@dataclass(frozen=True)
class GuidedActionCueTokens:
    frame_interval_ms: int
    wave_duration_ms: int
    pause_duration_ms: int
    overlay_margin_px: int
    static_pen_width_px: int
    band_width_ratio: float
    minimum_band_width_px: int
    band_slant_px: int


GUIDED_ACTION_CUE = GuidedActionCueTokens(
    frame_interval_ms=40,
    wave_duration_ms=960,
    pause_duration_ms=4800,
    overlay_margin_px=4,
    static_pen_width_px=4,
    band_width_ratio=0.34,
    minimum_band_width_px=64,
    band_slant_px=18,
)


ANIMATION = {
    "fast_ms": 80,
    "normal_ms": 120,
    "slow_ms": 160,
    "slide_px": 2,
}

PIXEL_UNIT = 4
GRID_UNIT = 8
BORDER_WIDTH_PIXEL = 2
TRANSITION_FAST = 120

PIXEL_LAYER_OFFSETS = {
    "red": (-2, 2),
    "yellow": (-1, 1),
    "green": (1, 1),
    "blue": (2, -1),
}
