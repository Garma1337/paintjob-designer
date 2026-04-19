# coding: utf-8

from PySide6.QtGui import QUndoCommand

from paintjob_designer.models import PsxColor, SlotRegions


class SetSlotColorCommand(QUndoCommand):
    """A single color-picker edit, captured so it can be undone/redone.

    The command holds the before/after PSX color plus enough state to re-apply
    either direction: it calls back into the owning main window which owns the
    atlas buffer and widget refreshes.
    """

    def __init__(
        self,
        main_window,
        character_id: str,
        slot: SlotRegions,
        color_index: int,
        old_color: PsxColor,
        new_color: PsxColor,
    ) -> None:
        super().__init__(f"Set {slot.slot_name}[{color_index}] color")
        self._window = main_window
        self._character_id = character_id
        self._slot = slot
        self._color_index = color_index
        self._old_color = old_color
        self._new_color = new_color
        self._skip_next_redo = True  # first redo happens implicitly when pushed

    def redo(self) -> None:
        if self._skip_next_redo:
            self._skip_next_redo = False
            return

        self._window.apply_color_edit_from_command(
            self._character_id, self._slot, self._color_index, self._new_color,
        )

    def undo(self) -> None:
        self._window.apply_color_edit_from_command(
            self._character_id, self._slot, self._color_index, self._old_color,
        )
