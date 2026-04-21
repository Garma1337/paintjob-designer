# coding: utf-8

from PySide6.QtGui import QUndoCommand

from paintjob_designer.gui.command.bulk_transform_command import BulkColorEdit


class ApplyPaletteCommand(QUndoCommand):
    """Apply a saved palette to a slot as one undoable batch.

    Wraps the same `BulkColorEdit` list the Transform Colors pipeline uses,
    so redo/undo both funnel through `main_window.apply_bulk_edits_from_command`
    and share the grouped-per-slot atlas render that keeps the 3D preview in
    sync. The palette's entry order encodes the slot-index mapping (entry 0 →
    slot[0], entry 1 → slot[1], ...); the caller builds the `edits` list with
    that mapping already baked in.
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
            (e.paintjob, e.slot, e.color_index, e.new_color)
            for e in self._edits
        ])

    def undo(self) -> None:
        self._window.apply_bulk_edits_from_command([
            (e.paintjob, e.slot, e.color_index, e.old_color)
            for e in reversed(self._edits)
        ])
