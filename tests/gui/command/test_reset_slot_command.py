# coding: utf-8

import pytest

pytest.importorskip("PySide6")

from paintjob_designer.gui.command.reset_slot_command import ResetSlotCommand
from paintjob_designer.models import Paintjob, PsxColor, SlotColors, SlotRegions


class _RecordingWindow:
    """Stand-in for `MainWindow` that records delegated calls."""

    def __init__(self) -> None:
        self.resets: list[tuple] = []
        self.restores: list[tuple] = []

    def apply_slot_reset_from_command(self, paintjob, slot):
        self.resets.append((paintjob, slot))

    def apply_slot_restore_from_command(self, paintjob, slot, old_colors):
        self.restores.append((paintjob, slot, old_colors))


def _snapshot(value: int = 0xABCD) -> SlotColors:
    return SlotColors(colors=[PsxColor(value=value) for _ in range(16)])


def _build(paintjob=None, slot=None, old_colors=None):
    window = _RecordingWindow()
    paintjob = paintjob if paintjob is not None else Paintjob()
    slot = slot if slot is not None else SlotRegions(slot_name="front")
    cmd = ResetSlotCommand(window, paintjob, slot, old_colors)
    return window, cmd, paintjob, slot


class TestInitialRedoIsNoOp:

    def test_first_redo_does_not_reset(self):
        window, cmd, _, _ = _build()

        cmd.redo()

        assert window.resets == []

    def test_second_redo_delegates_to_reset(self):
        window, cmd, paintjob, slot = _build()

        cmd.redo()   # no-op first
        cmd.redo()

        assert window.resets == [(paintjob, slot)]


class TestUndo:

    def test_undo_restores_captured_snapshot(self):
        snapshot = _snapshot(value=0x7FFF)
        window, cmd, paintjob, slot = _build(old_colors=snapshot)

        cmd.undo()

        assert len(window.restores) == 1
        pj, s, old = window.restores[0]
        assert pj is paintjob
        assert s is slot
        assert old is snapshot

    def test_undo_with_none_snapshot_passes_none(self):
        # `None` means "the slot was never populated" — restore should
        # delete the paintjob entry, not write default colors.
        window, cmd, _, _ = _build(old_colors=None)

        cmd.undo()

        assert window.restores[0][2] is None


class TestLabel:

    def test_label_embeds_slot_name(self):
        slot = SlotRegions(slot_name="motorside")
        _, cmd, _, _ = _build(slot=slot)

        assert "motorside" in cmd.text()
