# coding: utf-8

from pathlib import Path

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QMenu, QWidget

from paintjob_designer.core import Slugifier
from paintjob_designer.gui.controller.character_picker import CharacterPicker
from paintjob_designer.gui.controller.library_controller import LibraryController
from paintjob_designer.gui.handler.color_handler import ColorHandler
from paintjob_designer.gui.handler.project_handler import ProjectHandler
from paintjob_designer.gui.util.dialogs import (
    FilePicker,
    InputPrompt,
    MessageDialog,
)
from paintjob_designer.gui.util.library_writer import LibraryWriter
from paintjob_designer.gui.widget.paintjob_library_sidebar import PaintjobLibrarySidebar
from paintjob_designer.models import (
    CharacterProfile,
    Paintjob,
    PaintjobLibrary,
    SlotColors,
)
from paintjob_designer.paintjob.writer import PaintjobWriter

_PAINTJOB_EXT = ".json"
_PAINTJOB_FILTER = f"Paintjob (*{_PAINTJOB_EXT})"


class PaintjobLibraryController(LibraryController[Paintjob, PaintjobLibrary]):
    """Owns the paintjob library + sidebar + all paintjob CRUD."""

    def __init__(
        self,
        sidebar: PaintjobLibrarySidebar,
        project_handler: ProjectHandler,
        paintjob_writer: PaintjobWriter,
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
        self._project_handler = project_handler
        self._paintjob_writer = paintjob_writer
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
        self._sidebar.paintjobs_reordered.connect(self._on_reordered)
        self._sidebar.export_requested.connect(self.export_library)

    def set_iso_root(self, iso_root: str) -> None:
        self._iso_root = iso_root

    def _make_empty_library(self) -> PaintjobLibrary:
        return PaintjobLibrary()

    def _items(self) -> list[Paintjob]:
        return self._library.paintjobs

    def _item_label(self, item: Paintjob, index: int) -> str:
        return item.name.strip() or f"Paintjob {index + 1}"

    def _item_kind(self) -> str:
        return "paintjob"

    def _refresh_sidebar(self, selected_index: int | None) -> None:
        self._sidebar.set_library(self._library, selected_index=selected_index)

    def _remove_at(self, index: int) -> Paintjob:
        return self._library.remove(index)

    def _set_sidebar_selection(self, index: int) -> None:
        self._sidebar.set_selected_index(index)

    def new(self) -> None:
        base = self._character_picker.pick(
            "New paintjob — pick base character", parent=self._parent_widget,
        )

        if base is None:
            return

        paintjob = Paintjob(
            name=f"Paintjob {self._library.count() + 1}",
            kart_type=base.kart_type,
            base_character_id=base.id,
            slots=self._seed_slots(base),
        )

        index = self._library.add(paintjob)
        self._refresh_sidebar(index)
        self._after_mutation()

    def rename(self, index: int) -> None:
        if not (0 <= index < self._library.count()):
            return

        paintjob = self._library.paintjobs[index]
        new_name = self._prompt.get_text(
            self._parent_widget, "Rename paintjob", "Name:", paintjob.name,
        )

        if new_name is None:
            return

        paintjob.name = new_name.strip()
        self._refresh_sidebar(index)
        self._after_mutation()

    def set_author(self, index: int) -> None:
        if not (0 <= index < self._library.count()):
            return

        paintjob = self._library.paintjobs[index]
        new_author = self._prompt.get_text(
            self._parent_widget, "Set paintjob author",
            "Author:", paintjob.author,
        )

        if new_author is None:
            return

        paintjob.author = new_author.strip()
        self._refresh_sidebar(index)
        self._after_mutation()

    def change_base_character(self, index: int) -> None:
        profile = self._character_picker.current_profile()
        if profile is None or not (0 <= index < self._library.count()):
            return

        paintjob = self._library.paintjobs[index]
        none_label = "(none — unbound)"
        options = [none_label] + [c.id for c in profile.characters]
        current_value = paintjob.base_character_id or none_label
        current_index = options.index(current_value) if current_value in options else 0

        chosen = self._prompt.get_item(
            self._parent_widget, "Change base character",
            "Base character for this paintjob:", options, current_index,
        )

        if chosen is None:
            return

        paintjob.base_character_id = None if chosen == none_label else chosen
        self._refresh_sidebar(index)
        self._after_mutation()

        if paintjob is self._current:
            self.selection_changed.emit(self._current)

    def _on_reordered(self, from_index: int, to_index: int) -> None:
        self._library.move(from_index, to_index)
        self._sidebar.set_selected_index(to_index)
        self._after_mutation()

    def import_files(self, default_dir: str | None = None) -> None:
        for path in self._files.pick_open_paths(
            self._parent_widget, "Import paintjobs",
            default_dir, f"{_PAINTJOB_FILTER};;All files (*)",
        ):
            self.import_file(path)

    def import_file(self, path: Path) -> None:
        try:
            loaded = self._project_handler.load(path)
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
            self._parent_widget, "Replace paintjob from JSON",
            None, f"{_PAINTJOB_FILTER};;All files (*)",
        )

        if path is None:
            return

        try:
            loaded = self._project_handler.load(path)
        except (OSError, ValueError) as exc:
            self._message.error(self._parent_widget, "Import failed", str(exc))
            return

        self._library.paintjobs[index] = loaded
        self.library_reset.emit()
        self._refresh_sidebar(index)
        self._after_mutation()

    def export_one(self, paintjob: Paintjob) -> None:
        try:
            index = self._library.paintjobs.index(paintjob)
        except ValueError:
            return

        default_name = self._slug_filename(paintjob, index) + _PAINTJOB_EXT
        path = self._files.pick_save_path(
            self._parent_widget, "Export paintjob as JSON",
            default_name, _PAINTJOB_FILTER,
        )

        if path is None:
            return

        try:
            self._project_handler.save(path, paintjob)
        except OSError as exc:
            self._message.error(self._parent_widget, "Export failed", str(exc))

    def export_library(self) -> None:
        if self._library.count() == 0:
            self._message.info(
                self._parent_widget, "Nothing to save",
                "The paintjob library is empty — create or import at least one "
                "paintjob before saving.",
            )

            return

        directory = self._files.pick_directory(
            self._parent_widget, "Save paintjob library",
        )

        if directory is None:
            return

        try:
            self._library_writer.write(
                directory, self._library.paintjobs,
                filename_for=self._library_filename,
                serialize=self._paintjob_writer.serialize,
            )
        except OSError as exc:
            self._message.error(
                self._parent_widget, "Save library failed", str(exc),
            )

    def select_paintjob(self, paintjob: Paintjob) -> None:
        try:
            self._set_sidebar_selection(self._library.paintjobs.index(paintjob))
            self._current = paintjob
        except ValueError:
            pass

    def _on_context_menu(self, index: int, global_pos: QPoint) -> None:
        if not (0 <= index < self._library.count()):
            return

        paintjob = self._library.paintjobs[index]
        menu = QMenu(self._parent_widget)
        menu.addAction("Edit metadata...", lambda: self.edit_metadata(index))
        menu.addSeparator()
        menu.addAction("Export as JSON...", lambda: self.export_one(paintjob))
        menu.addAction("Replace from JSON...", lambda: self.replace_from_file(index))
        menu.addSeparator()
        menu.addAction("Delete", lambda: self.delete(index))
        menu.exec(global_pos)

    def edit_metadata(self, index: int) -> None:
        from paintjob_designer.gui.dialog.edit_metadata_dialog import (
            EditMetadataDialog,
        )

        if not (0 <= index < self._library.count()):
            return

        paintjob = self._library.paintjobs[index]
        profile = self._character_picker.current_profile()
        base_options = (
            [c.id for c in profile.characters] if profile is not None else []
        )

        dialog = EditMetadataDialog(
            self._parent_widget,
            title="Edit paintjob metadata",
            name=paintjob.name,
            author=paintjob.author,
            base_character_options=base_options,
            base_character_current=paintjob.base_character_id,
        )

        edit = dialog.exec_get()
        if edit is None:
            return

        self.apply_metadata(index, edit)

    def apply_metadata(self, index: int, edit) -> None:
        """Atomic mutation: name + author + base_character_id in one go.
        Pure data manipulation; unit-testable without a Qt event loop.
        """
        if not (0 <= index < self._library.count()):
            return

        paintjob = self._library.paintjobs[index]
        previous_base = paintjob.base_character_id
        paintjob.name = edit.name
        paintjob.author = edit.author
        paintjob.base_character_id = edit.base_character_id

        self._refresh_sidebar(index)
        self._after_mutation()

        if paintjob is self._current and previous_base != edit.base_character_id:
            self.selection_changed.emit(self._current)

    def _seed_slots(self, character: CharacterProfile) -> dict[str, SlotColors]:
        slots: dict[str, SlotColors] = {}

        for slot_profile in character.kart_slots:
            defaults = self._color_handler.default_slot_colors_at(
                self._iso_root, slot_profile.clut_race.x, slot_profile.clut_race.y,
            )
            slots[slot_profile.name] = SlotColors(colors=list(defaults))

        return slots

    def _library_filename(self, paintjob: Paintjob, index: int) -> str:
        slug = (
            self._slugifier.slugify(paintjob.name)
            or paintjob.base_character_id or "paintjob"
        )

        return f"{index:02d}_{slug}{_PAINTJOB_EXT}"

    def _slug_filename(self, paintjob: Paintjob, index: int) -> str:
        return (
            self._slugifier.slugify(paintjob.name)
            or paintjob.base_character_id
            or f"paintjob_{index:02d}"
        )
