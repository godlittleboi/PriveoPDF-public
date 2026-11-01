from __future__ import annotations

from typing import Literal

from PySide6.QtWidgets import QWidget

PixelRole = Literal["neutral", "primary", "success", "warning", "danger", "info"]


def apply_pixel_layers(
    widget: QWidget,
    role: PixelRole = "primary",
    raised: bool = False,
) -> None:
    widget.setProperty("pixelRole", role)
    widget.setProperty("pixelRaised", raised)
    refresh_pixel_style(widget)


def set_pixel_raised(widget: QWidget, raised: bool) -> None:
    widget.setProperty("pixelRaised", raised)
    refresh_pixel_style(widget)


def refresh_pixel_style(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()
