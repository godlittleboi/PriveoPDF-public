from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton, QWidget


def set_button_role(button: QPushButton, role: str) -> QPushButton:
    button.setProperty("role", role)
    button.setCursor(
        Qt.CursorShape.PointingHandCursor if button.isEnabled() else Qt.CursorShape.ArrowCursor
    )
    button.style().unpolish(button)
    button.style().polish(button)
    return button


class StyledButton(QPushButton):
    def __init__(
        self, text: str = "", role: str = "secondary", parent: QWidget | None = None
    ) -> None:
        super().__init__(text, parent)
        set_button_role(self, role)

    def setEnabled(self, enabled: bool) -> None:  # noqa: N802
        super().setEnabled(enabled)
        self.setCursor(Qt.CursorShape.PointingHandCursor if enabled else Qt.CursorShape.ArrowCursor)


class PrimaryButton(StyledButton):
    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, "primary", parent)


class SecondaryButton(StyledButton):
    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, "secondary", parent)


class DangerButton(StyledButton):
    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, "danger", parent)


class GhostButton(StyledButton):
    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, "ghost", parent)


class IconButton(StyledButton):
    def __init__(self, text: str = "", tooltip: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, "ghost", parent)
        self.setFixedSize(40, 40)
        if tooltip:
            self.setToolTip(tooltip)
