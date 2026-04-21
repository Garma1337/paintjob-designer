# coding: utf-8

import pytest

pytest.importorskip("PySide6.QtGui")

from paintjob_designer.gui.command.apply_palette_command import ApplyPaletteCommand
from paintjob_designer.gui.command.bulk_transform_command import BulkColorEdit
from paintjob_designer.models import Paintjob, PsxColor, SlotRegions


class _RecordingWindow:
    """Stand-in main window that records every bulk-apply invocation."""

    def __init__(self) -> None:
        self.bulk_calls: list[list] = []

    def apply_bulk_edits_from_command(self, operations):
        # Copy so the recorder doesn't share state with the command's lists.
        self.bulk_calls.append(list(operations))


def _edit(paintjob, slot_name: str, color_index: int, old: int, new: int) -> BulkColorEdit:
    return BulkColorEdit(
        paintjob=paintjob,
        slot=SlotRegions(slot_name=slot_name),
        color_index=color_index,
        old_color=PsxColor(value=old),
        new_color=PsxColor(value=new),
    )


class TestInitialRedoIsNoOp:

    def test_first_redo_does_not_invoke_window(self):
        # QUndoStack auto-fires `redo()` when a command is pushed; the first
        # redo needs to skip because the caller already applied the edits
        # up-front so the artist sees the change immediately. Matches the
        # BulkTransformCommand contract.
        window = _RecordingWindow()
        edits = [_edit(Paintjob(), "front", 0, 0x0000, 0x1111)]
        cmd = ApplyPaletteCommand(window, "Apply palette", edits)

        cmd.redo()

        assert window.bulk_calls == []

    def test_second_redo_applies_new_colors_in_palette_order(self):
        # Palette entry order defines slot-index mapping (entry 0 → slot[0],
        # entry 1 → slot[1], ...), so redo must walk the edits front-to-back
        # in the list the caller supplied.
        window = _RecordingWindow()
        paintjob = Paintjob()
        edits = [
            _edit(paintjob, "front", 0, 0x0000, 0x1111),
            _edit(paintjob, "front", 1, 0x0000, 0x2222),
            _edit(paintjob, "front", 2, 0x0000, 0x3333),
        ]
        cmd = ApplyPaletteCommand(window, "Apply palette", edits)

        cmd.redo()   # no-op first
        cmd.redo()

        assert len(window.bulk_calls) == 1
        ops = window.bulk_calls[0]
        assert [op[2] for op in ops] == [0, 1, 2]
        assert [op[3].value for op in ops] == [0x1111, 0x2222, 0x3333]


class TestUndoRestoresOldColorsInReverseOrder:

    def test_reverse_walk(self):
        # Reverse order on undo mirrors the same invariant as BulkTransform:
        # if two palette entries somehow landed on the same (slot, index)
        # the last-wins semantic has to hold both ways.
        window = _RecordingWindow()
        paintjob = Paintjob()
        edits = [
            _edit(paintjob, "front", 0, 0x0A0A, 0x1111),
            _edit(paintjob, "front", 1, 0x0B0B, 0x2222),
        ]
        cmd = ApplyPaletteCommand(window, "Apply palette", edits)

        cmd.undo()

        ops = window.bulk_calls[0]
        assert [op[2] for op in ops] == [1, 0]
        assert [op[3].value for op in ops] == [0x0B0B, 0x0A0A]


class TestDefensiveCopy:

    def test_mutating_caller_list_doesnt_affect_command(self):
        window = _RecordingWindow()
        paintjob = Paintjob()
        edits = [_edit(paintjob, "front", 0, 0x0000, 0x1111)]
        cmd = ApplyPaletteCommand(window, "Apply palette", edits)

        edits.append(_edit(paintjob, "front", 1, 0x0000, 0x2222))
        cmd.redo()   # no-op first
        cmd.redo()

        ops = window.bulk_calls[0]
        assert len(ops) == 1
        assert ops[0][2] == 0


class TestLabel:

    def test_label_is_user_supplied(self):
        cmd = ApplyPaletteCommand(_RecordingWindow(), "Apply 'Sunset' to front", [])

        assert cmd.text() == "Apply 'Sunset' to front"


class TestEmptyEdits:

    def test_redo_and_undo_are_safe_on_empty_list(self):
        # An apply that matches the existing colors exactly produces zero
        # edits — the main window should still be free to push a command
        # (or skip, but if it pushes the command it can't crash).
        window = _RecordingWindow()
        cmd = ApplyPaletteCommand(window, "Empty", [])

        cmd.redo()   # first-redo skip
        cmd.redo()   # genuine redo, nothing to apply
        cmd.undo()

        assert window.bulk_calls == [[], []]
