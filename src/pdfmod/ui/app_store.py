from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

from pdfmod.app.settings import (
    DEFAULT_PDF_OPENING_MODE,
    PdfOpeningMode,
    normalize_pdf_opening_mode,
    normalize_theme_preset,
)
from pdfmod.ui.i18n import Locale, normalize_locale
from pdfmod.ui.theme.tokens import DEFAULT_THEME_PRESET, ThemePreference
from pdfmod.ui.workspace_state import (
    PageCountStatus,
    WorkspaceDocument,
    WorkspaceInfo,
    WorkspaceState,
)

JobUiStatus = Literal["idle", "running", "succeeded", "failed"]


class SettingsStateSource(Protocol):
    def language(self) -> Locale: ...

    def theme_preset(self) -> ThemePreference: ...

    def reduce_motion(self) -> bool: ...

    def automatic_update_checks(self) -> bool: ...

    def pdf_opening_mode(self) -> PdfOpeningMode: ...


@dataclass(frozen=True)
class UiPreferencesState:
    locale: Locale = "en"
    theme_preset: ThemePreference = DEFAULT_THEME_PRESET
    reduce_motion: bool = False
    update_checks_enabled: bool = True
    pdf_opening_mode: PdfOpeningMode = DEFAULT_PDF_OPENING_MODE


@dataclass(frozen=True)
class JobUiState:
    status: JobUiStatus = "idle"
    tool_key: str | None = None
    message: str | None = None


@dataclass(frozen=True)
class UserMessageState:
    message: str | None = None
    code: str | None = None


@dataclass(frozen=True)
class AppState:
    workspaces: tuple[WorkspaceInfo, ...]
    active_workspace_id: str
    documents: tuple[WorkspaceDocument, ...]
    selected_document_id: str | None
    selected_document: WorkspaceDocument | None
    active_tool_key: str | None
    ui_preferences: UiPreferencesState
    job: JobUiState
    user_error: UserMessageState


