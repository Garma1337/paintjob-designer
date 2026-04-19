# coding: utf-8

from dataclasses import dataclass

from PySide6.QtGui import QUndoCommand

from paintjob_designer.models import PsxColor, SlotRegions


@dataclass
class BulkColorEdit:
    """One (character, slot, color-index) coordinate of a bulk transform.

    Bundled together into `BulkTransformCommand` so a single Ctrl+Z reverses
    a Transform Colors dialog application no matter how many colors changed.
    """

    character_id: str
    slot: SlotRegions
    color_index: int
    old_color: PsxColor
    new_color: PsxColor


class BulkTransformCommand(QUndoCommand):
    """A Transform Colors dialog apply — N single-color edits bundled into one undo.

    Ordering matters: redo walks `edits` front-to-back and applies `new_color`
    to each target; undo walks them back-to-front and applies `old_color`. If
    the transform touched the same slot/index twice (shouldn't happen with the
    current dialog, but cheap to get right) the last-wins semantics still land
    correctly because of the reverse walk on undo.
    """

    def __init__(
        self,
        main_window,
        label: str,
        edits: list[BulkColorEdit],
    ) -> None:
        super().__init__(label)
        self._window = main_window
        self._edits = list(edits)
        self._skip_next_redo = True

    def redo(self) -> None:
        if self._skip_next_redo:
            self._skip_next_redo = False
            return

        self._window.apply_bulk_edits_from_command([
            (e.character_id, e.slot, e.color_index, e.new_color)
            for e in self._edits
        ])

    def undo(self) -> None:
        self._window.apply_bulk_edits_from_command([
            (e.character_id, e.slot, e.color_index, e.old_color)
            for e in reversed(self._edits)
        ])
