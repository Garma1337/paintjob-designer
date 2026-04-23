# coding: utf-8

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame


# Stylesheet applied by SlotEditor when a row is the focused slot. Just a
# tinted left border so the active row is obvious without shifting layout.
FOCUSED_STYLE = "QFrame { border-left: 3px solid #3fa9f5; background: #2a2d33; }"


class SlotRow(QFrame):
    """QFrame that reports right-click context requests."""

    right_clicked = Signal()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.RightButton:
            self.right_clicked.emit()

        super().mousePressEvent(event)

    def set_focused(self, focused: bool) -> None:
        """Toggle the focus highlight on this row."""
        self.setStyleSheet(FOCUSED_STYLE if focused else "")
