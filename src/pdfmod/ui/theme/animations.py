from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QTimer
from PySide6.QtWidgets import QGraphicsOpacityEffect, QWidget

from pdfmod.ui.theme.tokens import ANIMATION


def fade_in(widget: QWidget, reduce_motion: bool = False) -> None:
    if reduce_motion:
        return
    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)
    animation = QPropertyAnimation(effect, b"opacity", widget)
    animation.setDuration(ANIMATION["normal_ms"])
    animation.setStartValue(0.88)
    animation.setEndValue(1.0)
    animation.setEasingCurve(QEasingCurve.Type.OutCubic)
    animation.finished.connect(lambda: widget.setGraphicsEffect(None))
    widget._priveopdf_fade_animation = animation  # type: ignore[attr-defined]
    animation.start()


def set_transient_property(
    widget: QWidget,
    property_name: str,
    active_value: object,
    inactive_value: object,
    duration_ms: int = ANIMATION["normal_ms"],
) -> None:
    widget.setProperty(property_name, active_value)
    _refresh_style(widget)

    def reset() -> None:
        widget.setProperty(property_name, inactive_value)
        _refresh_style(widget)

    QTimer.singleShot(duration_ms, reset)


def _refresh_style(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()
