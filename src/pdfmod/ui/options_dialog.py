from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from pdfmod.app.app_info import is_beta_runtime, is_dev_runtime
from pdfmod.app.beta_diagnostics import (
    DiagnosticError,
    export_latest_report,
    is_diagnostic_session,
    latest_diagnostic_session,
    start_diagnostic_session,
    suggested_report_name,
)
from pdfmod.app.beta_versions import (
    BetaVersion,
    BetaVersionError,
    current_beta_version,
    previous_beta_versions,
    relaunch_beta_version,
)
from pdfmod.app.dev_publication import (
    DevPublicationError,
    PublicationMode,
    dev_publication_text,
    queue_publication,
)
from pdfmod.app.settings import AppSettings
from pdfmod.ui.components.buttons import GhostButton, PrimaryButton, SecondaryButton
from pdfmod.ui.components.cards import SurfacePanel
from pdfmod.ui.i18n import SUPPORTED_LANGUAGE_OPTIONS, Locale, tr
from pdfmod.ui.theme.tokens import SELECTABLE_THEME_PRESETS


class OptionsDialog(QDialog):
    preferences_changed = Signal(str, str, bool, bool, str, bool)
    manual_update_check_requested = Signal()

    def __init__(
        self,
        settings: AppSettings,
        locale: Locale,
        parent=None,  # noqa: ANN001
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._locale: Locale = locale
        self._default_output_dir = settings.default_output_dir()
        self.setWindowTitle(tr("options.title", locale))
        self.setModal(True)
        self.resize(620, 700)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        title = QLabel(tr("options.title", locale))
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        scroll = QScrollArea()
        scroll.setObjectName("OptionsScrollArea")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(14)
        content_layout.addWidget(self._build_general_panel())
        content_layout.addWidget(self._build_documents_panel())
        if is_dev_runtime():
            content_layout.addWidget(self._build_dev_publication_panel())
        if is_beta_runtime():
            content_layout.addWidget(self._build_beta_panel())
        content_layout.addWidget(self._build_privacy_panel())
        content_layout.addStretch(1)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        close_button = GhostButton(tr("options.close", locale))
        close_button.clicked.connect(self.reject)
        apply_button = PrimaryButton(tr("options.apply", locale))
        apply_button.clicked.connect(self._apply)
        button_row.addWidget(close_button)
        button_row.addWidget(apply_button)
        layout.addLayout(button_row)

    def _build_general_panel(self) -> SurfacePanel:
        panel = SurfacePanel(role="primary")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        heading = QLabel(tr("options.general", self._locale))
        heading.setObjectName("SectionTitle")
        layout.addWidget(heading)

        self._language_combo = QComboBox()
        for option in SUPPORTED_LANGUAGE_OPTIONS:
            self._language_combo.addItem(tr(option.label_key, self._locale), option.locale)
        self._set_combo_value(self._language_combo, self._settings.language())
        layout.addWidget(_labeled_row(tr("options.language", self._locale), self._language_combo))

        self._theme_combo = QComboBox()
        for key, preset in _theme_preset_options():
            self._theme_combo.addItem(tr(key, self._locale), preset)
        self._set_combo_value(self._theme_combo, self._settings.theme_preset())
        layout.addWidget(_labeled_row(tr("options.theme", self._locale), self._theme_combo))

        self._reduce_motion_checkbox = QCheckBox(tr("options.reduce_motion", self._locale))
        self._reduce_motion_checkbox.setChecked(self._settings.reduce_motion())
        layout.addWidget(self._reduce_motion_checkbox)

        self._update_checks_checkbox = QCheckBox(tr("options.update_checks", self._locale))
        self._update_checks_checkbox.setChecked(self._settings.automatic_update_checks())
        layout.addWidget(self._update_checks_checkbox)
        self._update_status_label = QLabel(_update_status_text(self._settings, self._locale))
        self._update_status_label.setObjectName("HelpText")
        self._update_status_label.setWordWrap(True)
        layout.addWidget(self._update_status_label)
        self._manual_update_check_button = SecondaryButton(
            tr("options.check_updates_now", self._locale)
        )
        self._manual_update_check_button.clicked.connect(self.manual_update_check_requested.emit)
        layout.addWidget(self._manual_update_check_button)
        if is_beta_runtime():
            self._update_checks_checkbox.setVisible(False)
            self._update_status_label.setVisible(False)
            self._manual_update_check_button.setVisible(False)

        self._output_dir_label = QLabel()
        self._output_dir_label.setObjectName("HelpText")
        self._output_dir_label.setWordWrap(True)
        output_buttons = QWidget()
        output_buttons_layout = QHBoxLayout(output_buttons)
        output_buttons_layout.setContentsMargins(0, 0, 0, 0)
        output_buttons_layout.setSpacing(8)
        choose_output_dir_button = SecondaryButton(tr("button.choose_folder", self._locale))
        choose_output_dir_button.clicked.connect(self._choose_default_output_dir)
        clear_output_dir_button = GhostButton(tr("button.clear", self._locale))
        clear_output_dir_button.clicked.connect(self._clear_default_output_dir)
        output_buttons_layout.addWidget(choose_output_dir_button)
        output_buttons_layout.addWidget(clear_output_dir_button)
        layout.addWidget(
            _labeled_row(
                tr("options.default_output_dir", self._locale),
                self._output_dir_label,
                output_buttons,
            )
        )
        self._refresh_output_dir_label()

        self._after_job_combo = QComboBox()
        self._after_job_combo.addItem(tr("options.after_job.none", self._locale), "none")
        self._after_job_combo.addItem(
            tr("options.after_job.open_output_folder", self._locale),
            "open_output_folder",
        )
        self._set_combo_value(self._after_job_combo, self._settings.after_job_behavior())
        layout.addWidget(
            _labeled_row(tr("options.output_behavior", self._locale), self._after_job_combo)
        )

        return panel

    def _build_documents_panel(self) -> SurfacePanel:
        panel = SurfacePanel(role="primary")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        heading = QLabel(tr("options.pdf_reading", self._locale))
        heading.setObjectName("SectionTitle")
        layout.addWidget(heading)

        self._pdf_opening_mode_combo = QComboBox()
        self._pdf_opening_mode_combo.addItem(
            tr("options.pdf_opening_mode.fit_page", self._locale),
            "fit_page",
        )
        self._pdf_opening_mode_combo.addItem(
            tr("options.pdf_opening_mode.fit_width", self._locale),
            "fit_width",
        )
        self._set_combo_value(
            self._pdf_opening_mode_combo,
            self._settings.pdf_opening_mode(),
        )
        layout.addWidget(
            _labeled_row(
                tr("options.pdf_opening_mode", self._locale),
                self._pdf_opening_mode_combo,
            )
        )

        self._open_last_pdf_checkbox = QCheckBox(
            tr("options.open_last_pdf_on_startup", self._locale)
        )
        self._open_last_pdf_checkbox.setChecked(self._settings.open_last_pdf_on_startup())
        self._open_last_pdf_checkbox.setEnabled(self._settings.remember_open_documents())
        layout.addWidget(self._open_last_pdf_checkbox)

        return panel

    def _build_privacy_panel(self) -> SurfacePanel:
        panel = SurfacePanel(role="primary")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        heading = QLabel(tr("options.privacy", self._locale))
        heading.setObjectName("SectionTitle")
        layout.addWidget(heading)

        self._remember_documents_checkbox = QCheckBox(
            tr("options.remember_open_documents", self._locale)
        )
        self._remember_documents_checkbox.setChecked(self._settings.remember_open_documents())
        self._remember_documents_checkbox.toggled.connect(self._remember_documents_toggled)
        layout.addWidget(self._remember_documents_checkbox)

        explanation = QLabel(tr("options.remember_open_documents.help", self._locale))
        explanation.setObjectName("HelpText")
        explanation.setWordWrap(True)
        explanation.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(explanation)

        clear_button = SecondaryButton(tr("options.clear_local_data", self._locale))
        clear_button.clicked.connect(self._clear_local_data)
        layout.addWidget(clear_button)
        return panel

    def _build_dev_publication_panel(self) -> SurfacePanel:
        panel = SurfacePanel(role="primary")
        panel.setObjectName("DevPublicationPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        heading = QLabel(dev_publication_text("heading", self._locale))
        heading.setObjectName("SectionTitle")
        layout.addWidget(heading)

        help_text = QLabel(dev_publication_text("help", self._locale))
        help_text.setObjectName("HelpText")
        help_text.setWordWrap(True)
        help_text.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(help_text)

        check_button = SecondaryButton(dev_publication_text("check", self._locale))
        check_button.clicked.connect(lambda: self._confirm_dev_publication("check"))
        layout.addWidget(check_button)

        publish_button = PrimaryButton(dev_publication_text("publish", self._locale))
        publish_button.clicked.connect(lambda: self._confirm_dev_publication("publish"))
        layout.addWidget(publish_button)
        return panel

    def _confirm_dev_publication(self, mode: PublicationMode) -> None:
        title_key = "check_title" if mode == "check" else "publish_title"
        message_key = "check_message" if mode == "check" else "publish_message"
        action_key = "check" if mode == "check" else "publish"

        dialog = QMessageBox(self)
        dialog.setIcon(
            QMessageBox.Icon.Information if mode == "check" else QMessageBox.Icon.Warning
        )
        dialog.setWindowTitle(dev_publication_text(title_key, self._locale))
        dialog.setText(dev_publication_text(message_key, self._locale))
        dialog.setTextFormat(Qt.TextFormat.PlainText)
        action_button = dialog.addButton(
            dev_publication_text(action_key, self._locale),
            QMessageBox.ButtonRole.AcceptRole,
        )
        dialog.addButton(tr("options.close", self._locale), QMessageBox.ButtonRole.RejectRole)
        dialog.exec()
        if dialog.clickedButton() is not action_button:
            return

        try:
            queue_publication(mode)
        except (DevPublicationError, OSError):
            error_dialog = QMessageBox(self)
            error_dialog.setIcon(QMessageBox.Icon.Critical)
            error_dialog.setWindowTitle(dev_publication_text("queue_error_title", self._locale))
            error_dialog.setText(dev_publication_text("queue_error_message", self._locale))
            error_dialog.setTextFormat(Qt.TextFormat.PlainText)
            error_dialog.exec()
            return

        self.accept()
        application = QApplication.instance()
        if isinstance(application, QApplication):
            application.closeAllWindows()

    def _build_beta_panel(self) -> SurfacePanel:
        panel = SurfacePanel(role="primary")
        panel.setObjectName("BetaVersionsPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        heading = QLabel(tr("options.beta_versions", self._locale))
        heading.setObjectName("SectionTitle")
        layout.addWidget(heading)

        current = current_beta_version()
        current_text = (
            tr(
                "options.beta.current",
                self._locale,
                pr=current.pull_request,
                sha=current.head_sha[:12],
            )
            if current is not None
            else tr("options.beta.current_unavailable", self._locale)
        )
        current_label = QLabel(current_text)
        current_label.setObjectName("HelpText")
        current_label.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(current_label)

        explanation = QLabel(tr("options.beta.help", self._locale))
        explanation.setObjectName("HelpText")
        explanation.setWordWrap(True)
        explanation.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(explanation)

        self._previous_beta_versions = previous_beta_versions()
        self._beta_versions_combo = QComboBox()
        for version in self._previous_beta_versions:
            self._beta_versions_combo.addItem(
                _beta_version_label(version, self._locale),
                version,
            )
        if not self._previous_beta_versions:
            self._beta_versions_combo.addItem(tr("options.beta.none", self._locale), None)
            self._beta_versions_combo.setEnabled(False)
        layout.addWidget(
            _labeled_row(
                tr("options.beta.previous", self._locale),
                self._beta_versions_combo,
            )
        )

        self._relaunch_beta_button = SecondaryButton(tr("options.beta.relaunch", self._locale))
        self._relaunch_beta_button.setEnabled(bool(self._previous_beta_versions))
        self._relaunch_beta_button.clicked.connect(self._relaunch_selected_beta)
        layout.addWidget(self._relaunch_beta_button)

        diagnostic_heading = QLabel(tr("options.beta.diagnostic", self._locale))
        diagnostic_heading.setObjectName("SectionTitle")
        layout.addWidget(diagnostic_heading)

        diagnostic_help = QLabel(tr("options.beta.diagnostic.help", self._locale))
        diagnostic_help.setObjectName("HelpText")
        diagnostic_help.setWordWrap(True)
        diagnostic_help.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(diagnostic_help)

        latest_diagnostic = latest_diagnostic_session()
        if is_diagnostic_session():
            diagnostic_status = tr("options.beta.diagnostic.status.active", self._locale)
        elif latest_diagnostic is None:
            diagnostic_status = tr("options.beta.diagnostic.status.none", self._locale)
        elif latest_diagnostic.is_abnormal:
            diagnostic_status = tr("options.beta.diagnostic.status.abnormal", self._locale)
        else:
            diagnostic_status = tr("options.beta.diagnostic.status.available", self._locale)
        self._diagnostic_status_label = QLabel(diagnostic_status)
        self._diagnostic_status_label.setObjectName("HelpText")
        self._diagnostic_status_label.setWordWrap(True)
        self._diagnostic_status_label.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self._diagnostic_status_label)

        self._start_diagnostic_button = SecondaryButton(
            tr("options.beta.diagnostic.start", self._locale)
        )
        self._start_diagnostic_button.setEnabled(not is_diagnostic_session())
        self._start_diagnostic_button.clicked.connect(self._start_diagnostic)
        layout.addWidget(self._start_diagnostic_button)

        self._export_diagnostic_button = SecondaryButton(
            tr("options.beta.diagnostic.export", self._locale)
        )
        self._export_diagnostic_button.setEnabled(latest_diagnostic is not None)
        self._export_diagnostic_button.clicked.connect(self._export_diagnostic)
        layout.addWidget(self._export_diagnostic_button)
        return panel

    def _start_diagnostic(self) -> None:
        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Warning)
        dialog.setWindowTitle(tr("options.beta.diagnostic.confirm.title", self._locale))
        dialog.setText(tr("options.beta.diagnostic.confirm.message", self._locale))
        dialog.setTextFormat(Qt.TextFormat.PlainText)
        start_button = dialog.addButton(
            tr("options.beta.diagnostic.start", self._locale),
            QMessageBox.ButtonRole.AcceptRole,
        )
        dialog.addButton(tr("options.close", self._locale), QMessageBox.ButtonRole.RejectRole)
        dialog.exec()
        if dialog.clickedButton() is not start_button:
            return
        try:
            start_diagnostic_session()
        except DiagnosticError:
            self._show_diagnostic_error()
            return
        self.accept()
        application = QApplication.instance()
        if isinstance(application, QApplication):
            application.closeAllWindows()

    def _export_diagnostic(self) -> None:
        suggested_path = str(Path.home() / suggested_report_name())
        selected_path, _ = QFileDialog.getSaveFileName(
            self,
            tr("options.beta.diagnostic.export", self._locale),
            suggested_path,
            tr("options.beta.diagnostic.zip_filter", self._locale),
        )
        if not selected_path:
            return
        try:
            output = export_latest_report(Path(selected_path))
        except (DiagnosticError, OSError):
            self._show_diagnostic_error()
            return
        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Information)
        dialog.setWindowTitle(tr("options.beta.diagnostic.exported.title", self._locale))
        dialog.setText(
            tr(
                "options.beta.diagnostic.exported.message",
                self._locale,
                name=output.name,
            )
        )
        dialog.setTextFormat(Qt.TextFormat.PlainText)
        dialog.exec()

    def _show_diagnostic_error(self) -> None:
        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Critical)
        dialog.setWindowTitle(tr("options.beta.diagnostic.error.title", self._locale))
        dialog.setText(tr("options.beta.diagnostic.error.message", self._locale))
        dialog.setTextFormat(Qt.TextFormat.PlainText)
        dialog.exec()

    def _relaunch_selected_beta(self) -> None:
        version = self._beta_versions_combo.currentData()
        if not isinstance(version, BetaVersion):
            return

        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Warning)
        dialog.setWindowTitle(tr("options.beta.confirm.title", self._locale))
        dialog.setText(
            tr(
                "options.beta.confirm.message",
                self._locale,
                pr=version.pull_request,
                sha=version.head_sha[:12],
            )
        )
        dialog.setTextFormat(Qt.TextFormat.PlainText)
        relaunch_button = dialog.addButton(
            tr("options.beta.relaunch", self._locale),
            QMessageBox.ButtonRole.AcceptRole,
        )
        dialog.addButton(tr("options.close", self._locale), QMessageBox.ButtonRole.RejectRole)
        dialog.exec()
        if dialog.clickedButton() is not relaunch_button:
            return

        try:
            relaunch_beta_version(version)
        except BetaVersionError:
            error_dialog = QMessageBox(self)
            error_dialog.setIcon(QMessageBox.Icon.Critical)
            error_dialog.setWindowTitle(tr("options.beta.error.title", self._locale))
            error_dialog.setText(tr("options.beta.error.message", self._locale))
            error_dialog.setTextFormat(Qt.TextFormat.PlainText)
            error_dialog.exec()
            return

        self.accept()
        application = QApplication.instance()
        if isinstance(application, QApplication):
            application.closeAllWindows()

    def _apply(self) -> None:
        locale = self._language_combo.currentData()
        theme = self._theme_combo.currentData()
        reduce_motion = self._reduce_motion_checkbox.isChecked()
        update_checks = self._update_checks_checkbox.isChecked()
        pdf_opening_mode = self._pdf_opening_mode_combo.currentData()
        remember_open_documents = self._remember_documents_checkbox.isChecked()
        open_last_pdf_on_startup = self._open_last_pdf_checkbox.isChecked()
        self._settings.set_language(locale)
        self._settings.set_theme_preset(theme)
        self._settings.set_reduce_motion(reduce_motion)
        self._settings.set_automatic_update_checks(update_checks)
        self._settings.set_default_output_dir(self._default_output_dir)
        self._settings.set_after_job_behavior(self._after_job_combo.currentData())
        self._settings.set_pdf_opening_mode(pdf_opening_mode)
        self._settings.set_remember_open_documents(remember_open_documents)
        self._settings.set_open_last_pdf_on_startup(open_last_pdf_on_startup)
        self._settings.sync()
        self.preferences_changed.emit(
            locale,
            theme,
            reduce_motion,
            update_checks,
            pdf_opening_mode,
            open_last_pdf_on_startup,
        )
        self.accept()

    def set_update_status(self, text: str, *, checking: bool = False) -> None:
        self._update_status_label.setText(text)
        self._update_status_label.setTextFormat(Qt.TextFormat.PlainText)
        self._manual_update_check_button.setEnabled(not checking)

    def _remember_documents_toggled(self, enabled: bool) -> None:
        self._open_last_pdf_checkbox.setEnabled(enabled)
        if not enabled:
            self._open_last_pdf_checkbox.setChecked(False)

    def _clear_local_data(self) -> None:
        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Warning)
        dialog.setWindowTitle(tr("options.clear_local_data.confirm.title", self._locale))
        dialog.setText(tr("options.clear_local_data.confirm.message", self._locale))
        dialog.setTextFormat(Qt.TextFormat.PlainText)
        clear_button = dialog.addButton(
            tr("options.clear_local_data", self._locale),
            QMessageBox.ButtonRole.AcceptRole,
        )
        dialog.addButton(tr("options.close", self._locale), QMessageBox.ButtonRole.RejectRole)
        dialog.exec()
        if dialog.clickedButton() is not clear_button:
            return
        self._settings.clear_local_data()
        self._default_output_dir = None
        self._refresh_output_dir_label()
        self._remember_documents_checkbox.setChecked(False)
        self._open_last_pdf_checkbox.setChecked(False)
        self._open_last_pdf_checkbox.setEnabled(False)

    def _choose_default_output_dir(self) -> None:
        current_dir = str(self._default_output_dir) if self._default_output_dir is not None else ""
        directory = QFileDialog.getExistingDirectory(
            self,
            tr("button.choose_folder", self._locale),
            current_dir,
        )
        if directory:
            self._default_output_dir = Path(directory)
            self._refresh_output_dir_label()

    def _clear_default_output_dir(self) -> None:
        self._default_output_dir = None
        self._refresh_output_dir_label()

    def _refresh_output_dir_label(self) -> None:
        if self._default_output_dir is None:
            self._output_dir_label.setText(tr("options.default_output_dir.empty", self._locale))
            self._output_dir_label.setToolTip("")
            return
        self._output_dir_label.setText(str(self._default_output_dir))
        self._output_dir_label.setToolTip(str(self._default_output_dir))

    def _set_combo_value(self, combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)


def _labeled_row(label_text: str, widget, trailing: QWidget | None = None) -> QWidget:  # noqa: ANN001
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(10)
    label = QLabel(label_text)
    label.setObjectName("SectionTitle")
    layout.addWidget(label, 1)
    layout.addWidget(widget, 2)
    if trailing is not None:
        layout.addWidget(trailing)
    return row


def _theme_preset_options() -> tuple[tuple[str, str], ...]:
    return tuple((f"theme.{preset}", preset) for preset in SELECTABLE_THEME_PRESETS)


def _beta_version_label(version: BetaVersion, locale: Locale) -> str:
    local_date = version.retained_at.astimezone()
    date_format = "%d/%m/%Y %H:%M" if locale == "fr" else "%Y-%m-%d %H:%M"
    return tr(
        "options.beta.item",
        locale,
        pr=version.pull_request,
        sha=version.head_sha[:12],
        date=local_date.strftime(date_format),
    )


def _update_status_text(settings: AppSettings, locale: Locale) -> str:
    if not settings.automatic_update_checks():
        return tr("update.state.disabled", locale)
    if not settings.update_manifest_url():
        return tr("update.state.not_configured", locale)
    return tr("update.state.not_verified", locale)
