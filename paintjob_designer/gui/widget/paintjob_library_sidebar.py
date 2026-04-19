# coding: utf-8

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from paintjob_designer.models import PaintjobLibrary


class PaintjobLibrarySidebar(QWidget):
    """Scrollable list of paintjobs in the session library.

    Each row shows a paintjob's display name. Below the list, "New" and
    "Delete" buttons manage the library; rows can be reordered via
    drag-and-drop (the in-game paintjob index = list position, so order
    matters for PAINTALL.BIN exports).

    Emits:
        - `paintjob_selected(index)` on row change.
        - `paintjob_context_requested(index, global_pos)` on right-click.
        - `new_paintjob_requested()` / `delete_paintjob_requested(index)`
          when the toolbar buttons are clicked.
        - `paintjobs_reordered(from_index, to_index)` after a drag.

    The sidebar is purely a view; the main window owns the library and
    relays model mutations back via `set_library` on each change.
    """

    paintjob_selected = Signal(int)
    paintjob_context_requested = Signal(int, QPoint)
    new_paintjob_requested = Signal()
    delete_paintjob_requested = Signal(int)
    paintjobs_reordered = Signal(int, int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self._last_emitted_index: int = -1
        self._suppress_reorder_signal = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._list = QListWidget()
        self._list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.currentRowChanged.connect(self._on_row_changed)
        self._list.customContextMenuRequested.connect(self._on_context_menu_requested)
        # `model().rowsMoved` fires after Qt finishes a drag-reorder; we use
        # it to translate the view-level move into a library-level move on
        # the main window (which owns the canonical ordering).
        self._list.model().rowsMoved.connect(self._on_rows_moved)
        layout.addWidget(self._list, 1)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        self._new_button = QPushButton("New")
        self._new_button.setToolTip("Create a blank paintjob in the library.")
        self._new_button.clicked.connect(self.new_paintjob_requested)
        button_row.addWidget(self._new_button)

        self._delete_button = QPushButton("Delete")
        self._delete_button.setToolTip(
            "Remove the selected paintjob from the library.",
        )
        self._delete_button.clicked.connect(self._on_delete_clicked)
        button_row.addWidget(self._delete_button)

        button_row.addStretch()
        layout.addLayout(button_row)

        self._refresh_button_state()

    def set_library(
        self,
        library: PaintjobLibrary,
        selected_index: int | None = None,
    ) -> None:
        """Rebuild the list to match `library`.

        `selected_index` controls which row ends up highlighted after the
        refresh — pass `None` to keep no selection, which happens when the
        library is empty or the main window hasn't picked a paintjob yet.
        """
        # Suppress both the selection-changed and rows-moved signals while
        # we rebuild — otherwise clearing the list emits a spurious
        # `currentRowChanged(-1)` and repopulation would look like a drag.
        self._list.blockSignals(True)
        self._suppress_reorder_signal = True
        self._list.clear()

        for i, paintjob in enumerate(library.paintjobs):
            self._list.addItem(QListWidgetItem(self._label_for(paintjob, i)))

        self._list.blockSignals(False)
        self._suppress_reorder_signal = False

        self._last_emitted_index = -1
        if selected_index is not None and 0 <= selected_index < library.count():
            self._list.setCurrentRow(selected_index)

        self._refresh_button_state()

    def set_selected_index(self, index: int | None) -> None:
        """Programmatically move the selection without firing `paintjob_selected`."""
        self._list.blockSignals(True)
        if index is None:
            self._list.setCurrentRow(-1)
            self._last_emitted_index = -1
        else:
            self._list.setCurrentRow(index)
            self._last_emitted_index = index

        self._list.blockSignals(False)
        self._refresh_button_state()

    def _label_for(self, paintjob, index: int) -> str:
        """Row label: prefer the paintjob's name, fall back to a numbered hint.

        When both name and base_character_id are set we show both so the
        artist can tell apart two paintjobs authored for the same character
        (e.g. "Crash classic" vs "Crash alt" both based on `crash`).
        """
        name = paintjob.name.strip()
        base = paintjob.base_character_id

        if name and base:
            return f"{name}  —  {base}"

        if name:
            return name

        if base:
            return f"({base})"

        return f"Paintjob {index + 1}"

    def _on_row_changed(self, row: int) -> None:
        if row == self._last_emitted_index:
            return

        self._last_emitted_index = row
        self._refresh_button_state()

        if row >= 0:
            self.paintjob_selected.emit(row)

    def _on_context_menu_requested(self, local_pos: QPoint) -> None:
        item = self._list.itemAt(local_pos)
        if item is None:
            return

        self.paintjob_context_requested.emit(
            self._list.row(item),
            self._list.viewport().mapToGlobal(local_pos),
        )

    def _on_delete_clicked(self) -> None:
        row = self._list.currentRow()
        if row < 0:
            return

        self.delete_paintjob_requested.emit(row)

    def _on_rows_moved(self, _parent, start: int, end: int, _dst_parent, dest: int) -> None:
        """Translate Qt's view-model row move into a library reorder.

        Qt's `rowsMoved` reports `dest` on the pre-move list state and uses
        the convention that moving a single row from index `start` to a
        landing index `dest` where `dest > start` means "after removal
        from `start`, insert at `dest - 1`". We convert to the
        `PaintjobLibrary.move` semantics (destination interpreted on the
        post-removal list) here so the main window receives a clean
        `(from_index, to_index)` pair.
        """
        if self._suppress_reorder_signal or start != end:
            return

        from_index = start
        to_index = dest if dest < start else dest - 1
        self.paintjobs_reordered.emit(from_index, to_index)

    def _refresh_button_state(self) -> None:
        has_selection = self._list.currentRow() >= 0
        self._delete_button.setEnabled(has_selection)
