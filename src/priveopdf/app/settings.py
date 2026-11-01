from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING, Literal, cast

from PySide6.QtCore import QByteArray, QCoreApplication, QSettings, QThread, QTimer

from priveopdf.ui.i18n import Locale, normalize_locale
from priveopdf.ui.theme.tokens import (
    DEFAULT_THEME_PRESET,
    LEGACY_THEME_PRESET_MIGRATIONS,
    SELECTABLE_THEME_PRESETS,
    ThemeMode,
    ThemePreference,
)

if TYPE_CHECKING:
    from priveopdf.app.app_info import ProductChannel
    from priveopdf.app.update_checker import UpdateCheckResult, UpdateStatus

AfterJobBehavior = Literal["none", "open_output_folder"]
PdfOpeningMode = Literal["fit_page", "fit_width"]
# L7 / E11: an A4 page is readable at opening without zooming (new installations).
DEFAULT_PDF_OPENING_MODE: PdfOpeningMode = "fit_width"
WORKSPACE_SESSION_KEY = "documents/open_session"
# 4: existing profiles keep `fit_page` as their PDF opening mode (L7).
SETTINGS_SCHEMA_VERSION = 4
SETTINGS_SCHEMA_VERSION_KEY = "privacy/settings_schema_version"
REMEMBER_OPEN_DOCUMENTS_KEY = "privacy/remember_open_documents"
AUTOMATIC_UPDATE_CHECKS_KEY = "updates/automatic_checks"
AUTOMATIC_UPDATE_CONSENT_KEY = "updates/automatic_checks_consent"
_UPDATE_STATUS_VALUES = {
    "up_to_date",
    "update_available",
    "not_verified",
    "disabled",
    "not_configured",
}
_PRODUCT_CHANNEL_VALUES = {"alpha", "beta", "stable"}
SETTINGS_WRITE_DEBOUNCE_MS = 200


