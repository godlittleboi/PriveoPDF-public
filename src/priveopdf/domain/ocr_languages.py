"""Tesseract language models: code validation and display names.

A model is a file ``<code>.traineddata`` of the system package
``tesseract-ocr-<code>`` (Debian/Ubuntu). PriveoPDF proposes every installed
model; it never bundles nor downloads one. ``OCR_BASELINE_LANGUAGES`` stay
visible in the tool even when absent, with the command that installs them.

The code reaches a file name and the native engine: it is validated before any
use. ``osd`` (orientation) and ``equ`` (equations) are not languages.
"""

from __future__ import annotations

import re
from pathlib import Path

OCR_BASELINE_LANGUAGES: tuple[str, ...] = ("eng", "fra", "spa")
OCR_MAX_SELECTED_LANGUAGES = 3
_MODEL_CODE = re.compile(r"^[a-z]{3}(_[a-z]+)*$")
_NOT_LANGUAGES = frozenset({"osd", "equ"})

# Debian/Ubuntu `tesseract-ocr-<code>` packages: (French name, English name).
# Scripts (`script/*`) and legacy `frk` are left out: not offered as languages.
OCR_LANGUAGE_NAMES: dict[str, tuple[str, str]] = {
    "afr": ("Afrikaans", "Afrikaans"),
    "amh": ("Amharique", "Amharic"),
    "ara": ("Arabe", "Arabic"),
    "asm": ("Assamais", "Assamese"),
    "aze": ("Azéri", "Azerbaijani"),
    "aze_cyrl": ("Azéri (cyrillique)", "Azerbaijani (Cyrillic)"),
    "bel": ("Biélorusse", "Belarusian"),
    "ben": ("Bengali", "Bengali"),
    "bod": ("Tibétain", "Tibetan"),
    "bos": ("Bosnien", "Bosnian"),
    "bre": ("Breton", "Breton"),
    "bul": ("Bulgare", "Bulgarian"),
    "cat": ("Catalan", "Catalan"),
    "ceb": ("Cebuano", "Cebuano"),
    "ces": ("Tchèque", "Czech"),
    "chi_sim": ("Chinois simplifié", "Chinese (Simplified)"),
    "chi_sim_vert": ("Chinois simplifié (vertical)", "Chinese (Simplified, vertical)"),
    "chi_tra": ("Chinois traditionnel", "Chinese (Traditional)"),
    "chi_tra_vert": ("Chinois traditionnel (vertical)", "Chinese (Traditional, vertical)"),
    "chr": ("Cherokee", "Cherokee"),
    "cos": ("Corse", "Corsican"),
    "cym": ("Gallois", "Welsh"),
    "dan": ("Danois", "Danish"),
    "deu": ("Allemand", "German"),
    "div": ("Maldivien", "Dhivehi"),
    "dzo": ("Dzongkha", "Dzongkha"),
    "ell": ("Grec", "Greek"),
    "eng": ("Anglais", "English"),
    "enm": ("Moyen anglais", "Middle English"),
    "epo": ("Espéranto", "Esperanto"),
    "est": ("Estonien", "Estonian"),
    "eus": ("Basque", "Basque"),
    "fao": ("Féroïen", "Faroese"),
    "fas": ("Persan", "Persian"),
    "fil": ("Filipino", "Filipino"),
    "fin": ("Finnois", "Finnish"),
    "fra": ("Français", "French"),
    "frm": ("Moyen français", "Middle French"),
    "fry": ("Frison occidental", "Western Frisian"),
    "gla": ("Gaélique écossais", "Scottish Gaelic"),
    "gle": ("Irlandais", "Irish"),
    "glg": ("Galicien", "Galician"),
    "grc": ("Grec ancien", "Ancient Greek"),
    "guj": ("Gujarati", "Gujarati"),
    "hat": ("Créole haïtien", "Haitian Creole"),
    "heb": ("Hébreu", "Hebrew"),
    "hin": ("Hindi", "Hindi"),
    "hrv": ("Croate", "Croatian"),
    "hun": ("Hongrois", "Hungarian"),
    "hye": ("Arménien", "Armenian"),
    "iku": ("Inuktitut", "Inuktitut"),
    "ind": ("Indonésien", "Indonesian"),
    "isl": ("Islandais", "Icelandic"),
    "ita": ("Italien", "Italian"),
    "ita_old": ("Italien ancien", "Italian (old)"),
    "jav": ("Javanais", "Javanese"),
    "jpn": ("Japonais", "Japanese"),
    "jpn_vert": ("Japonais (vertical)", "Japanese (vertical)"),
    "kan": ("Kannada", "Kannada"),
    "kat": ("Géorgien", "Georgian"),
    "kat_old": ("Géorgien ancien", "Georgian (old)"),
    "kaz": ("Kazakh", "Kazakh"),
    "khm": ("Khmer", "Khmer"),
    "kir": ("Kirghize", "Kyrgyz"),
    "kmr": ("Kurde (kurmandji)", "Kurdish (Kurmanji)"),
    "kor": ("Coréen", "Korean"),
    "kor_vert": ("Coréen (vertical)", "Korean (vertical)"),
    "lao": ("Lao", "Lao"),
    "lat": ("Latin", "Latin"),
    "lav": ("Letton", "Latvian"),
    "lit": ("Lituanien", "Lithuanian"),
    "ltz": ("Luxembourgeois", "Luxembourgish"),
    "mal": ("Malayalam", "Malayalam"),
    "mar": ("Marathi", "Marathi"),
    "mkd": ("Macédonien", "Macedonian"),
    "mlt": ("Maltais", "Maltese"),
    "mon": ("Mongol", "Mongolian"),
    "mri": ("Maori", "Maori"),
    "msa": ("Malais", "Malay"),
    "mya": ("Birman", "Burmese"),
    "nep": ("Népalais", "Nepali"),
    "nld": ("Néerlandais", "Dutch"),
    "nor": ("Norvégien", "Norwegian"),
    "oci": ("Occitan", "Occitan"),
    "ori": ("Odia", "Odia"),
    "pan": ("Pendjabi", "Punjabi"),
    "pol": ("Polonais", "Polish"),
    "por": ("Portugais", "Portuguese"),
    "pus": ("Pachto", "Pashto"),
    "que": ("Quechua", "Quechua"),
    "ron": ("Roumain", "Romanian"),
    "rus": ("Russe", "Russian"),
    "san": ("Sanskrit", "Sanskrit"),
    "sin": ("Cingalais", "Sinhala"),
    "slk": ("Slovaque", "Slovak"),
    "slv": ("Slovène", "Slovenian"),
    "snd": ("Sindhi", "Sindhi"),
    "spa": ("Espagnol", "Spanish"),
    "spa_old": ("Espagnol ancien", "Spanish (old)"),
    "sqi": ("Albanais", "Albanian"),
    "srp": ("Serbe", "Serbian"),
    "srp_latn": ("Serbe (latin)", "Serbian (Latin)"),
    "sun": ("Soundanais", "Sundanese"),
    "swa": ("Swahili", "Swahili"),
    "swe": ("Suédois", "Swedish"),
    "syr": ("Syriaque", "Syriac"),
    "tam": ("Tamoul", "Tamil"),
    "tat": ("Tatar", "Tatar"),
    "tel": ("Télougou", "Telugu"),
    "tgk": ("Tadjik", "Tajik"),
    "tgl": ("Tagalog", "Tagalog"),
    "tha": ("Thaï", "Thai"),
    "tir": ("Tigrigna", "Tigrinya"),
    "ton": ("Tongien", "Tongan"),
    "tur": ("Turc", "Turkish"),
    "uig": ("Ouïghour", "Uyghur"),
    "ukr": ("Ukrainien", "Ukrainian"),
    "urd": ("Ourdou", "Urdu"),
    "uzb": ("Ouzbek", "Uzbek"),
    "uzb_cyrl": ("Ouzbek (cyrillique)", "Uzbek (Cyrillic)"),
    "vie": ("Vietnamien", "Vietnamese"),
    "yid": ("Yiddish", "Yiddish"),
    "yor": ("Yoruba", "Yoruba"),
}


