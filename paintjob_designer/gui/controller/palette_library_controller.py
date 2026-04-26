# coding: utf-8

from pathlib import Path

from PIL import Image
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget

from paintjob_designer.color.converter import ColorConverter
from paintjob_designer.gui.controller.library_controller import LibraryController
from paintjob_designer.gui.dialog.palette_edit_dialog import PaletteEditDialog
from paintjob_designer.gui.util.dialogs import FilePicker, InputPrompt, MessageDialog
from paintjob_designer.gui.widget.palette_sidebar import PaletteSidebar
from paintjob_designer.models import Palette, PaletteLibrary, PsxColor
from paintjob_designer.palette.palette_from_colors_creator import PaletteFromColorsCreator
from paintjob_designer.palette.palette_from_image_creator import PaletteFromImageCreator


class PaletteLibraryController(LibraryController[Palette, PaletteLibrary]):
    """Owns the palette library + sidebar."""

    save_from_slot_requested = Signal()

    def __init__(
        self,
        sidebar: PaletteSidebar,
        color_converter: ColorConverter,
        message: MessageDialog,
        prompt: InputPrompt,
        files: FilePicker,
        palette_from_image_creator: PaletteFromImageCreator,
        palette_from_colors_creator: PaletteFromColorsCreator,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(message, parent)
        self._sidebar = sidebar
        self._converter = color_converter
        self._prompt = prompt
        self._files = files
        self._palette_from_image = palette_from_image_creator
        self._palette_from_colors = palette_from_colors_creator

        self._sidebar.new_palette_requested.connect(self.new)
        self._sidebar.save_from_slot_requested.connect(
            self.save_from_slot_requested,
        )
        self._sidebar.save_from_image_requested.connect(self.save_from_image)
        self._sidebar.delete_palette_requested.connect(self.delete)
        self._sidebar.edit_palette_requested.connect(self.edit)
        self._sidebar.rename_palette_requested.connect(self.rename)

    def _make_empty_library(self) -> PaletteLibrary:
        return PaletteLibrary()

    def _items(self) -> list[Palette]:
        return self._library.palettes

    def _item_label(self, item: Palette, index: int) -> str:
        return item.name.strip() or f"Palette {index + 1}"

    def _item_kind(self) -> str:
        return "palette"

    def _refresh_sidebar(self, selected_index: int | None) -> None:
        self._sidebar.set_palettes(
            self._library.palettes, selected_index=selected_index,
        )

    def _remove_at(self, index: int) -> Palette:
        return self._library.palettes.pop(index)

    def show_initial(self) -> None:
        self._refresh_sidebar(None)

    def new(self) -> None:
        seed = Palette(name=f"Palette {len(self._library.palettes) + 1}")
        self._run_palette_dialog(seed, replace_index=None)

    def add_from_colors(self, colors: list[PsxColor], default_name: str) -> None:
        seed = self._palette_from_colors.create(colors, default_name)
        self._run_palette_dialog(seed, replace_index=None)

    def save_from_image(self) -> None:
        path = self._files.pick_open_path(
            self._parent_widget, "Pick image to quantize",
            None, "PNG images (*.png);;All files (*)",
        )

        if path is None:
            return

        try:
            with Image.open(path) as src:
                palette = self._palette_from_image.create(src, Path(path).stem)
        except (OSError, ValueError) as exc:
            self._message.error(
                self._parent_widget, "Palette from image failed", str(exc),
            )

            return

        self._run_palette_dialog(palette, replace_index=None)

    def edit(self, index: int) -> None:
        if not (0 <= index < len(self._library.palettes)):
            return

        self._run_palette_dialog(
            self._library.palettes[index], replace_index=index,
        )

    def rename(self, index: int) -> None:
        if not (0 <= index < len(self._library.palettes)):
            return

        palette = self._library.palettes[index]
        new_name = self._prompt.get_text(
            self._parent_widget, "Rename palette", "Name:", palette.name,
        )

        if new_name is None:
            return

        palette.name = new_name.strip()
        self._refresh_sidebar(index)
        self._after_mutation()

    def _run_palette_dialog(
        self, seed: Palette, *, replace_index: int | None,
    ) -> None:
        """Open the edit dialog for `seed`. On accept, append (replace_index
        is None) or replace at the given index."""
        dialog = PaletteEditDialog(
            seed, self._converter, parent=self._parent_widget,
        )

        if dialog.exec() != PaletteEditDialog.DialogCode.Accepted:
            return

        result = dialog.resulting_palette()
        if replace_index is None:
            self._library.palettes.append(result)
            selected = len(self._library.palettes) - 1
        else:
            self._library.palettes[replace_index] = result
            selected = replace_index

        self._refresh_sidebar(selected)
        self._after_mutation()
