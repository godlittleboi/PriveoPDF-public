"""Redact a PDF (SEC05/SEC06): draw black-out areas on the page, export a
verified photocopy.

The page-editing skeleton is `ViewerToolPage`; the areas are drawn directly on
the reader (`RedactionTool`, `RedactionOverlay`).
"""

from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QLabel, QVBoxLayout

from priveopdf.domain.jobs import REDACTION_MAX_AREAS, JobResult, OperationType
from priveopdf.ui.components import SecondaryButton, job_result_message, page_count_text
from priveopdf.ui.components.cards import _current_tokens
from priveopdf.ui.components.viewer_tools import RedactionOverlay, RedactionTool
from priveopdf.ui.i18n import Locale, tr
from priveopdf.ui.tool_pages.viewer_tool_page import ViewerToolPage


def redaction_counts(result: JobResult) -> tuple[int, int] | None:
    """(areas, pages) the worker's independent verification established."""
    if len(result.warnings) != 2:
        return None
    counts: list[int] = []
    for prefix, warning in zip(
        ("redaction_areas_", "redaction_pages_"), result.warnings, strict=True
    ):
        value = warning.removeprefix(prefix)
        if value == warning or not value.isdigit():
            return None
        counts.append(int(value))
    return counts[0], counts[1]


class RedactPdfPage(ViewerToolPage):
    SPEC_KEY = "redact_pdf"
    OPERATION = OperationType.REDACT_PDF
    READY_STATUS_KEY = "redact.status.ready"
    FRESH_BLOCKER_KEY = "redact.required.fresh"

    def _build_settings(self, layout: QVBoxLayout) -> None:
        # The output prints annotation appearances (stamps, filled fields):
        # the pages to draw on show them too, the reader's default (review of B5).
        self._tool = RedactionTool()
        self._tool.areas_changed.connect(self._areas_changed)
        self._overlay = RedactionOverlay(self._tool, QColor(_current_tokens().color_danger))
        self._view.add_overlay(self._overlay)
        self._view.set_active_tool(self._tool)
        self._areas_title = QLabel()
        self._areas_title.setObjectName("SectionTitle")
        self._areas_value = QLabel()
        self._areas_value.setObjectName("RotationAngleValue")
        self._areas_help = QLabel()
        self._areas_help.setObjectName("HelpText")
        self._areas_help.setWordWrap(True)
        self._remove_last_button = SecondaryButton()
        self._remove_last_button.clicked.connect(self._tool.remove_last)
        self._clear_button = SecondaryButton()
        self._clear_button.clicked.connect(self._tool.clear)
        for widget in (
            self._areas_title,
            self._areas_value,
            self._areas_help,
            self._remove_last_button,
            self._clear_button,
        ):
            layout.addWidget(widget)

    def _set_settings_texts(self, locale: Locale) -> None:
        self._areas_title.setText(tr("redact.areas.title", locale))
        self._areas_help.setText(tr("redact.areas.help", locale))
        self._remove_last_button.setText(tr("redact.areas.remove_last", locale))
        self._clear_button.setText(tr("redact.areas.clear", locale))
        self._refresh_areas()

    def _reset_settings(self) -> None:
        self._tool.clear()

    def areas(self) -> tuple[tuple[int, float, float, float, float], ...]:
        return self._tool.areas()

    def redaction_tool(self) -> RedactionTool:
        return self._tool

    def _refresh_areas(self) -> None:
        count = len(self._tool.areas())
        running = self._job_runner.is_running()
        self._areas_value.setText(tr("redact.areas.count", self._locale, count=count))
        self._remove_last_button.setEnabled(count > 0 and not running)
        self._clear_button.setEnabled(count > 0 and not running)

    def _areas_changed(self) -> None:
        self._refresh_areas()
        self._settings_changed()

    def _settings_blocker(self) -> str:
        if not self._tool.areas():
            return tr("redact.required.areas", self._locale)
        if len(self._tool.areas()) > REDACTION_MAX_AREAS:
            return tr("redact.required.too_many", self._locale, maximum=REDACTION_MAX_AREAS)
        return ""

    def _job_options(self) -> dict[str, object]:
        areas = self._tool.areas()
        if not areas:
            raise ValueError(tr("redact.required.areas", self._locale))
        return {"areas": areas}

    def _settings_running(self, running: bool) -> None:
        # The drawing tool is the setting: no area can be drawn while the job runs.
        self._view.set_active_tool(None if running else self._tool)
        self._refresh_areas()

    def _result_message(self, result: JobResult) -> str:
        message = job_result_message(result, self._locale, "redact")
        counts = redaction_counts(result) if result.success else None
        if counts is not None:
            areas, pages = counts
            message += "\n" + tr(
                "redact.result",
                self._locale,
                areas=areas,
                pages=page_count_text(pages, self._locale),
            )
        return message
