# coding: utf-8

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QListWidget, QListWidgetItem

from paintjob_designer.gui.widget.library_sidebar import (
    LibraryRowDelegate,
    LibrarySidebar,
)
from paintjob_designer.models import PaintjobLibrary


class PaintjobLibrarySidebar(LibrarySidebar):
    """Scrollable list of paintjobs in the session library."""

    paintjobs_reordered = Signal(int, int)

    def __init__(self, parent=None) -> None:
        super().__init__(
            new_tooltip="Create a blank paintjob in the library.",
            delete_tooltip="Remove the selected paintjob from the library.",
            export_tooltip="Export the entire paintjob library to a directory of JSONs.",
            parent=parent,
        )

        self._suppress_reorder_signal = False
        self._list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        # `model().rowsMoved` fires after Qt finishes a drag-reorder; we
        # translate the view-level move into a library-level move on the
        # controller (which owns the canonical ordering).
        self._list.model().rowsMoved.connect(self._on_rows_moved)

    def set_library(
        self,
        library: PaintjobLibrary,
        selected_index: int | None = None,
    ) -> None:
        """Rebuild the list to match `library`."""
        # Suppress selection + reorder signals during the rebuild — clearing
        # the list emits a spurious `currentRowChanged(-1)` and repopulation
        # would otherwise look like a drag.
        self._list.blockSignals(True)
        self._suppress_reorder_signal = True
        self._list.clear()

        for i, paintjob in enumerate(library.paintjobs):
            item = QListWidgetItem(self._primary_text_for(paintjob, i))
            author = paintjob.author.strip()

            if author:
                item.setData(LibraryRowDelegate.SECONDARY_ROLE, author)

            self._list.addItem(item)

        self._list.blockSignals(False)
        self._suppress_reorder_signal = False

        self._apply_selection_after_rebuild(selected_index, library.count())
        self._refresh_button_state()

    def _primary_text_for(self, paintjob, index: int) -> str:
        name = paintjob.name.strip()
        character_label = self._character_resolver(paintjob.base_character_id or "")
        marker = " (textured)" if paintjob.has_any_pixels() else ""

        if name and character_label:
            return f"{name}  —  {character_label}{marker}"

        if name:
            return f"{name}{marker}"

        if character_label:
            return f"({character_label}){marker}"

        return f"Paintjob {index + 1}{marker}"

    def _on_rows_moved(self, _parent, start: int, end: int, _dst_parent, dest: int) -> None:
        if self._suppress_reorder_signal or start != end:
            return

        from_index = start
        to_index = dest if dest < start else dest - 1
        self.paintjobs_reordered.emit(from_index, to_index)
