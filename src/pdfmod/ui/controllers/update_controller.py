from __future__ import annotations

import os
from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pdfmod.app.app_info import is_beta_runtime
from pdfmod.app.network_broker import request_open_release, request_source_install
from pdfmod.app.settings import AppSettings
from pdfmod.app.source_update import (
    SOURCE_UPDATE_KIND,
    SourceUpdateCheckResult,
    is_valid_source_revision,
)
from pdfmod.app.update_checker import (
    DEFAULT_ALLOWED_UPDATE_HOSTS,
    UpdateCheckError,
    UpdateCheckResult,
    validate_https_url,
)
from pdfmod.ui.components import Sidebar
from pdfmod.ui.i18n import Locale, tr
from pdfmod.ui.options_dialog import OptionsDialog
from pdfmod.ui.theme.tokens import UPDATE_DIALOG_LAYOUT
from pdfmod.workers.update_runner import QtUpdateCheckRunner


class UpdateProgressDialog(QDialog):
    """Small non-blocking progress window for an explicit update check."""

    def __init__(self, locale: Locale, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("UpdateProgressDialog")
        self.setWindowTitle(tr("update.progress.title", locale))
        self.setModal(True)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setMinimumWidth(UPDATE_DIALOG_LAYOUT.minimum_width)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            UPDATE_DIALOG_LAYOUT.margin_horizontal,
            UPDATE_DIALOG_LAYOUT.margin_vertical,
            UPDATE_DIALOG_LAYOUT.margin_horizontal,
            UPDATE_DIALOG_LAYOUT.margin_vertical,
        )
        layout.setSpacing(UPDATE_DIALOG_LAYOUT.spacing)

        label = QLabel(tr("update.progress.message", locale))
        label.setObjectName("SectionTitle")
        label.setWordWrap(True)
        layout.addWidget(label)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 0)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setAccessibleName(tr("update.progress.message", locale))
        layout.addWidget(self._progress_bar)


