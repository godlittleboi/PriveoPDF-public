"""Watermark a PDF (SEC13): write a visible traceability text into every page,
verified after export.

The page-editing skeleton is `ViewerToolPage`; this page adds the text, its
layout and its strength, previewed by a `WatermarkOverlay` (no tool, no mouse).
"""

from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QFormLayout, QLabel, QLineEdit, QVBoxLayout

from priveopdf.domain.jobs import (
    WATERMARK_LAYOUTS,
    WATERMARK_MAX_TEXT,
    WATERMARK_STRENGTHS,
    JobResult,
    OperationType,
    validate_watermark_text,
)
from priveopdf.domain.watermark_layout import OPACITIES, encode_text
from priveopdf.ui.components import job_result_message, page_count_text
from priveopdf.ui.components.viewer_tools import WatermarkOverlay
from priveopdf.ui.i18n import Locale, tr
from priveopdf.ui.theme.tokens import SPACING
from priveopdf.ui.tool_pages.viewer_tool_page import ViewerToolPage


def watermark_pages(result: JobResult) -> int | None:
    """The number of pages the worker's verification found marked."""
    if len(result.warnings) != 1:
        return None
    value = result.warnings[0].removeprefix("watermark_pages_")
    if value == result.warnings[0] or not value.isdigit():
        return None
    return int(value)


class WatermarkPdfPage(ViewerToolPage):
    SPEC_KEY = "watermark"
    OPERATION = OperationType.WATERMARK_PDF
    READY_STATUS_KEY = "watermark.status.ready"
    FRESH_BLOCKER_KEY = "watermark.required.fresh"

    def _build_settings(self, layout: QVBoxLayout) -> None:
        # The preview shows the printed gray of the output, whatever the theme.
        self._overlay = WatermarkOverlay()
        self._view.add_overlay(self._overlay)
        self._settings_title = QLabel()
        self._settings_title.setObjectName("SectionTitle")
        self._text = QLineEdit()
        self._text.setMaxLength(WATERMARK_MAX_TEXT)
        self._text.textChanged.connect(self._options_changed)
        self._text_label = QLabel()
        self._text_help = QLabel()
        self._text_help.setObjectName("HelpText")
        self._text_help.setWordWrap(True)
        self._layout = QComboBox()
        for key in WATERMARK_LAYOUTS:
            self._layout.addItem("", key)
        self._layout.currentIndexChanged.connect(self._options_changed)
        self._layout_label = QLabel()
        self._strength = QComboBox()
        for key in WATERMARK_STRENGTHS:
            self._strength.addItem("", key)
        self._strength.setCurrentIndex(WATERMARK_STRENGTHS.index("medium"))
        self._strength.currentIndexChanged.connect(self._options_changed)
        self._strength_label = QLabel()
        layout.addWidget(self._settings_title)
        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(SPACING["sm"])
        form.addRow(self._text_label, self._text)
        form.addRow(self._layout_label, self._layout)
        form.addRow(self._strength_label, self._strength)
        layout.addLayout(form)
        layout.addWidget(self._text_help)

    def _set_settings_texts(self, locale: Locale) -> None:
        self._settings_title.setText(tr("watermark.settings.title", locale))
        self._text_label.setText(tr("watermark.text.label", locale))
        self._text.setPlaceholderText(tr("watermark.text.placeholder", locale))
        self._text_help.setText(tr("watermark.text.help", locale))
        self._layout_label.setText(tr("watermark.layout.label", locale))
        for index in range(self._layout.count()):
            key = self._layout.itemData(index)
            self._layout.setItemText(index, tr(f"watermark.layout.{key}", locale))
        self._strength_label.setText(tr("watermark.strength.label", locale))
        for index in range(self._strength.count()):
            key = self._strength.itemData(index)
            self._strength.setItemText(index, tr(f"watermark.strength.{key}", locale))

    def watermark(self) -> tuple[str, str, str]:
        """(text, layout, strength) as set on the page."""
        return (
            self._text.text(),
            str(self._layout.currentData()),
            str(self._strength.currentData()),
        )

    def _text_problem(self) -> str:
        """The blocker for the current text, empty when it can be written."""
        text, _layout, _strength = self.watermark()
        if not text.strip():
            return tr("watermark.required.text", self._locale)
        try:
            encode_text(text)
        except ValueError:
            return tr("watermark.required.text_invalid", self._locale)
        return ""

    def _options_changed(self) -> None:
        text, layout, strength = self.watermark()
        shown = "" if self._text_problem() else validate_watermark_text(text)
        self._overlay.set_watermark(shown, layout, OPACITIES[strength])
        self._settings_changed()

    def _settings_blocker(self) -> str:
        return self._text_problem()

    def _job_options(self) -> dict[str, object]:
        problem = self._text_problem()
        if problem:
            raise ValueError(problem)
        text, layout, strength = self.watermark()
        return {"text": validate_watermark_text(text), "layout": layout, "strength": strength}

    def _result_message(self, result: JobResult) -> str:
        message = job_result_message(result, self._locale, "watermark")
        pages = watermark_pages(result) if result.success else None
        if pages is not None:
            message += "\n" + tr(
                "watermark.result", self._locale, pages=page_count_text(pages, self._locale)
            )
        return message