class AppSettings:
    def __init__(self, settings: QSettings | None = None) -> None:
        self._settings = settings or QSettings("PriveoPDF", "PriveoPDF")
        self._sync_timer: QTimer | None = None
        self._sync_pending = False
        self._migrate_settings()

    def theme_preset(self) -> ThemePreference:
        value = str(self._settings.value("ui/theme_preset", "")).strip()
        normalized = normalize_theme_preset(value)
        if normalized is not None:
            return normalized

        legacy_mode = str(self._settings.value("ui/theme_mode", "")).strip()
        if legacy_mode == "light":
            return "light_pixel"
        if legacy_mode == "dark":
            return "dark_pixel"
        return DEFAULT_THEME_PRESET

    def set_theme_preset(self, preset: ThemePreference) -> None:
        normalized = normalize_theme_preset(preset) or DEFAULT_THEME_PRESET
        self._settings.setValue("ui/theme_preset", normalized)
        self._settings.setValue("ui/theme_mode", theme_brightness(normalized))
        self.request_sync()

    def theme_mode(self) -> ThemeMode:
        return theme_brightness(self.theme_preset())

    def set_theme_mode(self, mode: ThemeMode) -> None:
        self.set_theme_preset("light_pixel" if mode == "light" else "dark_pixel")

    def language(self) -> Locale:
        return normalize_locale(str(self._settings.value("ui/language", "en")))

    def set_language(self, locale: Locale) -> None:
        self._settings.setValue("ui/language", normalize_locale(locale))
        self.request_sync()

    def reduce_motion(self) -> bool:
        value = self._settings.value("ui/reduce_motion", False)
        if isinstance(value, bool):
            return value
        return str(value).lower() in {"1", "true", "yes", "on"}

    def set_reduce_motion(self, reduce_motion: bool) -> None:
        self._settings.setValue("ui/reduce_motion", reduce_motion)
        self.request_sync()

    def sidebar_collapsed(self) -> bool:
        value = self._settings.value("ui/sidebar_collapsed", False)
        if isinstance(value, bool):
            return value
        return str(value).lower() in {"1", "true", "yes", "on"}

    def set_sidebar_collapsed(self, collapsed: bool) -> None:
        self._settings.setValue("ui/sidebar_collapsed", collapsed)
        self.request_sync()

    def window_geometry(self) -> QByteArray | None:
        value = self._settings.value("ui/window_geometry")
        if isinstance(value, QByteArray) and not value.isEmpty():
            return value
        return None

    def set_window_geometry(self, geometry: QByteArray) -> None:
        if geometry.isEmpty():
            return
        self._settings.setValue("ui/window_geometry", geometry)
        self.request_sync()

    def initial_setup_completed(self) -> bool:
        return self._bool_value("onboarding/completed", False)

    def set_initial_setup_completed(self, completed: bool) -> None:
        self._settings.setValue("onboarding/completed", completed)
        self.request_sync()

    def has_legacy_user_preferences(self) -> bool:
        return any(
            self._settings.contains(key)
            for key in (
                "ui/language",
                "ui/theme_preset",
                "ui/theme_mode",
                "ui/reduce_motion",
                "ui/sidebar_collapsed",
                "documents/pdf_opening_mode",
                "documents/open_last_pdf_on_startup",
            )
        )

    def should_show_initial_setup(self) -> bool:
        return not self.initial_setup_completed() and not self.has_legacy_user_preferences()

    def automatic_update_checks(self) -> bool:
        if not self._bool_value(AUTOMATIC_UPDATE_CONSENT_KEY, False):
            return False
        return self._bool_value(AUTOMATIC_UPDATE_CHECKS_KEY, False)

    def set_automatic_update_checks(self, enabled: bool) -> None:
        self._settings.setValue(AUTOMATIC_UPDATE_CONSENT_KEY, True)
        self._settings.setValue(AUTOMATIC_UPDATE_CHECKS_KEY, bool(enabled))
        self.request_sync()

    def has_automatic_update_consent(self) -> bool:
        return self._bool_value(AUTOMATIC_UPDATE_CONSENT_KEY, False)

    def update_manifest_url(self) -> str:
        return str(self._settings.value("updates/manifest_url", "")).strip()

    def default_output_dir(self) -> Path | None:
        value = self._settings.value("output/default_dir", "")
        path_text = str(value).strip()
        return Path(path_text) if path_text else None

    def last_open_dir(self) -> Path | None:
        path_text = str(self._settings.value("input/last_dir", "")).strip()
        return Path(path_text) if path_text else None

    def set_last_open_dir(self, directory: Path) -> None:
        self._settings.setValue("input/last_dir", str(directory))
        self.request_sync()

    def set_default_output_dir(self, output_dir: Path | None) -> None:
        if output_dir is None:
            self._settings.remove("output/default_dir")
            self.request_sync()
            return
        self._settings.setValue("output/default_dir", str(output_dir))
        self.request_sync()

    def after_job_behavior(self) -> AfterJobBehavior:
        value = str(self._settings.value("output/after_job_behavior", "none"))
        return "open_output_folder" if value == "open_output_folder" else "none"

    def set_after_job_behavior(self, behavior: AfterJobBehavior) -> None:
        self._settings.setValue(
            "output/after_job_behavior",
            "open_output_folder" if behavior == "open_output_folder" else "none",
        )
        self.request_sync()

    def pdf_opening_mode(self) -> PdfOpeningMode:
        value = str(
            self._settings.value("documents/pdf_opening_mode", DEFAULT_PDF_OPENING_MODE)
        ).strip()
        return normalize_pdf_opening_mode(value) or DEFAULT_PDF_OPENING_MODE

    def set_pdf_opening_mode(self, mode: str) -> None:
        self._settings.setValue(
            "documents/pdf_opening_mode",
            normalize_pdf_opening_mode(mode) or DEFAULT_PDF_OPENING_MODE,
        )
        self.request_sync()

    def open_last_pdf_on_startup(self) -> bool:
        return self.remember_open_documents() and self._bool_value(
            "documents/open_last_pdf_on_startup", False
        )

    def set_open_last_pdf_on_startup(self, enabled: bool) -> None:
        self._settings.setValue(
            "documents/open_last_pdf_on_startup",
            bool(enabled) and self.remember_open_documents(),
        )
        self.request_sync()

    def remember_open_documents(self) -> bool:
        return self._bool_value(REMEMBER_OPEN_DOCUMENTS_KEY, False)

    def set_remember_open_documents(self, enabled: bool) -> None:
        self._settings.setValue(REMEMBER_OPEN_DOCUMENTS_KEY, bool(enabled))
        if enabled:
            self.request_sync()
            return
        self._settings.remove(WORKSPACE_SESSION_KEY)
        self._settings.setValue("documents/open_last_pdf_on_startup", False)
        # Revoking path persistence is privacy-sensitive and must not wait for a timer.
        self.flush()

    def workspace_session_json(self) -> str:
        if not self.remember_open_documents():
            if self._settings.contains(WORKSPACE_SESSION_KEY):
                self._settings.remove(WORKSPACE_SESSION_KEY)
                self.flush()
            return ""
        return str(self._settings.value(WORKSPACE_SESSION_KEY, "")).strip()

    def set_workspace_session_json(self, payload: str) -> None:
        if not self.remember_open_documents():
            if self._settings.contains(WORKSPACE_SESSION_KEY):
                self._settings.remove(WORKSPACE_SESSION_KEY)
                self.flush()
            return
        cleaned = payload.strip()
        if not cleaned:
            self._settings.remove(WORKSPACE_SESSION_KEY)
            self.request_sync()
            return
        self._settings.setValue(WORKSPACE_SESSION_KEY, cleaned)
        self.request_sync()

    def cached_update_check(self, max_age_seconds: int = 24 * 60 * 60) -> UpdateCheckResult | None:
        from priveopdf.app.update_checker import UpdateCheckResult

        checked_at = self._float_value("updates/cache/checked_at", 0.0)
        if checked_at <= 0 or time.time() - checked_at > max_age_seconds:
            return None
        status = _normalize_update_status(str(self._settings.value("updates/cache/status", "")))
        if status is None:
            return None
        channel = _normalize_product_channel(
            str(self._settings.value("updates/cache/channel", "beta"))
        )
        return UpdateCheckResult(
            status=status,
            installed_version=str(self._settings.value("updates/cache/installed_version", "")),
            latest_version=str(self._settings.value("updates/cache/latest_version", "")),
            release_url=str(self._settings.value("updates/cache/release_url", "")),
            release_notes=str(self._settings.value("updates/cache/release_notes", "")),
            checked_at=checked_at,
            error_code=str(self._settings.value("updates/cache/error_code", "")),
            repo_full_name=str(self._settings.value("updates/cache/repo_full_name", "")),
            source=str(self._settings.value("updates/cache/source", "")),
            channel=channel,
        )

    def set_cached_update_check(self, result: UpdateCheckResult) -> None:
        self._settings.setValue("updates/cache/status", result.status)
        self._settings.setValue("updates/cache/installed_version", result.installed_version)
        self._settings.setValue("updates/cache/latest_version", result.latest_version)
        # Remote URLs and notes are intentionally not persisted. A cached available update is
        # rechecked (with consent) before it can become an actionable external link.
        self._settings.remove("updates/cache/release_url")
        self._settings.remove("updates/cache/release_notes")
        self._settings.setValue("updates/cache/checked_at", result.checked_at)
        self._settings.setValue("updates/cache/error_code", result.error_code)
        self._settings.setValue("updates/cache/repo_full_name", result.repo_full_name)
        self._settings.setValue("updates/cache/source", result.source)
        self._settings.setValue("updates/cache/channel", result.channel)
        self.request_sync()

    def clear_local_data(self) -> None:
        """Remove locally persisted paths and caches without touching source documents."""
        self.set_remember_open_documents(False)
        self._settings.remove("output/default_dir")
        self._settings.remove("input/last_dir")
        self._settings.remove("ui/window_geometry")
        self._settings.remove("updates/cache")
        self.flush()
        # N3: Qt's own file dialog remembers its history and last folder in
        # QtProject.conf; they are local data too.
        file_dialog = QSettings(QSettings.Scope.UserScope, "QtProject")
        file_dialog.remove("FileDialog")
        file_dialog.sync()

    def sync(self) -> None:
        """Request a coalesced settings write; use :meth:`flush` before shutdown."""

        self.request_sync()

    def request_sync(self) -> None:
        """Coalesce GUI-thread writes while retaining synchronous non-GUI behavior."""

        self._sync_pending = True
        application = QCoreApplication.instance()
        if application is None or QThread.currentThread() != application.thread():
            self.flush()
            return

        if self._sync_timer is None:
            self._sync_timer = QTimer()
            self._sync_timer.setSingleShot(True)
            self._sync_timer.timeout.connect(self.flush)
        self._sync_timer.start(SETTINGS_WRITE_DEBOUNCE_MS)

    def flush(self) -> None:
        """Force pending settings to disk, notably during application shutdown."""

        if self._sync_timer is not None and self._sync_timer.isActive():
            self._sync_timer.stop()
        self._sync_pending = False
        self._settings.sync()
        _restrict_to_owner(Path(self._settings.fileName()))

    def has_pending_writes(self) -> bool:
        return self._sync_pending

    def _migrate_settings(self) -> None:
        version = self._int_value(SETTINGS_SCHEMA_VERSION_KEY, 0)
        if version >= SETTINGS_SCHEMA_VERSION:
            return
        # A profile already used: first-run setup done, or preferences stored. A
        # profile without either still shows the first-run setup, left untouched.
        existing_profile = self.initial_setup_completed() or self.has_legacy_user_preferences()

        # L7 opens new installations fitted to the width. An existing profile that
        # never chose kept the former default, fitted to the page (Codex review of
        # PR 385): it is written down so that the upgrade changes nothing.
        if existing_profile and not self._settings.contains("documents/pdf_opening_mode"):
            self._settings.setValue("documents/pdf_opening_mode", "fit_page")

        stored_theme = str(self._settings.value("ui/theme_preset", "")).strip()
        normalized_theme = normalize_theme_preset(stored_theme)
        if normalized_theme is None:
            legacy_mode = str(self._settings.value("ui/theme_mode", "")).strip()
            if legacy_mode in {"dark", "light"}:
                normalized_theme = "dark_pixel" if legacy_mode == "dark" else "light_pixel"
        if normalized_theme is not None and normalized_theme != stored_theme:
            self._settings.setValue("ui/theme_preset", normalized_theme)
            self._settings.setValue("ui/theme_mode", theme_brightness(normalized_theme))

        # Historical builds persisted open paths without a dedicated privacy consent.
        # Absence of the new key is not consent, so the legacy payload must be erased.
        if not self._settings.contains(REMEMBER_OPEN_DOCUMENTS_KEY):
            self._settings.remove(WORKSPACE_SESSION_KEY)
            self._settings.setValue(REMEMBER_OPEN_DOCUMENTS_KEY, False)

        # Likewise, a legacy true value does not constitute explicit network consent.
        if not self._settings.contains(AUTOMATIC_UPDATE_CONSENT_KEY):
            self._settings.setValue(AUTOMATIC_UPDATE_CHECKS_KEY, False)

        if not self.remember_open_documents():
            self._settings.remove(WORKSPACE_SESSION_KEY)
            self._settings.remove("documents/open_last_pdf_on_startup")

        self._settings.setValue(SETTINGS_SCHEMA_VERSION_KEY, SETTINGS_SCHEMA_VERSION)
        self._settings.sync()
        _restrict_to_owner(Path(self._settings.fileName()))

    def _bool_value(self, key: str, default: bool) -> bool:
        value = self._settings.value(key, default)
        if isinstance(value, bool):
            return value
        return str(value).lower() in {"1", "true", "yes", "on"}

    def _float_value(self, key: str, default: float) -> float:
        value = self._settings.value(key, default)
        if not isinstance(value, str | int | float):
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _int_value(self, key: str, default: int) -> int:
        value = self._settings.value(key, default)
        if not isinstance(value, str | int):
            return default
        try:
            return int(value)
        except (TypeError, ValueError):
            return default


