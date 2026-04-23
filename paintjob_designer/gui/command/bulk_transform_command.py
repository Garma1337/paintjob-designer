# coding: utf-8

from dataclasses import dataclass

from paintjob_designer.gui.command.undo_command_base import UndoCommandBase
from paintjob_designer.models import Paintjob, PsxColor, Skin, SlotRegions


@dataclass
class BulkColorEdit:
    """One (asset, slot, color-index) coordinate of a bulk edit.

    `asset` is the Paintjob OR Skin that owns the slot — both have the
    same `.slots[name] -> SlotColors` shape, so the apply path duck-types
    on it.
    """

    asset: Paintjob | Skin
    slot: SlotRegions
    color_index: int
    old_color: PsxColor
    new_color: PsxColor


class BulkTransformCommand(UndoCommandBase):
    """N single-color edits collapsed into one undoable batch.

    Used by the Transform Colors panel and the apply-palette / gradient-
    fill flows — every path that needs many `(slot, index, color)` writes
    to undo as one step.
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

    def _apply_redo(self) -> None:
        self._window.apply_bulk_edits_from_command([
            (e.asset, e.slot, e.color_index, e.new_color)
            for e in self._edits
        ])

    def undo(self) -> None:
        self._window.apply_bulk_edits_from_command([
            (e.asset, e.slot, e.color_index, e.old_color)
            for e in reversed(self._edits)
        ])