class UpdateController:
    """Coordinate consent, checks, and the isolated installation boundary."""

    def __init__(
        self,
        *,
        parent: QWidget,
        settings: AppSettings,
        sidebar: Sidebar,
        locale: Callable[[], Locale],
        is_closing: Callable[[], bool],
        source_updater_launcher: Callable[[int, str], bool] | None = None,
    ) -> None:
        self._parent = parent
        self._settings = settings
        self._sidebar = sidebar
        self._locale = locale
        self._is_closing = is_closing
        self._source_updater_launcher = source_updater_launcher or _launch_source_update_helper
        self._runner = QtUpdateCheckRunner(parent)
        self._runner.finished.connect(self.handle_finished)
        self._runner.idle.connect(self._start_queued_manual_check)
        self._latest_result: UpdateCheckResult | None = None
        self._manual_check_pending = False
        self._manual_check_queued = False
        self._manual_dialog: OptionsDialog | None = None
        self._queued_manual_dialog: OptionsDialog | None = None
        self._progress_dialog: UpdateProgressDialog | None = None

    @property
    def runner(self) -> QtUpdateCheckRunner:
        return self._runner

    @property
    def latest_result(self) -> UpdateCheckResult | None:
        return self._latest_result

    def set_latest_result(self, result: UpdateCheckResult | None) -> None:
        self._latest_result = result
        self._sidebar.set_update_status(result.status if result is not None else "not_verified")

    def set_disabled(self) -> None:
        self._latest_result = None
        self._sidebar.set_update_status("disabled")

    def set_not_verified(self) -> None:
        self._latest_result = None
        self._sidebar.set_update_status("not_verified")

    def refresh(self) -> None:
        if self._is_closing():
            return
        if is_beta_runtime():
            self.set_disabled()
            return
        if not self._settings.automatic_update_checks():
            self.set_disabled()
            return
        cached_result = self._settings.cached_update_check()
        if (
            cached_result is not None
            and cached_result.source != SOURCE_UPDATE_KIND
            and cached_result.status != "update_available"
        ):
            self._set_result(cached_result)
            return
        if self._runner.is_running():
            return
        self._sidebar.set_update_status("checking")
        self._runner.start(self._settings.update_manifest_url())

    def request_manual_check(self) -> None:
        if is_beta_runtime():
            return
        result = self._latest_result
        if result is not None and result.status == "update_available":
            self.open_dialog()
            return
        if self._confirm_manual_check():
            self._start_manual_check(None)

    def start_manual_check(self, dialog: OptionsDialog) -> None:
        if is_beta_runtime():
            return
        if self._confirm_manual_check():
            self._start_manual_check(dialog)

    def _confirm_manual_check(self) -> bool:
        dialog, continue_button = _build_consent_dialog(self._locale(), self._parent)
        dialog.exec()
        return dialog.clickedButton() is continue_button

    def _start_manual_check(self, dialog: OptionsDialog | None) -> None:
        if self._is_closing() or self._manual_check_pending or self._manual_check_queued:
            return
        if self._runner.is_running():
            self._manual_check_queued = True
            self._queued_manual_dialog = dialog
            self._prepare_manual_check_feedback(dialog)
            return
        self._begin_manual_check(dialog)

    def _begin_manual_check(
        self,
        dialog: OptionsDialog | None,
        *,
        feedback_prepared: bool = False,
    ) -> None:
        self._manual_check_pending = True
        self._manual_dialog = dialog
        if not feedback_prepared:
            self._prepare_manual_check_feedback(dialog)
        self._runner.authorize_source_checkout_once()
        self._runner.start(self._settings.update_manifest_url())

    def _prepare_manual_check_feedback(self, dialog: OptionsDialog | None) -> None:
        if dialog is not None:
            dialog.set_update_status(tr("update.state.checking", self._locale()), checking=True)
        else:
            self._show_progress_dialog()
        self._sidebar.set_update_status("checking")

    def _start_queued_manual_check(self) -> None:
        if not self._manual_check_queued:
            return
        dialog = self._queued_manual_dialog
        self._manual_check_queued = False
        self._queued_manual_dialog = None
        if self._is_closing():
            self._close_progress_dialog()
            return
        self._begin_manual_check(dialog, feedback_prepared=True)

    def _show_progress_dialog(self) -> None:
        self._close_progress_dialog()
        self._progress_dialog = UpdateProgressDialog(self._locale(), self._parent)
        self._progress_dialog.show()

    def _close_progress_dialog(self) -> None:
        if self._progress_dialog is None:
            return
        self._progress_dialog.accept()
        self._progress_dialog.deleteLater()
        self._progress_dialog = None

    def handle_finished(self, result: UpdateCheckResult) -> None:
        if self._is_closing():
            return
        if result.source != SOURCE_UPDATE_KIND:
            self._settings.set_cached_update_check(result)
            self._settings.sync()
        if self._manual_check_pending:
            self._manual_check_pending = False
            self._set_result(result)
            dialog = self._manual_dialog
            self._manual_dialog = None
            self._close_progress_dialog()
            if dialog is not None:
                dialog.set_update_status(self.result_text(result), checking=False)
            elif result.status == "update_available":
                self.open_dialog()
            else:
                _build_result_dialog(
                    result,
                    self._locale(),
                    self.result_text(result),
                    self._parent,
                ).exec()
            return
        if self._settings.automatic_update_checks():
            self._set_result(result)
        else:
            self.set_disabled()

    def open_dialog(self) -> None:
        if is_beta_runtime():
            return
        result = self._latest_result
        if result is None or result.status != "update_available":
            return

        dialog, install_button = _build_update_available_dialog(
            result,
            self._locale(),
            self._parent,
        )
        dialog.exec()
        if dialog.clickedButton() is not install_button:
            return
        if result.source == SOURCE_UPDATE_KIND:
            target_revision = (
                result.target_revision if isinstance(result, SourceUpdateCheckResult) else ""
            )
            self._start_source_installation(target_revision)
            return
        if not result.release_url:
            return
        try:
            validate_https_url(
                result.release_url,
                allowed_hosts=DEFAULT_ALLOWED_UPDATE_HOSTS,
            )
        except UpdateCheckError:
            return
        if not request_open_release():
            _build_install_launch_error(self._locale(), self._parent).exec()

    def _start_source_installation(self, target_revision: str) -> None:
        if self._is_closing() or is_beta_runtime():
            return
        if not is_valid_source_revision(target_revision) or not self._source_updater_launcher(
            os.getpid(),
            target_revision.lower(),
        ):
            _build_install_launch_error(self._locale(), self._parent).exec()
            return
        self._parent.close()

    def status_text(self) -> str:
        result = self._latest_result
        if result is not None:
            return self.result_text(result)
        locale = self._locale()
        if not self._settings.automatic_update_checks():
            return tr("update.state.disabled", locale)
        if not self._settings.update_manifest_url():
            return tr("update.state.not_configured", locale)
        return tr("update.state.checking", locale)

    def result_text(self, result: UpdateCheckResult) -> str:
        locale = self._locale()
        if result.status == "not_verified" and result.error_code:
            return tr(f"update.state.{result.error_code}", locale)
        return tr(f"update.state.{result.status}", locale)

    def _set_result(self, result: UpdateCheckResult) -> None:
        if self._is_closing():
            return
        self._latest_result = result
        self._sidebar.set_update_status(result.status)


