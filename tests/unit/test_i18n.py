from __future__ import annotations

import re

from priveopdf.ui import i18n
from priveopdf.ui.i18n import Locale


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


def test_privacy_by_design_replaces_local_marketing_badge() -> None:
    expected_note = {
        "fr": "Aucun compte. Aucun cloud. Les documents restent sur cet appareil.",
        "en": "No account. No cloud. Documents stay on this device.",
    }
    for locale, note in expected_note.items():
        assert i18n.tr("local.badge", locale) == "PRIVACY BY DESIGN"
        assert i18n.tr("sidebar.local.tooltip", locale) == (f"PRIVACY BY DESIGN\n{note}")


def test_french_interface_addresses_the_user_with_vous() -> None:
    """B23: one form of address; the French help (wiki) also uses "vous"."""

    informal = re.compile(
        r"\b(Choisis|choisis|Clique|clique|Glisse|glisse|Sélectionne|Saisis|Attends|"
        r"Corrige|Réessaie|réessaie|Vérifie-le|Déverrouille-le|choisis-les|réorganise-les)\b"
    )
    offenders = {
        key: value
        for key, value in i18n.TRANSLATIONS["fr"].items()
        if isinstance(value, str) and informal.search(value)
    }

    assert offenders == {}


def test_viewer_file_size_follows_the_interface_language(tmp_path) -> None:  # noqa: ANN001
    from priveopdf.ui.document_workspace import _format_size

    path = tmp_path / "size.pdf"
    path.write_bytes(b"0" * 3000)

    # B20: the viewer used a dot in French ("2.9 Ko"); the unit never wraps alone.
    assert _format_size(path, "fr") == "2,9\u00a0Ko"
    assert _format_size(path, "en") == "2.9\u00a0KB"


def test_page_counts_use_a_real_plural_in_both_languages() -> None:
    from priveopdf.ui.components.tool_flow import page_count_text

    assert page_count_text(1, "fr") == "1 page"
    assert page_count_text(12, "fr") == "12 pages"
    assert page_count_text(12, "en") == "12 pages"
    # B26: "12 page(s)" in Insert and Blank page.
    for locale in ("fr", "en"):
        assert not any("page(s)" in value for value in i18n.TRANSLATIONS[locale].values())
