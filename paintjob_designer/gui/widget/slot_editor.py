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


class SlotEditor(QWidget):
    """Grid of slots × 16 color swatches for the current character."""

    color_edit_requested = Signal(str, int)
    slot_reset_requested = Signal(str)
    slot_focus_changed = Signal(object)
    transform_requested = Signal()
    reset_all_requested = Signal()
    # Right-click context. Payload: (slot_name, color_index | -1, global_pos).
    # `color_index == -1` means the right-click landed on row chrome, not a swatch.
    context_requested = Signal(str, int, object)

    def __init__(self, color_converter: ColorConverter, parent=None) -> None:
        super().__init__(parent)
        self._converter = color_converter

        self._rows: dict[str, SlotRow] = {}
        self._swatches: dict[tuple[str, int], ColorSwatch] = {}
        self._highlight_buttons: dict[str, QPushButton] = {}
        self._focused_slot: str | None = None
        self._strip_enabled = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(4)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(8, 6, 8, 0)
        self._transform_button = QPushButton("Transform...")
        self._transform_button.setToolTip(
            "Open the Transform Colors panel to bulk-rewrite slot colors "
            "via hue / saturation / brightness / RGB pipelines.",
        )
        self._transform_button.clicked.connect(self.transform_requested)
        button_row.addWidget(self._transform_button)

        self._reset_all_button = QPushButton("Reset all")
        self._reset_all_button.setToolTip(
            "Revert every slot in the active asset to the default CLUT "
            "colors from the ISO.",
        )
        self._reset_all_button.clicked.connect(self.reset_all_requested)
        button_row.addWidget(self._reset_all_button)
        button_row.addStretch()
        outer.addLayout(button_row)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        self._root = QWidget()
        self._root_layout = QVBoxLayout(self._root)
        self._root_layout.setContentsMargins(8, 8, 8, 8)
        self._root_layout.setSpacing(6)
        self._root_layout.addStretch()
        self._scroll.setWidget(self._root)
        outer.addWidget(self._scroll, 1)

        self._sync_top_buttons()

    def set_slots(
        self,
        slot_names: list[str],
        *,
        dimensions: dict[str, str] | None = None,
    ) -> None:
        self._clear()

        dimensions = dimensions or {}
        for slot_name in slot_names:
            row = self._build_slot_row(slot_name, dimensions.get(slot_name))
            self._rows[slot_name] = row
            self._root_layout.insertWidget(self._root_layout.count() - 1, row)

        self._set_focus(None)
        self._sync_top_buttons()

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
        return self._focused_slot

    def set_button_strip_enabled(self, enabled: bool) -> None:
        self._strip_enabled = enabled
        self._sync_top_buttons()

    def _clear(self) -> None:
        for row in self._rows.values():
            self._root_layout.removeWidget(row)
            row.deleteLater()

        self._rows.clear()
        self._swatches.clear()
        self._highlight_buttons.clear()

    def _sync_top_buttons(self) -> None:
        active = self._strip_enabled and bool(self._rows)
        self._transform_button.setEnabled(active)
        self._reset_all_button.setEnabled(active)

    def _build_slot_row(
        self, slot_name: str, dimension_hint: str | None = None,
    ) -> SlotRow:
        row = SlotRow()
        row.setFrameShape(QFrame.Shape.StyledPanel)
        row.right_clicked.connect(
            lambda name=slot_name: self.context_requested.emit(name, -1, QCursor.pos()),
        )

        # Buttons live under (not beside) the swatches so the grid keeps
        # full row width when the window narrows.
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
                # PSX convention: CLUT index 0 is the per-pixel transparency sentinel.
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

        # Explicit toggle so opening a color picker doesn't accidentally dim
        # the kart. At most one slot is highlighted at a time.
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
        # Captured-by-value closure so each swatch emits its own (slot, index).
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
