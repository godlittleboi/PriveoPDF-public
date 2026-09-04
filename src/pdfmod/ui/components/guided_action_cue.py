from __future__ import annotations

from PySide6.QtCore import QEvent, QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QApplication, QWidget

from pdfmod.ui.theme.tokens import (
    DEFAULT_THEME_PRESET,
    GUIDED_ACTION_CUE,
    PALETTES,
    ThemeTokens,
)


class GuidedActionCue(QWidget):
    """Highlight the single next logical action without intercepting input."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        reduce_motion: bool | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("GuidedActionCue")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._target: QWidget | None = None
        self._target_parent: QWidget | None = None
        self._follow_app_reduce_motion = reduce_motion is None
        self._reduce_motion = _app_reduce_motion() if reduce_motion is None else reduce_motion
        self._wave_elapsed_ms = 0
        self._wave_progress: float | None = None

        self._frame_timer = QTimer(self)
        self._frame_timer.setInterval(GUIDED_ACTION_CUE.frame_interval_ms)
        self._frame_timer.timeout.connect(self._advance_wave)
        self._pause_timer = QTimer(self)
        self._pause_timer.setSingleShot(True)
        self._pause_timer.setInterval(GUIDED_ACTION_CUE.pause_duration_ms)
        self._pause_timer.timeout.connect(self._start_wave)

        self.hide()

    def target(self) -> QWidget | None:
        return self._target

    def is_animating(self) -> bool:
        return self._frame_timer.isActive() or self._pause_timer.isActive()

    def is_wave_active(self) -> bool:
        return self._frame_timer.isActive()

    def set_reduce_motion(self, reduce_motion: bool) -> None:
        if self._reduce_motion == reduce_motion:
            return
        self._reduce_motion = reduce_motion
        self._refresh_animation()
        self.update()

    def set_target(self, target: QWidget | None) -> None:
        if target is self._target:
            self._sync_geometry()
            return
        self.clear()
        if target is None:
            return
        parent = target.parentWidget()
        if parent is None:
            return
        self._target = target
        self._target_parent = parent
        self.setParent(parent)
        _set_required_step(target, True)
        target.destroyed.connect(self._target_destroyed)
        target.installEventFilter(self)
        self._sync_geometry()

    def clear(self) -> None:
        self._stop_cycle()
        if self._target is not None:
            _set_required_step(self._target, False)
            self._target.removeEventFilter(self)
            self._target.destroyed.disconnect(self._target_destroyed)
        self._target = None
        self._target_parent = None
        self.hide()

    def eventFilter(self, watched: object, event: QEvent) -> bool:  # noqa: N802
        event_type = event.type()
        if watched is self._target and event_type in {
            QEvent.Type.EnabledChange,
            QEvent.Type.Hide,
            QEvent.Type.HideToParent,
            QEvent.Type.Move,
            QEvent.Type.ParentChange,
            QEvent.Type.Resize,
            QEvent.Type.Show,
            QEvent.Type.ShowToParent,
            QEvent.Type.StyleChange,
        }:
            if event_type == QEvent.Type.StyleChange and self._follow_app_reduce_motion:
                self.set_reduce_motion(_app_reduce_motion())
            self._sync_geometry()
        return False

    def _target_destroyed(self, *_args: object) -> None:
        self._target = None
        self._target_parent = None
        self._stop_cycle()
        self.hide()

    def paintEvent(self, event) -> None:  # noqa: ANN001, N802
        del event
        if self._target is None:
            return
        margin = GUIDED_ACTION_CUE.overlay_margin_px
        rect = QRectF(self.rect().adjusted(margin, margin, -margin, -margin))
        if not rect.isValid():
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        tokens = _theme_tokens()
        if self._reduce_motion:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(
                QPen(
                    _static_cue_color(tokens),
                    GUIDED_ACTION_CUE.static_pen_width_px,
                )
            )
            painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 4, 4)
            return
        if self._wave_progress is None:
            return

        clip_path = QPainterPath()
        clip_path.addRoundedRect(rect, 4, 4)
        painter.setClipPath(clip_path)
        painter.setPen(Qt.PenStyle.NoPen)
        _draw_wave(painter, rect, self._wave_progress, tokens)

    def _sync_geometry(self) -> None:
        target = self._target
        if target is None:
            return
        parent = target.parentWidget()
        if parent is None:
            self.clear()
            return
        if parent is not self._target_parent:
            self._target_parent = parent
            self.setParent(parent)
        if not target.isEnabled() or not target.isVisible():
            self.hide()
            self._stop_cycle()
            return
        margin = GUIDED_ACTION_CUE.overlay_margin_px
        self.setGeometry(target.geometry().adjusted(-margin, -margin, margin, margin))
        self.raise_()
        self.show()
        self._refresh_animation()
        self.update()

    def _refresh_animation(self) -> None:
        if self._target is None or self.isHidden():
            self._stop_cycle()
            return
        if self._reduce_motion:
            self._stop_cycle()
            self.update()
            return
        if not self.is_animating():
            self._start_wave()

    def _start_wave(self) -> None:
        if self._target is None or self._reduce_motion or self.isHidden():
            self._stop_cycle()
            return
        self._pause_timer.stop()
        self._wave_elapsed_ms = 0
        self._wave_progress = 0.0
        self._frame_timer.start()
        self.update()

    def _advance_wave(self) -> None:
        self._wave_elapsed_ms += GUIDED_ACTION_CUE.frame_interval_ms
        self._wave_progress = min(
            1.0,
            self._wave_elapsed_ms / GUIDED_ACTION_CUE.wave_duration_ms,
        )
        self.update()
        if self._wave_elapsed_ms < GUIDED_ACTION_CUE.wave_duration_ms:
            return
        self._frame_timer.stop()
        self._wave_progress = None
        self.update()
        self._pause_timer.start()

    def _stop_cycle(self) -> None:
        self._frame_timer.stop()
        self._pause_timer.stop()
        self._wave_elapsed_ms = 0
        self._wave_progress = None


def _draw_wave(
    painter: QPainter,
    rect: QRectF,
    progress: float,
    tokens: ThemeTokens,
) -> None:
    colors = _wave_colors(tokens)
    band_width = max(
        GUIDED_ACTION_CUE.minimum_band_width_px,
        rect.width() * GUIDED_ACTION_CUE.band_width_ratio,
    )
    slant = min(GUIDED_ACTION_CUE.band_slant_px, rect.height() * 0.45)
    travel = rect.width() + band_width + (slant * 2)
    wave_left = rect.left() - band_width - slant + (travel * progress)
    stripe_width = band_width / len(colors)
    for index, color in enumerate(colors):
        left = wave_left + (index * stripe_width)
        right = left + stripe_width + 1
        polygon = QPolygonF(
            (
                QPointF(left + slant, rect.top()),
                QPointF(right + slant, rect.top()),
                QPointF(right - slant, rect.bottom()),
                QPointF(left - slant, rect.bottom()),
            )
        )
        painter.setBrush(color)
        painter.drawPolygon(polygon)


def _wave_colors(tokens: ThemeTokens) -> tuple[QColor, ...]:
    if tokens.visual_style == "pixel":
        return tuple(
            _with_alpha(QColor(color), 150)
            for color in (
                tokens.color_pixel_blue,
                tokens.color_pixel_green,
                tokens.color_pixel_yellow,
                tokens.color_pixel_orange,
                tokens.color_pixel_red,
            )
        )
    accent = QColor(tokens.color_focus_primary)
    return tuple(_with_alpha(accent, alpha) for alpha in (34, 58, 92, 126, 78, 42))


def _static_cue_color(tokens: ThemeTokens) -> QColor:
    if tokens.visual_style == "pixel":
        return QColor(
            tokens.color_pixel_yellow if tokens.brightness == "dark" else tokens.color_pixel_orange
        )
    return QColor(tokens.color_focus_primary)


def _with_alpha(color: QColor, alpha: int) -> QColor:
    adjusted = QColor(color)
    adjusted.setAlpha(alpha)
    return adjusted


def _theme_tokens() -> ThemeTokens:
    app = QApplication.instance()
    preset = str(app.property("priveopdf_theme_preset")) if app is not None else ""
    return PALETTES.get(preset, PALETTES[DEFAULT_THEME_PRESET])


def _app_reduce_motion() -> bool:
    app = QApplication.instance()
    return bool(app.property("priveopdf_reduce_motion")) if app is not None else False


def _set_required_step(button: QWidget, required: bool) -> None:
    if button.property("requiredStep") == required:
        return
    button.setProperty("requiredStep", required)
    button.style().unpolish(button)
    button.style().polish(button)
