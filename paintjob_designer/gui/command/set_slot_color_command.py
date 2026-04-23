# coding: utf-8

from paintjob_designer.gui.command.undo_command_base import UndoCommandBase
from paintjob_designer.models import Paintjob, PsxColor, Skin, SlotRegions


class SetSlotColorCommand(UndoCommandBase):
    """A single color-picker edit, captured so it can be undone/redone."""

    def __init__(
        self,
        main_window,
        asset: Paintjob | Skin,
        slot: SlotRegions,
        color_index: int,
        old_color: PsxColor,
        new_color: PsxColor,
    ) -> None:
        super().__init__(f"Set {slot.slot_name}[{color_index}] color")
        self._window = main_window
        self._asset = asset
        self._slot = slot
        self._color_index = color_index
        self._old_color = old_color
        self._new_color = new_color

    def _apply_redo(self) -> None:
        self._window.apply_color_edit_from_command(
            self._asset, self._slot, self._color_index, self._new_color,
        )

    def undo(self) -> None:
        self._window.apply_color_edit_from_command(
            self._asset, self._slot, self._color_index, self._old_color,
        )
