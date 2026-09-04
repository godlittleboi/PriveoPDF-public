from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QByteArray, QUrl, Signal
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from pdfmod.ui.components import GhostButton, SurfacePanel
from pdfmod.ui.i18n import Locale, tr


@dataclass(frozen=True)
class CommunityDocument:
    key: str
    french_path: str
    english_path: str
    french_label: str
    english_label: str

    def path_for(self, locale: Locale) -> str:
        return self.french_path if locale == "fr" else self.english_path

    def label_for(self, locale: Locale) -> str:
        return self.french_label if locale == "fr" else self.english_label


_DOCUMENT_ORDER = {
    "index.md": 0,
    "getting-started.md": 1,
    "features/README.md": 2,
    "features/view.md": 3,
    "features/merge.md": 4,
    "features/split.md": 5,
    "features/extract.md": 6,
    "features/remove.md": 7,
    "features/reorder.md": 8,
    "features/rotate.md": 9,
    "features/insert.md": 10,
    "features/blank_page.md": 11,
    "privacy.md": 12,
    "faq.md": 13,
    "troubleshooting.md": 14,
    "features/appearance.md": 15,
    "addons/index.md": 16,
}


def discover_community_documents(wiki_root: Path) -> tuple[CommunityDocument, ...]:
    """Return every installed page that exists in both supported wiki locales."""

    french_paths = {
        path.relative_to(wiki_root).as_posix(): path
        for path in wiki_root.rglob("*.md")
        if path.is_file()
        and path != wiki_root / "README.md"
        and path.relative_to(wiki_root).parts[0] != "en"
    }
    english_root = wiki_root / "en"
    english_paths = {
        path.relative_to(english_root).as_posix(): path
        for path in english_root.rglob("*.md")
        if path.is_file()
    }

    return tuple(
        CommunityDocument(
            key=_document_key(relative_path),
            french_path=relative_path,
            english_path=f"en/{relative_path}",
            french_label=_markdown_title(french_paths[relative_path]),
            english_label=_markdown_title(english_paths[relative_path]),
        )
        for relative_path in sorted(
            french_paths.keys() & english_paths.keys(),
            key=_document_sort_key,
        )
    )


def _document_key(relative_path: str) -> str:
    if relative_path == "index.md":
        return "home"
    path = Path(relative_path)
    if path.name in {"README.md", "index.md"}:
        return path.parent.as_posix()
    return path.with_suffix("").as_posix()


def _document_sort_key(relative_path: str) -> tuple[int, str]:
    return (_DOCUMENT_ORDER.get(relative_path, len(_DOCUMENT_ORDER)), relative_path.casefold())


def _markdown_title(path: Path) -> str:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return path.stem.replace("-", " ")
    for line in lines:
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem.replace("-", " ")


class OfflineMarkdownBrowser(QTextBrowser):
    """Render bundled Markdown without resolving any embedded resource."""

    def loadResource(self, resource_type: int, name: QUrl | str) -> object:  # noqa: N802
        del resource_type, name
        return QByteArray()


