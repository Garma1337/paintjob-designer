# coding: utf-8

from unittest.mock import MagicMock

import pytest

from paintjob_designer.color.converter import ColorConverter
from paintjob_designer.gui.controller.palette_library_controller import PaletteLibraryController
from paintjob_designer.gui.widget.palette_sidebar import PaletteSidebar
from paintjob_designer.models import Palette, PaletteLibrary


@pytest.fixture
def fake_message():
    fake = MagicMock()
    fake.confirm_destructive.return_value = True
    return fake


@pytest.fixture
def fake_prompt():
    fake = MagicMock()
    fake.get_text.return_value = "renamed"
    return fake


@pytest.fixture
def fake_files():
    fake = MagicMock()
    fake.pick_open_path.return_value = None
    return fake


@pytest.fixture
def fake_palette_from_image_creator():
    fake = MagicMock()
    fake.create.return_value = Palette(name="from_image")
    return fake


@pytest.fixture
def fake_palette_from_colors_creator():
    fake = MagicMock()
    fake.create.return_value = Palette(name="from_colors")
    return fake


@pytest.fixture
def controller(
    qapp, fake_message, fake_prompt, fake_files,
    fake_palette_from_image_creator, fake_palette_from_colors_creator,
):
    converter = ColorConverter()
    sidebar = PaletteSidebar(converter)
    return PaletteLibraryController(
        sidebar=sidebar,
        color_converter=converter,
        message=fake_message,
        prompt=fake_prompt,
        files=fake_files,
        palette_from_image_creator=fake_palette_from_image_creator,
        palette_from_colors_creator=fake_palette_from_colors_creator,
    )


def _seed(controller: PaletteLibraryController) -> None:
    library = PaletteLibrary(palettes=[
        Palette(name="warm"),
        Palette(name="cool"),
    ])
    controller.replace_library(library)


def test_replace_library_swaps_palettes(controller):
    _seed(controller)
    assert [p.name for p in controller.library.palettes] == ["warm", "cool"]


def test_delete_removes_after_confirm(controller, fake_message):
    _seed(controller)
    controller.delete(0)

    assert [p.name for p in controller.library.palettes] == ["cool"]
    fake_message.confirm_destructive.assert_called_once()


def test_delete_aborts_on_cancel(controller, fake_message):
    _seed(controller)
    fake_message.confirm_destructive.return_value = False

    controller.delete(0)

    assert len(controller.library.palettes) == 2


def test_rename_writes_new_name(controller, fake_prompt):
    _seed(controller)
    fake_prompt.get_text.return_value = "spicy"

    controller.rename(1)

    assert controller.library.palettes[1].name == "spicy"


def test_rename_aborts_on_cancel(controller, fake_prompt):
    _seed(controller)
    fake_prompt.get_text.return_value = None

    controller.rename(1)

    assert controller.library.palettes[1].name == "cool"


def test_out_of_bounds_index_is_safe(controller):
    _seed(controller)
    controller.delete(99)
    controller.rename(-1)
    controller.edit(5)

    assert len(controller.library.palettes) == 2


def test_save_from_image_aborts_when_user_cancels_picker(controller, fake_files, fake_palette_from_image_creator):
    fake_files.pick_open_path.return_value = None

    controller.save_from_image()

    fake_palette_from_image_creator.create.assert_not_called()
