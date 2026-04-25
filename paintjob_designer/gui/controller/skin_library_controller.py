# coding: utf-8

from pathlib import Path

from PySide6.QtCore import QPoint, Signal
from PySide6.QtWidgets import QMenu, QWidget

from paintjob_designer.core import Slugifier
from paintjob_designer.gui.controller.character_picker import CharacterPicker
from paintjob_designer.gui.controller.library_controller import LibraryController
from paintjob_designer.gui.handler.color_handler import ColorHandler
from paintjob_designer.gui.util.dialogs import (
    FilePicker,
    InputPrompt,
    MessageDialog,
)
from paintjob_designer.gui.util.library_writer import LibraryWriter
from paintjob_designer.gui.widget.skin_library_sidebar import SkinLibrarySidebar
from paintjob_designer.models import (
    CharacterProfile,
    Skin,
    SkinLibrary,
    SlotColors,
)
from paintjob_designer.skin.reader import SkinReader
from paintjob_designer.skin.writer import SkinWriter

_SKIN_EXT = ".json"
_SKIN_FILTER = f"Skin (*{_SKIN_EXT})"


class SkinLibraryController(LibraryController[Skin, SkinLibrary]):
    """Owns the skin library + sidebar + skin CRUD."""

    transform_requested = Signal(int)

    def __init__(
        self,
        sidebar: SkinLibrarySidebar,
        skin_reader: SkinReader,
        skin_writer: SkinWriter,
        library_writer: LibraryWriter,
        message: MessageDialog,
        files: FilePicker,
        prompt: InputPrompt,
        slugifier: Slugifier,
        character_picker: CharacterPicker,
        color_handler: ColorHandler,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(message, parent)
        self._sidebar = sidebar
        self._skin_reader = skin_reader
        self._skin_writer = skin_writer
        self._library_writer = library_writer
        self._files = files
        self._prompt = prompt
        self._slugifier = slugifier
        self._character_picker = character_picker
        self._color_handler = color_handler
        self._iso_root: str = ""

        self._sidebar.item_selected.connect(self._on_sidebar_selected)
        self._sidebar.context_requested.connect(self._on_context_menu)
        self._sidebar.new_requested.connect(self.new)
        self._sidebar.delete_requested.connect(self.delete)
        self._sidebar.export_requested.connect(self.export_library)
        self._sidebar.transform_requested.connect(self.transform_requested.emit)

    def set_iso_root(self, iso_root: str) -> None:
        self._iso_root = iso_root

    def _make_empty_library(self) -> SkinLibrary:
        return SkinLibrary()

    def _items(self) -> list[Skin]:
        return self._library.skins

    def _item_label(self, item: Skin, index: int) -> str:
        return item.name.strip() or f"Skin {index + 1}"

    def _item_kind(self) -> str:
        return "skin"

    def _refresh_sidebar(self, selected_index: int | None) -> None:
        self._sidebar.set_library(self._library, selected_index=selected_index)

    def _remove_at(self, index: int) -> Skin:
        return self._library.remove(index)

    def _set_sidebar_selection(self, index: int) -> None:
        self._sidebar.set_selected_index(index)

    def new(self) -> None:
        character = self._character_picker.pick(
            "New skin — pick character to skin", parent=self._parent_widget,
        )

        if character is None:
            return

        skin = Skin(
            name=f"{character.display_name or character.id} skin "
                 f"{self._library.count() + 1}",
            character_id=character.id,
            slots=self._seed_slots(character),
        )

        index = self._library.add(skin)
        self._refresh_sidebar(index)
        self._after_mutation()

    def rename(self, index: int) -> None:
        if not (0 <= index < self._library.count()):
            return

        skin = self._library.skins[index]
        new_name = self._prompt.get_text(
            self._parent_widget, "Rename skin", "Name:", skin.name,
        )

        if new_name is None:
            return

        skin.name = new_name.strip()
        self._refresh_sidebar(index)
        self._after_mutation()

    def set_author(self, index: int) -> None:
        if not (0 <= index < self._library.count()):
            return

        skin = self._library.skins[index]
        new_author = self._prompt.get_text(
            self._parent_widget, "Set skin author",
            "Author:", skin.author,
        )

        if new_author is None:
            return

        skin.author = new_author.strip()
        self._refresh_sidebar(index)
        self._after_mutation()

    def import_files(self, default_dir: str | None = None) -> None:
        for path in self._files.pick_open_paths(
            self._parent_widget, "Import skins",
            default_dir, f"{_SKIN_FILTER};;All files (*)",
        ):
            self.import_file(path)

    def import_file(self, path: Path) -> None:
        try:
            loaded = self._skin_reader.read(path.read_bytes())
        except (OSError, ValueError) as exc:
            self._message.error(self._parent_widget, "Import failed", str(exc))
            return

        index = self._library.add(loaded)
        # Imports invalidate undo (commands captured pre-import refs).
        self.library_reset.emit()
        self._refresh_sidebar(index)
        self._after_mutation()

    def replace_from_file(self, index: int) -> None:
        if not (0 <= index < self._library.count()):
            return

        path = self._files.pick_open_path(
            self._parent_widget, "Replace skin from JSON",
            None, f"{_SKIN_FILTER};;All files (*)",
        )

        if path is None:
            return

        try:
            loaded = self._skin_reader.read(path.read_bytes())
        except (OSError, ValueError) as exc:
            self._message.error(self._parent_widget, "Import failed", str(exc))
            return

        self._library.skins[index] = loaded
        self.library_reset.emit()
        self._refresh_sidebar(index)
        self._after_mutation()

    def export_one(self, skin: Skin) -> None:
        try:
            index = self._library.skins.index(skin)
        except ValueError:
            return

        default_name = self._slug_filename(skin, index) + _SKIN_EXT
        path = self._files.pick_save_path(
            self._parent_widget, "Export skin as JSON",
            default_name, _SKIN_FILTER,
        )

        if path is None:
            return

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(self._skin_writer.serialize(skin), encoding="utf-8")
        except OSError as exc:
            self._message.error(self._parent_widget, "Export failed", str(exc))

    def export_library(self) -> None:
        if self._library.count() == 0:
            self._message.info(
                self._parent_widget, "Nothing to save",
                "The skin library is empty — create at least one skin "
                "before saving.",
            )

            return

        directory = self._files.pick_directory(
            self._parent_widget, "Save skin library",
        )

        if directory is None:
            return

        try:
            self._library_writer.write(
                directory, self._library.skins,
                filename_for=self._library_filename,
                serialize=self._skin_writer.serialize,
            )
        except OSError as exc:
            self._message.error(
                self._parent_widget, "Save skin library failed", str(exc),
            )

    def _on_context_menu(self, index: int, global_pos: QPoint) -> None:
        if not (0 <= index < self._library.count()):
            return

        skin = self._library.skins[index]
        menu = QMenu(self._parent_widget)
        menu.addAction("Rename...", lambda: self.rename(index))
        menu.addAction("Set author...", lambda: self.set_author(index))
        menu.addSeparator()
        menu.addAction("Export as JSON...", lambda: self.export_one(skin))
        menu.addAction("Replace from JSON...", lambda: self.replace_from_file(index))
        menu.addSeparator()
        menu.addAction("Delete", lambda: self.delete(index))
        menu.exec(global_pos)

    def _seed_slots(self, character: CharacterProfile) -> dict[str, SlotColors]:
        slots: dict[str, SlotColors] = {}

        for slot_profile in character.skin_slots:
            defaults = self._color_handler.default_slot_colors_at(
                self._iso_root, slot_profile.clut.x, slot_profile.clut.y,
            )
            slots[slot_profile.name] = SlotColors(colors=list(defaults))

        return slots

    def _library_filename(self, skin: Skin, index: int) -> str:
        slug = (
            self._slugifier.slugify(skin.name)
            or skin.character_id or f"skin_{index:02d}"
        )

        return f"{index:02d}_{slug}{_SKIN_EXT}"

    def _slug_filename(self, skin: Skin, index: int) -> str:
        return (
            self._slugifier.slugify(skin.name)
            or skin.character_id
            or f"skin_{index:02d}"
        )
