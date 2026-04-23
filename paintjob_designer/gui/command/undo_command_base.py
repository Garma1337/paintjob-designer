# coding: utf-8

from PySide6.QtGui import QUndoCommand


class UndoCommandBase(QUndoCommand):
    """Base for paintjob undo commands.

    Handles the shared first-redo-skip: every editor mutation in this app
    is applied immediately (so the artist sees the change) and *then* the
    matching undo command is pushed. QUndoStack.push fires `redo()`
    automatically, which would double-apply — subclasses should override
    `_apply_redo` instead of `redo`, and the first call is swallowed.
    """

    def __init__(self, label: str) -> None:
        super().__init__(label)
        self._skip_next_redo = True

    def redo(self) -> None:
        if self._skip_next_redo:
            self._skip_next_redo = False
            return

        self._apply_redo()

    def _apply_redo(self) -> None:
        raise NotImplementedError