def _build_consent_dialog(
    locale: Locale,
    parent: QWidget | None = None,
) -> tuple[QMessageBox, QPushButton]:
    dialog = QMessageBox(parent)
    dialog.setIcon(QMessageBox.Icon.Question)
    dialog.setWindowTitle(tr("update.consent.title", locale))
    dialog.setText(tr("update.consent.message", locale))
    dialog.setInformativeText(tr("update.consent.privacy", locale))
    dialog.setTextFormat(Qt.TextFormat.PlainText)
    continue_button = dialog.addButton(
        tr("update.consent.accept", locale),
        QMessageBox.ButtonRole.AcceptRole,
    )
    dialog.addButton(
        tr("update.consent.decline", locale),
        QMessageBox.ButtonRole.RejectRole,
    )
    _strip_message_box_button_icons(dialog)
    return dialog, continue_button


def _build_result_dialog(
    result: UpdateCheckResult,
    locale: Locale,
    result_text: str,
    parent: QWidget | None = None,
) -> QMessageBox:
    dialog = QMessageBox(parent)
    up_to_date = result.status == "up_to_date"
    dialog.setIcon(QMessageBox.Icon.Information if up_to_date else QMessageBox.Icon.Warning)
    dialog.setWindowTitle(
        tr(
            "update.result.up_to_date.title" if up_to_date else "update.result.failed.title",
            locale,
        )
    )
    dialog.setText(result_text)
    dialog.setTextFormat(Qt.TextFormat.PlainText)
    dialog.addButton(QMessageBox.StandardButton.Ok)
    _strip_message_box_button_icons(dialog)
    return dialog


def _build_update_available_dialog(
    result: UpdateCheckResult,
    locale: Locale,
    parent: QWidget | None = None,
) -> tuple[QMessageBox, QPushButton]:
    source_checkout = result.source == SOURCE_UPDATE_KIND
    notes = _format_release_notes(
        result.release_notes,
        tr("update.dialog.no_notes", locale),
    )
    message = tr(
        "update.dialog.source.available" if source_checkout else "update.dialog.available",
        locale,
        version=result.latest_version,
    )
    details = "\n".join(
        (
            tr(
                "update.dialog.source.installed" if source_checkout else "update.dialog.installed",
                locale,
                version=result.installed_version,
            ),
            tr(
                "update.dialog.source.latest" if source_checkout else "update.dialog.latest",
                locale,
                version=result.latest_version,
            ),
            "",
            tr("update.dialog.changes", locale),
            notes,
        )
    )
    dialog = QMessageBox(parent)
    dialog.setIcon(QMessageBox.Icon.Information)
    dialog.setWindowTitle(tr("update.dialog.title", locale))
    dialog.setText(message)
    dialog.setInformativeText(details)
    dialog.setTextFormat(Qt.TextFormat.PlainText)
    open_button = dialog.addButton(
        tr(
            "update.dialog.source.install" if source_checkout else "update.dialog.install",
            locale,
        ),
        QMessageBox.ButtonRole.AcceptRole,
    )
    dialog.addButton(
        tr("update.dialog.later", locale),
        QMessageBox.ButtonRole.RejectRole,
    )
    _strip_message_box_button_icons(dialog)
    return dialog, open_button


def _build_install_launch_error(
    locale: Locale,
    parent: QWidget | None = None,
) -> QMessageBox:
    dialog = QMessageBox(parent)
    dialog.setIcon(QMessageBox.Icon.Warning)
    dialog.setWindowTitle(tr("update.result.failed.title", locale))
    dialog.setText(tr("update.install.launch_failed", locale))
    dialog.setTextFormat(Qt.TextFormat.PlainText)
    dialog.addButton(QMessageBox.StandardButton.Ok)
    _strip_message_box_button_icons(dialog)
    return dialog


def _strip_message_box_button_icons(dialog: QMessageBox) -> None:
    empty_icon = QIcon()
    for button in dialog.buttons():
        button.setIcon(empty_icon)


def _format_release_notes(notes: str, fallback: str) -> str:
    items: list[str] = []
    for raw_line in notes.splitlines():
        item = raw_line.strip()
        if not item:
            continue
        item = item.lstrip("-*•# ").strip()
        if not item:
            continue
        if len(item) > 240:
            item = f"{item[:237]}..."
        items.append(item)
        if len(items) >= 12:
            break
    if not items:
        items.append(fallback)
    return "\n".join(f"• {item}" for item in items)


def _launch_source_update_helper(parent_pid: int, target_revision: str) -> bool:
    return request_source_install(parent_pid, target_revision)
