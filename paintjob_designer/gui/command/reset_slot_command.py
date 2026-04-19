# coding: utf-8

from PySide6.QtGui import QUndoCommand

from paintjob_designer.models import Paintjob, SlotColors, SlotRegions


class ResetSlotCommand(QUndoCommand):
    """A "reset this slot to the VRAM defaults" edit, reversible.

    Captures every existing color in the slot (or `None` if the slot
    hadn't been populated yet) so undo puts it back exactly how it was.
    """

    def __init__(
        self,
        main_window,
        paintjob: Paintjob,
        slot: SlotRegions,
        old_colors: SlotColors | None,
    ) -> None:
        super().__init__(f"Reset {slot.slot_name}")
        self._window = main_window
        self._paintjob = paintjob
        self._slot = slot
        self._old_colors = old_colors
        self._skip_next_redo = True

    def redo(self) -> None:
        if self._skip_next_redo:
            self._skip_next_redo = False
            return

        self._window.apply_slot_reset_from_command(self._paintjob, self._slot)

    def undo(self) -> None:
        self._window.apply_slot_restore_from_command(
            self._paintjob, self._slot, self._old_colors,
        )
