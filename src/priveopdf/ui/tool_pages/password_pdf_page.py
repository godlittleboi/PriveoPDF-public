from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from priveopdf.app.settings import AppSettings
from priveopdf.domain.document_context import ToolLaunchContext
from priveopdf.domain.jobs import (
    JobRequest,
    JobResult,
    OperationType,
    ProtectOptions,
    UnlockOptions,
    validate_pdf_password,
)
from priveopdf.ui.components import (
    ElidedLabel,
    GhostButton,
    OutputTargetField,
    PdfInputPanel,
    SecondaryButton,
    SourceCheck,
    SurfacePanel,
    ToolActionBar,
    job_result_message,
    open_output_folder_if_requested,
    output_suffix,
    proposed_output_directory,
)
from priveopdf.ui.i18n import Locale, tr
from priveopdf.ui.theme.tokens import SPACING
from priveopdf.ui.tool_pages.form_tool_page import FormToolPageMixin
from priveopdf.workers.job_runner import QtJobRunner


class PasswordPdfPage(FormToolPageMixin, QWidget):
    back_requested = Signal()
    workspace_files_added = Signal(list, bool)
    job_completed = Signal(object)
    output_pdf_requested = Signal(object)

    def __init__(
        self, operation: OperationType, locale: Locale = "en", settings: AppSettings | None = None
    ) -> None:
        super().__init__()
        self._locale = locale
        self._operation = operation
        self._protecting = operation is OperationType.PROTECT_PDF
        self._tool_key = "protect" if self._protecting else "unlock_pdf"
        self._settings = settings or AppSettings()
        self._input_path: Path | None = None
        self._replaced_input = False
        self._launch_context: ToolLaunchContext | None = None
        self._result: JobResult | None = None
        self._job_runner = QtJobRunner(self)
        self._job_runner.finished.connect(self._operation_finished)
        self._description = QLabel()
        self._description.setObjectName("HelpText")
        self._description.setWordWrap(True)
        self._back = GhostButton()
        self._back.clicked.connect(self.back_requested.emit)
        self._input = PdfInputPanel(multiple=False, locale=locale)
        self._input.paths_selected.connect(self._handle_files)
        self._document = ElidedLabel()
        # L4: the source is checked on load. Unlock reports a PDF that is not
        # protected before asking for any password.
        self._source_check = SourceCheck(locale, unlock_tool=not self._protecting)
        self._source_check.changed.connect(self._update_state)
        self._password_label = QLabel()
        self._password = QLineEdit()
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        self._password.setMaxLength(1024)
        self._password_label.setBuddy(self._password)
        self._confirm_label = QLabel()
        self._confirm = QLineEdit()
        self._confirm.setEchoMode(QLineEdit.EchoMode.Password)
        self._confirm.setMaxLength(1024)
        self._confirm_label.setBuddy(self._confirm)
        self._show_password = SecondaryButton()
        self._show_confirm = SecondaryButton()
        for button, field in (
            (self._show_password, self._password),
            (self._show_confirm, self._confirm),
        ):
            button.setCheckable(True)
            button.toggled.connect(
                lambda shown, field=field, button=button: self._set_secret_visible(
                    field, button, shown
                )
            )
        self._password_help = QLabel()
        self._password_help.setObjectName("HelpText")
        self._password_help.setWordWrap(True)
        self._password.textChanged.connect(self._update_state)
        self._confirm.textChanged.connect(self._update_state)
        self._output = OutputTargetField("file", locale, allow_replace=True)
        self._output.changed.connect(self._destination_changed)
        self._action_bar = ToolActionBar(locale)
        self._action_bar.set_action_text_key(f"password.{self._tool_key}.action")
        self._action_bar.action_requested.connect(self._start)
        self._action_bar.cancel_requested.connect(self._job_runner.cancel)
        self._action_bar.open_pdf_requested.connect(self.output_pdf_requested.emit)
        panel = SurfacePanel(role="primary")
        controls = QVBoxLayout(panel)
        controls.setContentsMargins(*(SPACING["lg"],) * 4)
        controls.setSpacing(SPACING["md"])
        controls.addWidget(self._password_label)
        password_row = QHBoxLayout()
        password_row.addWidget(self._password, 1)
        password_row.addWidget(self._show_password)
        controls.addLayout(password_row)
        controls.addWidget(self._confirm_label)
        confirm_row = QHBoxLayout()
        confirm_row.addWidget(self._confirm, 1)
        confirm_row.addWidget(self._show_confirm)
        controls.addLayout(confirm_row)
        controls.addWidget(self._password_help)
        controls.addWidget(self._output)
        controls.addWidget(self._action_bar)
        self._install_form_layout(panel)
        self.set_locale(locale)

    def _set_input(self, path: Path) -> None:
        if self._job_runner.is_running():
            return
        if path == self._input_path:
            # L4: the same file may have changed (unlocked in place): check it again.
            self._source_check.check([path])
            return
        self._clear_passwords()
        self._input_path = path
        self._result = None
        self._document.setText(path.name)
        self._input.set_loaded(True)
        self._output.clear()
        self._propose_output()
        self._action_bar.clear_result()
        self._source_check.check([path])
        self._update_state()

    def _propose_output(self) -> None:
        source = self._input_path
        if source is not None:
            directory = proposed_output_directory(source, self._settings)
            suffix = output_suffix(self._tool_key, self._locale)
            self._output.propose(directory, source.stem, suffix, source=source)

    def _set_secret_visible(self, field: QLineEdit, button: SecondaryButton, shown: bool) -> None:
        field.setEchoMode(QLineEdit.EchoMode.Normal if shown else QLineEdit.EchoMode.Password)
        button.setText(tr("password.hide" if shown else "password.show", self._locale))
        button.setAccessibleName(
            tr("password.hide_accessible" if shown else "password.show_accessible", self._locale)
        )

    def _clear_passwords(self) -> None:
        # setText(""), not clear(): clear() is undoable, so Show then Ctrl+Z gave
        # the secret back (security finding S1); setText resets the undo history.
        self._password.setText("")
        self._confirm.setText("")
        self._show_password.setChecked(False)
        self._show_confirm.setChecked(False)

    def _destination_changed(self) -> None:
        self._result = None
        self._action_bar.clear_result()
        self._update_state()

    def _build_job(self) -> JobRequest:
        output_path = self._output.path()
        if self._input_path is None or output_path is None:
            raise ValueError("password operation input or destination missing")
        if self._protecting and self._password.text() != self._confirm.text():
            raise ValueError("password confirmation does not match")
        replacing = self._output.replacing()
        return JobRequest(
            self._operation,
            (self._input_path,),
            output_path.parent,
            ProtectOptions(output_path, replace_input=replacing)
            if self._protecting
            else UnlockOptions(output_path, replace_input=replacing),
            password=self._password.text(),
        )

    def _start(self) -> None:
        if self._job_runner.is_running() or self._blocker():
            return
        if self._output.replacing():
            answer = QMessageBox.question(
                self,
                tr("password.replace_title", self._locale),
                tr(
                    "password.replace_confirmation",
                    self._locale,
                    name=self._input_path.name if self._input_path else "",
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self._result = None
        self._replaced_input = self._output.replacing()
        self._job_runner.start(self._build_job())
        self._clear_passwords()
        self._action_bar.set_running(tr("password.progress", self._locale))
        self._update_state()

    def _operation_finished(self, result: JobResult) -> None:
        if result.success and not self._replaced_input:
            # Next free name first: a destination change clears the displayed result.
            self._output.refresh()
        self._result = result
        self._password.setAccessibleName(self._password_label.text())
        self._confirm.setAccessibleName(self._confirm_label.text())
        self._action_bar.finish(result, self._result_message(result))
        if result.success:
            open_output_folder_if_requested(self._settings, result)
        self._update_state()
        # Keep the result visible; encrypted outputs are opened explicitly.
        self.job_completed.emit(result)

    def _result_message(self, result: JobResult) -> str:
        if result.success:
            key = "password.protected" if self._protecting else "password.unlocked"
            if self._replaced_input:
                return tr(key + "_replaced", self._locale)
            return job_result_message(result, self._locale) + "\n" + tr(key, self._locale)
        if result.technical_detail == "dangerous_output" and self._replaced_input:
            return tr("password.error.replacement_refused", self._locale)
        return job_result_message(result, self._locale, "password")

    def _password_state(self) -> tuple[bool, bool]:
        valid_password = False
        if self._password.text():
            try:
                validate_pdf_password(self._password.text())
                valid_password = True
            except (TypeError, ValueError):
                pass
        matches = not self._protecting or self._password.text() == self._confirm.text()
        return valid_password, matches

    def _blocker(self) -> str:
        valid_password, matches = self._password_state()
        if self._input_path is None:
            return tr("tool.required.source", self._locale)
        problem = self._source_check.blocker_text()
        if problem:
            return problem
        if not self._password.text():
            return tr("password.required", self._locale)
        if not valid_password:
            return tr("password.invalid", self._locale)
        if not matches:
            return tr("password.mismatch", self._locale)
        if self._output.path() is None:
            return tr("tool.required.output", self._locale)
        return ""

    def _update_state(self, *_args: object) -> None:
        busy = self._job_runner.is_running()
        for widget in (
            self._input,
            self._password,
            self._confirm,
            self._output,
            self._show_password,
            self._show_confirm,
        ):
            widget.setEnabled(not busy)
        # L4: no password field for a PDF that cannot be processed; a password
        # typed before the problem appeared is not kept behind hidden fields.
        asks_password = not self._source_check.problem()
        if not asks_password and (self._password.text() or self._confirm.text()):
            self._clear_passwords()
        for widget in (self._password_label, self._password, self._show_password):
            widget.setVisible(asks_password)
        self._password_help.setVisible(asks_password)
        self._show_confirm.setVisible(self._protecting and asks_password)
        self._confirm.setVisible(self._protecting and asks_password)
        self._confirm_label.setVisible(self._protecting and asks_password)
        valid_password, matches = self._password_state()
        help_key = "password.help" if self._protecting else "password.help_known"
        if self._password.text() and not valid_password:
            help_key = "password.invalid"
        elif self._protecting and self._confirm.text() and not matches:
            help_key = "password.mismatch"
        self._password_help.setText(tr(help_key, self._locale))
        self._action_bar.set_blocker(self._blocker())

    def set_locale(self, locale: Locale) -> None:
        self._locale = locale
        for widget, key in (
            (self._description, f"tool.{self._tool_key}.description"),
            (self._back, "button.back"),
            (self._password_label, "password.new" if self._protecting else "password.known"),
            (self._confirm_label, "password.confirm"),
        ):
            widget.setText(tr(key, locale))
        for field, button in (
            (self._password, self._show_password),
            (self._confirm, self._show_confirm),
        ):
            self._set_secret_visible(field, button, button.isChecked())
        self._input.set_locale(locale)
        self._source_check.set_locale(locale)
        self._output.set_locale(locale)
        self._action_bar.set_locale(locale)
        self._propose_output()
        self._password.setAccessibleName(self._password_label.text())
        self._confirm.setAccessibleName(self._confirm_label.text())
        if self._result is not None:
            self._action_bar.finish(self._result, self._result_message(self._result))
        self._update_state()

    def hideEvent(self, event) -> None:
        self._clear_passwords()
        # Rule 5: returning to the tool never finds "Replace this PDF" still checked.
        self._output.reset_replace()
        super().hideEvent(event)
