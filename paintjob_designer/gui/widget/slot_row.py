# coding: utf-8

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame


# Stylesheet applied by SlotEditor when a row is the focused slot. Just a
# tinted left border so the active row is obvious without shifting layout.
FOCUSED_STYLE = "QFrame { border-left: 3px solid #3fa9f5; background: #2a2d33; }"


class SlotRow(QFrame):
    """QFrame that reports its own clicks.

    We subclass instead of hooking an eventFilter so child widgets (swatches,
    Reset button) still swallow their own clicks naturally — `mousePressEvent`
    here only fires when the user clicks the row chrome itself.

    Extracted from `slot_editor.py` so the row's click/focus semantics can be
    exercised independently of the whole grid.
    """

    clicked = Signal()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()

        super().mousePressEvent(event)

    def set_focused(self, focused: bool) -> None:
        """Toggle the focus highlight on this row.

        Moving the style-sheet knob onto the row itself keeps `SlotEditor`
        from having to reach into row internals — it just flips this flag on
        the previously-focused row and the newly-focused one.
        """
        self.setStyleSheet(FOCUSED_STYLE if focused else "")
