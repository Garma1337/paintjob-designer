# coding: utf-8

from PySide6.QtGui import QUndoCommand

from paintjob_designer.models import Paintjob, PsxColor, SlotRegions


class SetSlotColorCommand(QUndoCommand):
    """A single color-picker edit, captured so it can be undone/redone.

    Holds a reference to the `Paintjob` it mutates — the library-first UX
    has paintjobs as stable objects, so a direct reference survives sidebar
    selection changes and reordering without needing an identifier lookup
    at redo/undo time.
    """

    def __init__(
        self,
        main_window,
        paintjob: Paintjob,
        slot: SlotRegions,
        color_index: int,
        old_color: PsxColor,
        new_color: PsxColor,
    ) -> None:
        super().__init__(f"Set {slot.slot_name}[{color_index}] color")
        self._window = main_window
        self._paintjob = paintjob
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
            self._paintjob, self._slot, self._color_index, self._new_color,
        )

    def undo(self) -> None:
        self._window.apply_color_edit_from_command(
            self._paintjob, self._slot, self._color_index, self._old_color,
        )
