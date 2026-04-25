# coding: utf-8

from PySide6.QtWidgets import QListWidgetItem

from paintjob_designer.gui.widget.library_sidebar import (
    LibraryRowDelegate,
    LibrarySidebar,
)
from paintjob_designer.models import SkinLibrary


class SkinLibrarySidebar(LibrarySidebar):
    """Scrollable list of character-bound skins in the session library."""

    def __init__(self, parent=None) -> None:
        super().__init__(
            new_tooltip="Create a new skin bound to a character.",
            delete_tooltip="Remove the selected skin from the library.",
            export_tooltip="Export the entire skin library to a directory of JSONs.",
            parent=parent,
        )

    def set_library(
        self,
        library: SkinLibrary,
        selected_index: int | None = None,
    ) -> None:
        self._list.blockSignals(True)
        self._list.clear()

        for index, skin in enumerate(library.skins):
            item = QListWidgetItem(self._primary_text_for(skin, index))
            author = (skin.author or "").strip()

            if author:
                item.setData(LibraryRowDelegate.SECONDARY_ROLE, author)

            self._list.addItem(item)

        self._list.blockSignals(False)

        self._apply_selection_after_rebuild(selected_index, library.count())
        self._refresh_button_state()

    def _primary_text_for(self, skin, index: int) -> str:
        name = (skin.name or "").strip()
        character_label = self._character_resolver(skin.character_id or "")

        if name and character_label:
            return f"{name}  —  {character_label}"

        if name:
            return name

        if character_label:
            return f"({character_label})"
        
        return f"Skin {index + 1}"
