# coding: utf-8

from PySide6.QtCore import Qt, Signal
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
    """Grid of slots × 16 color swatches for the current character.

    Emits:
        - `color_edit_requested(slot_name, color_index)` when a swatch is clicked.
        - `slot_reset_requested(slot_name)` when a row's Reset button is clicked.
        - `slot_focus_changed(slot_name | None)` when the active row changes.
          The main window uses it to highlight the matching 3D triangles and
          atlas regions.

    The main window wires all three signals to its handlers; the widget itself
    stays dumb about VRAM, paintjobs, or undo.
    """

    color_edit_requested = Signal(str, int)
    slot_reset_requested = Signal(str)
    slot_focus_changed = Signal(object)

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
        self._focused_slot: str | None = None

    def set_slots(self, slot_names: list[str]) -> None:
        """(Re)build the grid with one row per slot. Colors start transparent until
        `update_color` is called for each entry.
        """
        self._clear()

        for slot_name in slot_names:
            row = self._build_slot_row(slot_name)
            self._rows[slot_name] = row
            self._root_layout.insertWidget(self._root_layout.count() - 1, row)

        # New slot set → previous focus no longer maps to anything; drop it
        # quietly so the 3D viewer returns to "everything visible" state.
        self._set_focus(None)

    def update_color(self, slot_name: str, color_index: int, color: PsxColor) -> None:
        swatch = self._swatches.get((slot_name, color_index))
        if swatch is None:
            return

        if color.value == 0:
            swatch.set_transparent()
            return

        rgb = self._converter.psx_to_rgb(color)
        swatch.set_color(rgb.r, rgb.g, rgb.b, 0xFF)

    def set_slot_colors(self, slot_name: str, colors: list[PsxColor]) -> None:
        for i, color in enumerate(colors):
            self.update_color(slot_name, i, color)

    def _clear(self) -> None:
        for row in self._rows.values():
            self._root_layout.removeWidget(row)
            row.deleteLater()

        self._rows.clear()
        self._swatches.clear()

    def _build_slot_row(self, slot_name: str) -> SlotRow:
        row = SlotRow()
        row.setFrameShape(QFrame.Shape.StyledPanel)
        row.setCursor(Qt.CursorShape.PointingHandCursor)
        row.setToolTip("Click to highlight this slot's regions in the 3D view and atlas.")
        row.clicked.connect(lambda name=slot_name: self._on_row_clicked(name))
        layout = QHBoxLayout(row)
        layout.setContentsMargins(6, 4, 6, 4)

        label = QLabel(slot_name)
        label.setMinimumWidth(80)
        label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        layout.addWidget(label)

        grid = QGridLayout()
        grid.setSpacing(2)

        for i in range(SlotColors.SIZE):
            swatch = ColorSwatch()

            if i == 0:
                # PSX convention: CLUT index 0 is the per-pixel transparency
                # sentinel. Flag it so the user notices before editing.
                swatch.mark_as_transparency_index()

            swatch.clicked.connect(self._emit_edit(slot_name, i))
            grid.addWidget(swatch, 0, i)
            self._swatches[(slot_name, i)] = swatch

        layout.addLayout(grid)
        layout.addStretch()

        reset_button = QPushButton("Reset")
        reset_button.setToolTip("Revert this slot to the default CLUT colors from the ISO.")
        reset_button.setFixedHeight(22)
        reset_button.clicked.connect(self._emit_reset(slot_name))
        layout.addWidget(reset_button)

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

    def _on_row_clicked(self, slot_name: str) -> None:
        # Toggle: clicking the currently-focused row clears focus so the user
        # can get back to the un-highlighted view without hunting for an
        # "unfocus" target.
        if self._focused_slot == slot_name:
            self._set_focus(None)
        else:
            self._set_focus(slot_name)

    def _set_focus(self, slot_name: str | None) -> None:
        if slot_name == self._focused_slot:
            return

        previous = self._focused_slot
        self._focused_slot = slot_name

        if previous is not None:
            previous_row = self._rows.get(previous)
            if previous_row is not None:
                previous_row.set_focused(False)

        if slot_name is not None:
            current_row = self._rows.get(slot_name)
            if current_row is not None:
                current_row.set_focused(True)

        self.slot_focus_changed.emit(slot_name)