class AppStore:
    def __init__(
        self,
        *,
        settings: SettingsStateSource | None = None,
        workspace_state: WorkspaceState | None = None,
        ui_preferences: UiPreferencesState | None = None,
    ) -> None:
        self._workspace_state = workspace_state or WorkspaceState()
        self._active_tool_key: str | None = None
        self._ui_preferences = ui_preferences or _preferences_from_settings(settings)
        self._job = JobUiState()
        self._user_error = UserMessageState()

    def state(self) -> AppState:
        return AppState(
            workspaces=self.workspaces(),
            active_workspace_id=self.active_workspace_id(),
            documents=self.documents(),
            selected_document_id=self.selected_document_id(),
            selected_document=self.selected_document(),
            active_tool_key=self._active_tool_key,
            ui_preferences=self._ui_preferences,
            job=self._job,
            user_error=self._user_error,
        )

    @property
    def active_tool_key(self) -> str | None:
        return self._active_tool_key

    @property
    def ui_preferences(self) -> UiPreferencesState:
        return self._ui_preferences

    @property
    def job(self) -> JobUiState:
        return self._job

    @property
    def user_error(self) -> UserMessageState:
        return self._user_error

    def workspaces(self) -> tuple[WorkspaceInfo, ...]:
        return self._workspace_state.workspaces()

    def active_workspace_id(self) -> str:
        return self._workspace_state.active_workspace_id()

    def active_workspace(self) -> WorkspaceInfo:
        return self._workspace_state.active_workspace()

    def can_add_workspace(self) -> bool:
        return self._workspace_state.can_add_workspace()

    def add_workspace(self) -> WorkspaceInfo | None:
        return self._workspace_state.add_workspace()

    def select_workspace(self, workspace_id: str) -> bool:
        return self._workspace_state.select_workspace(workspace_id)

    def remove_workspace(self, workspace_id: str) -> WorkspaceInfo | None:
        return self._workspace_state.remove_workspace(workspace_id)

    def rename_workspace(self, workspace_id: str, name: str) -> bool:
        return self._workspace_state.rename_workspace(workspace_id, name)

    def documents(self) -> tuple[WorkspaceDocument, ...]:
        return self._workspace_state.documents()

    def selected_document_id(self) -> str | None:
        return self._workspace_state.selected_document_id()

    def selected_document(self) -> WorkspaceDocument | None:
        return self._workspace_state.selected_document()

    def document_by_id(self, document_id: str) -> WorkspaceDocument | None:
        return self._workspace_state.document_by_id(document_id)

    def document_by_path(self, path: Path) -> WorkspaceDocument | None:
        return self._workspace_state.document_by_path(path)

    def add_documents(self, paths: Iterable[Path]) -> tuple[WorkspaceDocument, ...]:
        return self._workspace_state.add_documents(paths)

    def select_document(self, document_id: str) -> bool:
        return self._workspace_state.select_document(document_id)

    def set_documents(self, documents: Iterable[WorkspaceDocument]) -> None:
        self._workspace_state.set_documents(documents)

    def remove_document(self, document_id: str) -> WorkspaceDocument | None:
        return self._workspace_state.remove_document(document_id)

    def set_page_count_status(
        self,
        document_id: str,
        page_count: int | None,
        status: PageCountStatus,
    ) -> None:
        self._workspace_state.set_page_count_status(document_id, page_count, status)

    def set_active_tool_key(self, key: str | None) -> None:
        self._active_tool_key = key.strip() if key else None

    def set_ui_preferences(
        self,
        *,
        locale: str | None = None,
        theme_preset: str | None = None,
        reduce_motion: bool | None = None,
        update_checks_enabled: bool | None = None,
        pdf_opening_mode: str | None = None,
    ) -> None:
        self._ui_preferences = UiPreferencesState(
            locale=(
                normalize_locale(locale) if locale is not None else self._ui_preferences.locale
            ),
            theme_preset=(
                _normalize_theme_preset(theme_preset)
                if theme_preset is not None
                else self._ui_preferences.theme_preset
            ),
            reduce_motion=(
                reduce_motion if reduce_motion is not None else self._ui_preferences.reduce_motion
            ),
            update_checks_enabled=(
                update_checks_enabled
                if update_checks_enabled is not None
                else self._ui_preferences.update_checks_enabled
            ),
            pdf_opening_mode=(
                _normalize_pdf_opening_mode(pdf_opening_mode)
                if pdf_opening_mode is not None
                else self._ui_preferences.pdf_opening_mode
            ),
        )

    def set_job_running(self, tool_key: str | None = None, message: str | None = None) -> None:
        self._job = JobUiState(status="running", tool_key=tool_key, message=message)

    def set_job_succeeded(self, tool_key: str | None = None, message: str | None = None) -> None:
        self._job = JobUiState(status="succeeded", tool_key=tool_key, message=message)

    def set_job_failed(self, tool_key: str | None = None, message: str | None = None) -> None:
        self._job = JobUiState(status="failed", tool_key=tool_key, message=message)

    def clear_job(self) -> None:
        self._job = JobUiState()

    def set_user_error(self, message: str, code: str | None = None) -> None:
        self._user_error = UserMessageState(message=message, code=code)

    def clear_user_error(self) -> None:
        self._user_error = UserMessageState()


def _preferences_from_settings(settings: SettingsStateSource | None) -> UiPreferencesState:
    if settings is None:
        return UiPreferencesState()
    return UiPreferencesState(
        locale=settings.language(),
        theme_preset=settings.theme_preset(),
        reduce_motion=settings.reduce_motion(),
        update_checks_enabled=settings.automatic_update_checks(),
        pdf_opening_mode=settings.pdf_opening_mode(),
    )


def _normalize_theme_preset(value: str) -> ThemePreference:
    return normalize_theme_preset(value) or DEFAULT_THEME_PRESET


def _normalize_pdf_opening_mode(value: str) -> PdfOpeningMode:
    return normalize_pdf_opening_mode(value) or DEFAULT_PDF_OPENING_MODE
