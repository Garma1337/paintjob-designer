# coding: utf-8

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from paintjob_designer.core import Slugifier
from paintjob_designer.gui.controller.character_picker import CharacterPicker
from paintjob_designer.gui.controller.skin_library_controller import SkinLibraryController
from paintjob_designer.gui.util.library_writer import LibraryWriter
from paintjob_designer.gui.widget.skin_library_sidebar import SkinLibrarySidebar
from paintjob_designer.models import MetadataEdit, Skin, SkinLibrary
from paintjob_designer.skin.writer import SkinWriter


@pytest.fixture
def fake_message():
    fake = MagicMock()
    fake.confirm_destructive.return_value = True
    return fake


@pytest.fixture
def fake_files():
    fake = MagicMock()
    fake.pick_directory.return_value = None
    fake.pick_open_paths.return_value = []
    fake.pick_open_path.return_value = None
    fake.pick_save_path.return_value = None
    return fake


@pytest.fixture
def fake_prompt():
    fake = MagicMock()
    fake.get_text.return_value = "default"
    return fake


@pytest.fixture
def fake_skin_reader():
    reader = MagicMock()
    reader.read.side_effect = lambda data: Skin(
        name="imported", character_id="crash",
    )
    return reader


@pytest.fixture
def empty_profile_picker():
    return CharacterPicker(profile_provider=lambda: None)


@pytest.fixture
def controller(
    qapp, fake_message, fake_files, fake_prompt,
    fake_skin_reader, empty_profile_picker,
):
    sidebar = SkinLibrarySidebar()
    return SkinLibraryController(
        sidebar=sidebar,
        skin_reader=fake_skin_reader,
        skin_writer=SkinWriter(),
        library_writer=LibraryWriter(),
        message=fake_message,
        files=fake_files,
        prompt=fake_prompt,
        slugifier=Slugifier(),
        character_picker=empty_profile_picker,
        color_handler=MagicMock(),
    )


def _seed(controller: SkinLibraryController) -> None:
    library = SkinLibrary()
    library.add(Skin(name="warpaint", character_id="crash"))
    library.add(Skin(name="bandanna", character_id="cortex"))
    controller.replace_library(library)


def test_replace_library_clears_selection(controller):
    _seed(controller)
    assert controller.current is None
    assert controller.library.count() == 2


def test_delete_confirms_and_removes(controller, fake_message):
    _seed(controller)
    controller.delete(0)

    fake_message.confirm_destructive.assert_called_once()
    assert controller.library.count() == 1
    assert controller.library.skins[0].name == "bandanna"


def test_delete_aborts_when_user_cancels(controller, fake_message):
    _seed(controller)
    fake_message.confirm_destructive.return_value = False

    controller.delete(0)

    assert controller.library.count() == 2


def test_rename_writes_new_name(controller, fake_prompt):
    _seed(controller)
    fake_prompt.get_text.return_value = "renamed"
    controller.rename(0)

    assert controller.library.skins[0].name == "renamed"


def test_rename_aborts_when_user_cancels(controller, fake_prompt):
    _seed(controller)
    fake_prompt.get_text.return_value = None
    controller.rename(0)

    assert controller.library.skins[0].name == "warpaint"


def test_set_author_writes_new_value(controller, fake_prompt):
    _seed(controller)
    fake_prompt.get_text.return_value = "Garma"
    controller.set_author(1)

    assert controller.library.skins[1].author == "Garma"


def test_apply_metadata_writes_name_and_author(controller):
    _seed(controller)

    controller.apply_metadata(0, MetadataEdit(
        name="Renamed", author="Garma", base_character_id=None,
    ))

    skin = controller.library.skins[0]
    assert skin.name == "Renamed"
    assert skin.author == "Garma"


def test_apply_metadata_does_not_change_character_id(controller):
    _seed(controller)
    original_char = controller.library.skins[0].character_id

    # Even passing a base_character_id, skin's character_id is immutable.
    controller.apply_metadata(0, MetadataEdit(
        name="x", author="y", base_character_id="some-other-character",
    ))

    assert controller.library.skins[0].character_id == original_char


def test_export_library_writes_files(controller, fake_files, tmp_path):
    _seed(controller)
    fake_files.pick_directory.return_value = tmp_path

    controller.export_library()

    names = sorted(p.name for p in tmp_path.iterdir())
    assert names == ["00_warpaint.json", "01_bandanna.json"]


def test_export_library_skips_when_empty(controller, fake_message, fake_files):
    controller.export_library()

    fake_message.info.assert_called_once()
    fake_files.pick_directory.assert_not_called()


def test_import_file_appends_to_library(controller, tmp_path: Path):
    path = tmp_path / "imported.json"
    path.write_text("{}")

    controller.import_file(path)

    assert controller.library.count() == 1
    assert controller.library.skins[0].name == "imported"


def test_import_file_reports_error_on_load_failure(
    controller, fake_skin_reader, fake_message, tmp_path,
):
    fake_skin_reader.read.side_effect = ValueError("bad json")

    controller.import_file(tmp_path / "bad.json")

    fake_message.error.assert_called_once()
    assert controller.library.count() == 0
