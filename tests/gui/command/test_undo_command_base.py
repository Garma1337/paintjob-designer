# coding: utf-8

import pytest

pytest.importorskip("PySide6.QtGui")

from paintjob_designer.gui.command.undo_command_base import UndoCommandBase


class _Counter(UndoCommandBase):
    def __init__(self) -> None:
        super().__init__("counter")
        self.redo_calls = 0
        self.undo_calls = 0

    def _apply_redo(self) -> None:
        self.redo_calls += 1

    def undo(self) -> None:
        self.undo_calls += 1


def test_first_redo_is_skipped():
    cmd = _Counter()
    cmd.redo()
    assert cmd.redo_calls == 0


def test_second_redo_calls_apply():
    cmd = _Counter()
    cmd.redo()
    cmd.redo()
    assert cmd.redo_calls == 1


def test_subsequent_redos_keep_calling():
    cmd = _Counter()
    cmd.redo()
    cmd.redo()
    cmd.redo()
    cmd.redo()
    assert cmd.redo_calls == 3


def test_undo_does_not_skip():
    cmd = _Counter()
    cmd.undo()
    assert cmd.undo_calls == 1


def test_label_passes_through():
    cmd = _Counter()
    assert cmd.text() == "counter"