class CommunityPage(QWidget):
    """Read the release-bundled wiki without opening a network connection."""

    home_requested = Signal()

    def __init__(self, locale: Locale = "en") -> None:
        super().__init__()
        self.setObjectName("CommunityPage")
        self._locale: Locale = locale
        self._wiki_root = _wiki_root()
        self._documents = discover_community_documents(self._wiki_root)
        self._current_document: CommunityDocument | None = None
        self._pending_anchor = ""

        self._description_label = QLabel()
        self._description_label.setObjectName("HelpText")
        self._description_label.setWordWrap(True)

        self._back_button = GhostButton()
        self._back_button.clicked.connect(self.home_requested.emit)

        self._page_label = QLabel()
        self._page_label.setObjectName("SectionTitle")
        self._page_combo = QComboBox()
        self._page_combo.setObjectName("CommunityPageCombo")
        self._page_combo.currentIndexChanged.connect(self._load_selected_document)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.setSpacing(12)
        toolbar.addWidget(self._back_button)
        toolbar.addStretch(1)
        toolbar.addWidget(self._page_label)
        toolbar.addWidget(self._page_combo)

        self._offline_label = QLabel()
        self._offline_label.setObjectName("SectionTitle")

        self._browser = OfflineMarkdownBrowser()
        self._browser.setObjectName("CommunityBrowser")
        self._browser.setOpenExternalLinks(False)
        self._browser.setOpenLinks(False)
        self._browser.anchorClicked.connect(self._open_local_link)

        self._portal_note = QLabel()
        self._portal_note.setObjectName("HelpText")
        self._portal_note.setWordWrap(True)

        panel = SurfacePanel()
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(18, 18, 18, 18)
        panel_layout.setSpacing(12)
        panel_layout.addWidget(self._offline_label)
        panel_layout.addWidget(self._browser, 1)
        panel_layout.addWidget(self._portal_note)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 30, 32, 30)
        layout.setSpacing(16)
        layout.addWidget(self._description_label)
        layout.addLayout(toolbar)
        layout.addWidget(panel, 1)

        self.set_locale(locale)

    def set_locale(self, locale: Locale) -> None:
        selected_key = self._page_combo.currentData()
        self._apply_locale(locale, selected_key)
        self._load_selected_document()

    def _apply_locale(self, locale: Locale, selected_key: object) -> None:
        self._locale = locale
        self._description_label.setText(tr("community.description", locale))
        self._back_button.setText(tr("button.back", locale))
        self._page_label.setText(tr("community.page_label", locale))
        self._offline_label.setText(tr("community.offline_copy", locale))
        self._portal_note.setText(tr("community.portal_note", locale))

        self._page_combo.blockSignals(True)
        self._page_combo.clear()
        selected_index = 0
        for index, document in enumerate(self._documents):
            self._page_combo.addItem(document.label_for(locale), document.key)
            if document.key == selected_key:
                selected_index = index
        self._page_combo.setCurrentIndex(selected_index)
        self._page_combo.blockSignals(False)

    def _load_selected_document(self) -> None:
        key = self._page_combo.currentData()
        document = next(
            (candidate for candidate in self._documents if candidate.key == key),
            None,
        )
        if document is None:
            self._current_document = None
            self._browser.setMarkdown(tr("community.unavailable", self._locale))
            return
        self._current_document = document
        path = self._wiki_root / document.path_for(self._locale)
        try:
            markdown = path.read_text(encoding="utf-8")
        except OSError:
            markdown = tr("community.unavailable", self._locale)
        self._browser.setMarkdown(markdown)
        if self._pending_anchor:
            self._browser.scrollToAnchor(self._pending_anchor)
            self._pending_anchor = ""
        else:
            self._browser.moveCursor(QTextCursor.MoveOperation.Start)
        self._portal_note.setText(tr("community.portal_note", self._locale))

    def _open_local_link(self, url: QUrl) -> None:
        if not url.isRelative() or url.scheme() or url.host():
            self._portal_note.setText(tr("community.link.external_blocked", self._locale))
            return
        if url.hasQuery():
            self._portal_note.setText(tr("community.link.invalid", self._locale))
            return

        encoded_path = url.path(QUrl.ComponentFormattingOption.FullyEncoded)
        raw_path = QUrl.fromPercentEncoding(encoded_path.encode("ascii"))
        if "\\" in raw_path or "\x00" in raw_path:
            self._portal_note.setText(tr("community.link.invalid", self._locale))
            return

        current_path = Path(
            self._current_document.path_for(self._locale)
            if self._current_document is not None
            else ("index.md" if self._locale == "fr" else "en/index.md")
        )
        candidate = self._wiki_root / current_path.parent / (raw_path or current_path.name)
        try:
            relative_path = candidate.resolve().relative_to(self._wiki_root.resolve())
        except (OSError, ValueError):
            self._portal_note.setText(tr("community.link.invalid", self._locale))
            return

        if relative_path.is_absolute() or relative_path.suffix.lower() != ".md":
            self._portal_note.setText(tr("community.link.invalid", self._locale))
            return

        parts = relative_path.parts
        target_locale: Locale = "en" if parts and parts[0] == "en" else "fr"
        logical_path = Path(*parts[1:]) if target_locale == "en" else relative_path
        logical_name = logical_path.as_posix()
        document = next(
            (item for item in self._documents if item.french_path == logical_name),
            None,
        )
        if document is None:
            self._portal_note.setText(tr("community.link.unavailable", self._locale))
            return

        encoded_fragment = url.fragment(QUrl.ComponentFormattingOption.FullyEncoded)
        self._pending_anchor = QUrl.fromPercentEncoding(encoded_fragment.encode("ascii"))
        self._apply_locale(target_locale, document.key)
        self._load_selected_document()


def _wiki_root() -> Path:
    source_root = Path(__file__).resolve().parents[3] / "docs" / "wiki"
    if source_root.is_dir():
        return source_root
    return Path(__file__).resolve().parents[1] / "assets" / "wiki"