def is_ocr_language_code(code: object) -> bool:
    """A Tesseract model code usable as a language: strict shape, never a path."""

    return (
        type(code) is str
        and len(code) <= 16
        and _MODEL_CODE.match(code) is not None
        and code not in _NOT_LANGUAGES
    )


def validate_ocr_languages(languages: object) -> tuple[str, ...]:
    """One to three distinct language codes; the caller checks installation."""

    if (
        not isinstance(languages, (list, tuple))
        or not 1 <= len(languages) <= OCR_MAX_SELECTED_LANGUAGES
        or any(not is_ocr_language_code(code) for code in languages)
        or len(set(languages)) != len(languages)
    ):
        raise ValueError("OCR languages must be one to three distinct model codes")
    return tuple(languages)


def ocr_language_name(code: str, locale: str) -> str:
    """Display name in the interface language; the code itself when unknown."""

    names = OCR_LANGUAGE_NAMES.get(code)
    if names is None:
        return code
    return names[0] if locale == "fr" else names[1]


def installed_ocr_languages(tessdata: Path, locale: str = "fr") -> tuple[str, ...]:
    """Codes of the installed models: baseline languages first (contract order),
    then the others sorted by their display name."""

    try:
        files = tuple(tessdata.glob("*.traineddata"))
    except OSError:
        return ()
    installed = {
        path.name[: -len(".traineddata")]
        for path in files
        if path.is_file() and is_ocr_language_code(path.name[: -len(".traineddata")])
    }
    baseline = tuple(code for code in OCR_BASELINE_LANGUAGES if code in installed)
    others = sorted(
        installed - set(OCR_BASELINE_LANGUAGES), key=lambda c: ocr_language_name(c, locale)
    )
    return (*baseline, *others)
