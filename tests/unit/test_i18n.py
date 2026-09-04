from __future__ import annotations

from pdfmod.ui import i18n
from pdfmod.ui.i18n import Locale


def test_english_is_default_locale() -> None:
    assert i18n.DEFAULT_LOCALE == "en"
    assert i18n.normalize_locale("de") == "en"
    assert i18n.tr("about.title") == "ABOUT"


def test_french_requires_explicit_selection() -> None:
    assert i18n.normalize_locale("fr") == "fr"
    assert i18n.tr("about.title", "fr") == "À PROPOS"


def test_missing_translation_falls_back_to_english(monkeypatch) -> None:  # noqa: ANN001
    french_without_about = {
        key: value for key, value in i18n.TRANSLATIONS["fr"].items() if key != "about.title"
    }
    monkeypatch.setitem(i18n.TRANSLATIONS, "fr", french_without_about)

    assert i18n.tr("about.title", "fr") == "ABOUT"


def test_theme_choice_labels_are_complete_in_french_and_english() -> None:
    expected: dict[Locale, dict[str, str]] = {
        "en": {
            "theme.system": "Automatic — follow system",
            "theme.dark_pro": "Dark — Clean",
            "theme.light_pro": "Light — Clean",
            "theme.dark_pixel": "Dark — Pixel",
            "theme.light_pixel": "Light — Pixel",
            "theme.dark_contrast": "High contrast",
        },
        "fr": {
            "theme.system": "Automatique — suivre le système",
            "theme.dark_pro": "Sombre — Sobre",
            "theme.light_pro": "Clair — Sobre",
            "theme.dark_pixel": "Sombre — Pixel",
            "theme.light_pixel": "Clair — Pixel",
            "theme.dark_contrast": "Contraste élevé",
        },
    }
    for locale, labels in expected.items():
        for key, label in labels.items():
            assert i18n.tr(key, locale) == label
