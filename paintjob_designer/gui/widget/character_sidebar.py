# coding: utf-8

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtWidgets import QListWidget, QListWidgetItem

from paintjob_designer.models import Profile


class CharacterSidebar(QListWidget):
    """Scrollable list of characters for the loaded profile.

    Emits:
        - `character_selected(character_id: str)` on row change.
        - `character_context_requested(character_id: str, global_pos: QPoint)`
          when the user right-clicks a row. The main window uses this to show a
          per-character export context menu (JSON / Code) at the cursor.

    Profiles are set via `set_profile`; the sidebar caches the last emitted id
    so repeated row-change signals don't spam re-loads.
    """

    character_selected = Signal(str)
    character_context_requested = Signal(str, QPoint)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._last_emitted_id: str = ""
        self.currentRowChanged.connect(self._on_row_changed)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu_requested)

    def set_profile(self, profile: Profile) -> None:
        self.blockSignals(True)
        self.clear()

        for character in profile.characters:
            item = QListWidgetItem(character.display_name or character.id)
            item.setData(Qt.ItemDataRole.UserRole, character.id)
            self.addItem(item)

        self.blockSignals(False)

        self._last_emitted_id = ""
        if self.count() > 0:
            self.setCurrentRow(0)

    def _on_row_changed(self, row: int) -> None:
        if row < 0:
            return

        item = self.item(row)
        if item is None:
            return

        character_id = str(item.data(Qt.ItemDataRole.UserRole))
        if character_id == self._last_emitted_id:
            return

        self._last_emitted_id = character_id
        self.character_selected.emit(character_id)

    def _on_context_menu_requested(self, local_pos: QPoint) -> None:
        item = self.itemAt(local_pos)
        if item is None:
            return

        character_id = str(item.data(Qt.ItemDataRole.UserRole))
        self.character_context_requested.emit(
            character_id, self.viewport().mapToGlobal(local_pos),
        )
