# coding: utf-8

import pytest

pytest.importorskip("PySide6.QtGui")

from paintjob_designer.gui.command.bulk_transform_command import (
    BulkColorEdit,
    BulkTransformCommand,
)
from paintjob_designer.models import Paintjob, PsxColor, SlotRegions


class _RecordingWindow:
    """Stand-in that records every bulk-apply invocation."""

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
        window = _RecordingWindow()
        edits = [_edit(Paintjob(), "front", 0, 0x0000, 0x1111)]
        cmd = BulkTransformCommand(window, "Transform", edits)

        cmd.redo()

        assert window.bulk_calls == []

    def test_second_redo_applies_new_colors_in_order(self):
        window = _RecordingWindow()
        paintjob = Paintjob()
        edits = [
            _edit(paintjob, "front", 0, 0x0000, 0x1111),
            _edit(paintjob, "back",  3, 0x0000, 0x2222),
        ]
        cmd = BulkTransformCommand(window, "Transform", edits)

        cmd.redo()   # no-op first
        cmd.redo()

        assert len(window.bulk_calls) == 1
        ops = window.bulk_calls[0]
        assert len(ops) == 2

        # Forward order on redo: first edit first.
        pj0, slot0, idx0, color0 = ops[0]
        pj1, slot1, idx1, color1 = ops[1]
        assert pj0 is paintjob and pj1 is paintjob
        assert slot0.slot_name == "front"
        assert slot1.slot_name == "back"
        assert color0.value == 0x1111
        assert color1.value == 0x2222


class TestUndoAppliesOldColorsInReverseOrder:

    def test_reverse_walk(self):
        # Reverse order matters when two edits touch the same (slot, index)
        # — last-wins semantics must hold when unwinding too.
        window = _RecordingWindow()
        paintjob = Paintjob()
        edits = [
            _edit(paintjob, "front", 0, 0x0000, 0x1111),
            _edit(paintjob, "back",  3, 0x0000, 0x2222),
        ]
        cmd = BulkTransformCommand(window, "Transform", edits)

        cmd.undo()

        ops = window.bulk_calls[0]
        # Second edit ("back") reverted first, first edit ("front") second.
        assert ops[0][1].slot_name == "back"
        assert ops[0][3].value == 0x0000
        assert ops[1][1].slot_name == "front"
        assert ops[1][3].value == 0x0000


class TestDefensiveCopy:

    def test_mutating_caller_list_doesnt_affect_command(self):
        # The command stores `list(edits)` so a caller can mutate its own
        # list without spooky action at a distance on an already-pushed
        # command.
        window = _RecordingWindow()
        paintjob = Paintjob()
        edits = [_edit(paintjob, "front", 0, 0x0000, 0x1111)]
        cmd = BulkTransformCommand(window, "Transform", edits)

        edits.append(_edit(paintjob, "back", 0, 0x0000, 0x2222))
        cmd.redo()   # no-op first
        cmd.redo()

        # Only the one original edit should have landed.
        ops = window.bulk_calls[0]
        assert len(ops) == 1
        assert ops[0][1].slot_name == "front"


class TestLabel:

    def test_label_is_user_supplied(self):
        cmd = BulkTransformCommand(_RecordingWindow(), "Shift hue +45", [])

        assert cmd.text() == "Shift hue +45"


class TestEmptyEdits:

    def test_redo_and_undo_are_safe_on_empty_list(self):
        window = _RecordingWindow()
        cmd = BulkTransformCommand(window, "Empty", [])

        cmd.redo()   # first-redo skip
        cmd.redo()   # genuine redo, but nothing to apply
        cmd.undo()

        assert window.bulk_calls == [[], []]
