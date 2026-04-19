# coding: utf-8

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame


# Stylesheet applied by SlotEditor when a row is the focused slot. Just a
# tinted left border so the active row is obvious without shifting layout.
FOCUSED_STYLE = "QFrame { border-left: 3px solid #3fa9f5; background: #2a2d33; }"


class SlotRow(QFrame):
    """QFrame that reports right-click context requests.

    We subclass instead of hooking an eventFilter so child widgets (swatches,
    Highlight / Reset buttons) still swallow their own clicks naturally —
    `mousePressEvent` here only fires when the user right-clicks the row
    chrome itself (for the Transform Colors context menu).

    Left-clicks on the row chrome are intentionally ignored: slot highlight
    is an explicit opt-in via the row's Highlight button, not something the
    user triggers by clicking near a swatch.
    """

    right_clicked = Signal()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.RightButton:
            self.right_clicked.emit()

        super().mousePressEvent(event)

    def set_focused(self, focused: bool) -> None:
        """Toggle the focus highlight on this row.

        Moving the style-sheet knob onto the row itself keeps `SlotEditor`
        from having to reach into row internals — it just flips this flag on
        the previously-focused row and the newly-focused one.
        """
        self.setStyleSheet(FOCUSED_STYLE if focused else "")
