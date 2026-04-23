# coding: utf-8

from paintjob_designer.gui.command.undo_command_base import UndoCommandBase
from paintjob_designer.models import Paintjob, Skin, SlotColors, SlotRegions


class ResetSlotCommand(UndoCommandBase):
    """A "reset this slot to the VRAM defaults" edit, reversible."""

    def __init__(
        self,
        main_window,
        asset: Paintjob | Skin,
        slot: SlotRegions,
        old_colors: SlotColors | None,
    ) -> None:
        super().__init__(f"Reset {slot.slot_name}")
        self._window = main_window
        self._asset = asset
        self._slot = slot
        self._old_colors = old_colors

    def _apply_redo(self) -> None:
        self._window.apply_slot_reset_from_command(self._asset, self._slot)

    def undo(self) -> None:
        self._window.apply_slot_restore_from_command(
            self._asset, self._slot, self._old_colors,
        )