def normalize_theme_preset(value: str) -> ThemePreference | None:
    if value in SELECTABLE_THEME_PRESETS:
        return cast("ThemePreference", value)
    return LEGACY_THEME_PRESET_MIGRATIONS.get(value)


def theme_brightness(preset: ThemePreference) -> ThemeMode:
    # `system` keeps a deterministic dark fallback here; Qt runtime resolution
    # happens in ThemeManager without replacing the persisted preference.
    return "light" if preset in {"light_pro", "light_pixel"} else "dark"


def normalize_pdf_opening_mode(value: str) -> PdfOpeningMode | None:
    if value in {"fit_page", "fit_width"}:
        return value  # type: ignore[return-value]
    return None


def _normalize_update_status(value: str) -> UpdateStatus | None:
    cleaned = value.strip()
    if cleaned in _UPDATE_STATUS_VALUES:
        return cast("UpdateStatus", cleaned)
    return None


def _normalize_product_channel(value: str) -> ProductChannel:
    cleaned = value.strip()
    if cleaned in _PRODUCT_CHANNEL_VALUES:
        return cast("ProductChannel", cleaned)
    return "beta"


def _restrict_to_owner(path: Path) -> None:
    """Keep the settings private: they hold folders and, with consent, document paths."""

    try:
        if path.is_file() and not path.is_symlink():
            path.chmod(0o600)
        folder = path.parent
        if folder.name == "PriveoPDF" and folder.is_dir() and not folder.is_symlink():
            folder.chmod(0o700)
    except OSError:
        return
