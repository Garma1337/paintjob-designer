# coding: utf-8

import pytest

# Commands extend `QUndoCommand`; skip this module when Qt isn't available
# (system Python running the headless suite). The command logic is still
# exercised via integration when running under the venv.
pytest.importorskip("PySide6")

from paintjob_designer.gui.command.set_slot_color_command import SetSlotColorCommand
from paintjob_designer.models import Paintjob, PsxColor, SlotRegions


class _RecordingWindow:
    """Minimal stand-in for `MainWindow` that records delegated calls.

    The commands only ever call `apply_color_edit_from_command` /
    `apply_slot_reset_from_command` / `apply_slot_restore_from_command` on
    the window, so a tiny recorder is enough to assert each redo/undo
    delegates with the expected arguments without needing a real
    `QApplication`.
    """

    def __init__(self) -> None:
        self.color_edits: list[tuple] = []
        self.slot_resets: list[tuple] = []
        self.slot_restores: list[tuple] = []

    def apply_color_edit_from_command(self, paintjob, slot, color_index, new_color):
        self.color_edits.append((paintjob, slot, color_index, new_color))

    def apply_slot_reset_from_command(self, paintjob, slot):
        self.slot_resets.append((paintjob, slot))

    def apply_slot_restore_from_command(self, paintjob, slot, old_colors):
        self.slot_restores.append((paintjob, slot, old_colors))


def _build(paintjob=None, slot=None, color_index=3, old=0x1111, new=0x2222):
    window = _RecordingWindow()
    paintjob = paintjob if paintjob is not None else Paintjob()
    slot = slot if slot is not None else SlotRegions(slot_name="front")
    cmd = SetSlotColorCommand(
        window, paintjob, slot, color_index,
        PsxColor(value=old), PsxColor(value=new),
    )
    return window, cmd, paintjob, slot


class TestInitialRedoIsNoOp:

    def test_first_redo_skipped(self):
        # When the command is pushed onto a QUndoStack, `redo()` fires
        # automatically. The edit has ALREADY been applied by the caller
        # (so the user can see the change immediately), so the first
        # redo must not double-apply.
        window, cmd, _, _ = _build()

        cmd.redo()

        assert window.color_edits == []

    def test_second_redo_applies_new_color(self):
        window, cmd, paintjob, slot = _build(new=0x7FFF)

        cmd.redo()   # no-op first
        cmd.redo()   # actual redo

        assert len(window.color_edits) == 1
        pj, s, idx, color = window.color_edits[0]
        assert pj is paintjob
        assert s is slot
        assert idx == 3
        assert color.value == 0x7FFF


class TestUndo:

    def test_undo_applies_old_color(self):
        window, cmd, paintjob, slot = _build(old=0x0123)

        cmd.undo()

        assert len(window.color_edits) == 1
        pj, s, idx, color = window.color_edits[0]
        assert pj is paintjob
        assert s is slot
        assert color.value == 0x0123

    def test_redo_undo_round_trip(self):
        window, cmd, _, _ = _build(old=0x1111, new=0x2222)

        cmd.redo()   # no-op first
        cmd.redo()   # apply new
        cmd.undo()   # revert to old
        cmd.redo()   # re-apply new

        assert [c[3].value for c in window.color_edits] == [0x2222, 0x1111, 0x2222]


class TestLabel:

    def test_label_embeds_slot_and_index(self):
        # QUndoStack shows the label in its undo/redo menu entries; a
        # meaningful label helps the artist see what's about to revert.
        slot = SlotRegions(slot_name="motorside")
        _, cmd, _, _ = _build(slot=slot, color_index=7)

        assert "motorside" in cmd.text()
        assert "7" in cmd.text()


class TestStoresReferences:

    def test_command_holds_paintjob_ref_not_copy(self):
        paintjob = Paintjob(name="original")
        _, cmd, _, _ = _build(paintjob=paintjob)

        # Mutating the paintjob outside the command: the command's ref
        # should follow, since pass-2 relies on paintjob-object identity
        # across library mutations.
        paintjob.name = "renamed"

        # Read back via undo — the paintjob arg should be the SAME object.
        window = cmd._window
        cmd.undo()
        applied_paintjob = window.color_edits[0][0]
        assert applied_paintjob is paintjob
        assert applied_paintjob.name == "renamed"
