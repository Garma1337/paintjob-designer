# coding: utf-8

from PySide6.QtCore import Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from paintjob_designer.color.converter import ColorConverter
from paintjob_designer.gui.widget.color_swatch import ColorSwatch
from paintjob_designer.gui.widget.slot_row import SlotRow
from paintjob_designer.models import PsxColor, SlotColors


class SlotEditor(QScrollArea):
    """Grid of slots × 16 color swatches for the current character."""

    color_edit_requested = Signal(str, int)
    slot_reset_requested = Signal(str)
    slot_focus_changed = Signal(object)
    # Right-click context requests. Payload: (slot_name, color_index | -1, global_pos).
    # `color_index == -1` means the right-click landed on the row chrome, not a swatch.
    context_requested = Signal(str, int, object)

    def __init__(self, color_converter: ColorConverter, parent=None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)

        self._converter = color_converter

        self._root = QWidget()
        self._root_layout = QVBoxLayout(self._root)
        self._root_layout.setContentsMargins(8, 8, 8, 8)
        self._root_layout.setSpacing(6)
        self._root_layout.addStretch()
        self.setWidget(self._root)

        self._rows: dict[str, SlotRow] = {}
        self._swatches: dict[tuple[str, int], ColorSwatch] = {}
        self._highlight_buttons: dict[str, QPushButton] = {}
        self._focused_slot: str | None = None

    def set_slots(
        self,
        slot_names: list[str],
        *,
        dimensions: dict[str, str] | None = None,
    ) -> None:
        """(Re)build the grid with one row per slot. Colors start transparent until
        `update_color` is called for each entry.
        """
        self._clear()

        dimensions = dimensions or {}
        for slot_name in slot_names:
            row = self._build_slot_row(slot_name, dimensions.get(slot_name))
            self._rows[slot_name] = row
            self._root_layout.insertWidget(self._root_layout.count() - 1, row)

        # New slot set → previous focus no longer maps to anything; drop it
        # quietly so the 3D viewer returns to "everything visible" state.
        self._set_focus(None)

    def update_color(self, slot_name: str, color_index: int, color: PsxColor) -> None:
        swatch = self._swatches.get((slot_name, color_index))
        if swatch is None:
            return

        if color.is_transparent:
            swatch.set_transparent()
            return

        rgb = self._converter.psx_to_rgb(color)
        swatch.set_color(rgb.r, rgb.g, rgb.b, 0xFF)

    def set_slot_colors(self, slot_name: str, colors: list[PsxColor]) -> None:
        for i, color in enumerate(colors):
            self.update_color(slot_name, i, color)

    def focused_slot(self) -> str | None:
        """Current Highlight-toggle slot, or None if nothing's focused."""
        return self._focused_slot

    def _clear(self) -> None:
        for row in self._rows.values():
            self._root_layout.removeWidget(row)
            row.deleteLater()

        self._rows.clear()
        self._swatches.clear()
        self._highlight_buttons.clear()

    def _build_slot_row(
        self, slot_name: str, dimension_hint: str | None = None,
    ) -> SlotRow:
        row = SlotRow()
        row.setFrameShape(QFrame.Shape.StyledPanel)
        row.right_clicked.connect(
            lambda name=slot_name: self.context_requested.emit(name, -1, QCursor.pos()),
        )

        # Two-row layout: label + swatch grid on top, action buttons below.
        # Keeping buttons under the swatches instead of beside them stops the
        # grid from shrinking when the window narrows — the swatches get the
        # full row width and the button strip is right-aligned underneath.
        row_layout = QVBoxLayout(row)
        row_layout.setContentsMargins(6, 4, 6, 4)
        row_layout.setSpacing(4)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)

        label_text = slot_name
        if dimension_hint:
            label_text = f"{slot_name}  ({dimension_hint})"

        label = QLabel(label_text)
        label.setMinimumWidth(120)
        label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        top.addWidget(label)

        grid = QGridLayout()
        grid.setSpacing(2)

        for i in range(SlotColors.SIZE):
            swatch = ColorSwatch()

            if i == 0:
                # PSX convention: CLUT index 0 is the per-pixel transparency
                # sentinel. Flag it so the user notices before editing.
                swatch.mark_as_transparency_index()

            swatch.clicked.connect(self._emit_edit(slot_name, i))
            swatch.right_clicked.connect(self._emit_context(slot_name, i))
            grid.addWidget(swatch, 0, i)
            self._swatches[(slot_name, i)] = swatch

        top.addLayout(grid)
        top.addStretch()
        row_layout.addLayout(top)

        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 0, 0, 0)
        bottom.addStretch()

        # Checkable "Highlight" toggle — explicit, so opening a color picker
        # doesn't accidentally dim the rest of the kart. Only one slot can be
        # highlighted at a time; clicking an already-highlighted row's button
        # clears focus.
        highlight_button = QPushButton("Highlight")
        highlight_button.setCheckable(True)
        highlight_button.setToolTip(
            "Dim every kart face that doesn't sample this slot, so you can "
            "see exactly where these 16 colors land on the model.",
        )
        highlight_button.setFixedHeight(22)
        highlight_button.clicked.connect(self._emit_highlight_toggle(slot_name))
        bottom.addWidget(highlight_button)
        self._highlight_buttons[slot_name] = highlight_button

        reset_button = QPushButton("Reset")
        reset_button.setToolTip("Revert this slot to the default CLUT colors from the ISO.")
        reset_button.setFixedHeight(22)
        reset_button.clicked.connect(self._emit_reset(slot_name))
        bottom.addWidget(reset_button)

        row_layout.addLayout(bottom)

        return row

    def _emit_edit(self, slot_name: str, color_index: int):
        # Captured-by-value indirection so each swatch's click emits its own
        # (slot_name, index), not whatever the loop variables ended at.
        def handler():
            self.color_edit_requested.emit(slot_name, color_index)

        return handler

    def _emit_reset(self, slot_name: str):
        def handler():
            self.slot_reset_requested.emit(slot_name)

        return handler

    def _emit_context(self, slot_name: str, color_index: int):
        def handler():
            self.context_requested.emit(slot_name, color_index, QCursor.pos())

        return handler

    def _emit_highlight_toggle(self, slot_name: str):
        def handler():
            # Toggle: clicking an already-highlighted row's button clears focus
            # so the user can get back to the un-dimmed view without hunting
            # for an "unfocus" target.
            if self._focused_slot == slot_name:
                self._set_focus(None)
            else:
                self._set_focus(slot_name)

        return handler

    def _set_focus(self, slot_name: str | None) -> None:
        if slot_name == self._focused_slot:
            return

        previous = self._focused_slot
        self._focused_slot = slot_name

        if previous is not None:
            previous_row = self._rows.get(previous)
            if previous_row is not None:
                previous_row.set_focused(False)

            previous_button = self._highlight_buttons.get(previous)
            if previous_button is not None:
                previous_button.setChecked(False)

        if slot_name is not None:
            current_row = self._rows.get(slot_name)
            if current_row is not None:
                current_row.set_focused(True)

            current_button = self._highlight_buttons.get(slot_name)
            if current_button is not None:
                current_button.setChecked(True)

        self.slot_focus_changed.emit(slot_name)
