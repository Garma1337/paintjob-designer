# coding: utf-8

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from paintjob_designer.core import Slugifier
from paintjob_designer.gui.controller.character_picker import CharacterPicker
from paintjob_designer.gui.controller.paintjob_library_controller import (
    PaintjobLibraryController,
)
from paintjob_designer.gui.util.library_writer import LibraryWriter
from paintjob_designer.gui.widget.paintjob_library_sidebar import (
    PaintjobLibrarySidebar,
)
from paintjob_designer.models import (
    KartType,
    MetadataEdit,
    Paintjob,
    PaintjobLibrary,
    PsxColor,
    SlotColors,
)
from paintjob_designer.paintjob.writer import PaintjobWriter


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
    fake.get_item.return_value = None
    return fake


@pytest.fixture
def fake_project_handler():
    handler = MagicMock()
    handler.load.side_effect = lambda path: Paintjob(
        name=path.stem, kart_type=KartType.KART, slots={},
    )
    return handler


@pytest.fixture
def fake_color_handler():
    return MagicMock()


@pytest.fixture
def empty_profile_picker():
    return CharacterPicker(profile_provider=lambda: None)


@pytest.fixture
def controller(
    qapp, fake_project_handler, fake_message, fake_files, fake_prompt,
    empty_profile_picker, fake_color_handler,
):
    sidebar = PaintjobLibrarySidebar()
    return PaintjobLibraryController(
        sidebar=sidebar,
        project_handler=fake_project_handler,
        paintjob_writer=PaintjobWriter(),
        library_writer=LibraryWriter(),
        message=fake_message,
        files=fake_files,
        prompt=fake_prompt,
        slugifier=Slugifier(),
        character_picker=empty_profile_picker,
        color_handler=fake_color_handler,
    )


def _slot() -> SlotColors:
    return SlotColors(colors=[PsxColor(value=0) for _ in range(SlotColors.SIZE)])


def _seed_two_paintjobs(controller: PaintjobLibraryController) -> None:
    library = PaintjobLibrary()
    library.add(Paintjob(name="alpha", kart_type=KartType.KART, slots={"a": _slot()}))
    library.add(Paintjob(name="beta", kart_type=KartType.KART, slots={"b": _slot()}))
    controller.replace_library(library)


def test_replace_library_clears_selection(controller):
    _seed_two_paintjobs(controller)
    assert controller.current is None
    assert controller.library.count() == 2


def test_show_initial_selection_picks_first(controller):
    _seed_two_paintjobs(controller)
    controller.show_initial_selection()
    assert controller.current is controller.library.paintjobs[0]


def test_delete_confirms_then_removes(controller, fake_message, fake_files, fake_prompt):
    _seed_two_paintjobs(controller)
    controller.delete(0)

    fake_message.confirm_destructive.assert_called_once()
    assert controller.library.count() == 1
    assert controller.library.paintjobs[0].name == "beta"


def test_delete_aborts_when_user_cancels(controller, fake_message, fake_files, fake_prompt):
    _seed_two_paintjobs(controller)
    fake_message.confirm_destructive.return_value = False
    controller.delete(0)

    assert controller.library.count() == 2


def test_rename_writes_new_name(controller, fake_message, fake_files, fake_prompt):
    _seed_two_paintjobs(controller)
    fake_prompt.get_text.return_value = "renamed"
    controller.rename(0)

    assert controller.library.paintjobs[0].name == "renamed"


def test_rename_aborts_when_user_cancels(controller, fake_message, fake_files, fake_prompt):
    _seed_two_paintjobs(controller)
    fake_prompt.get_text.return_value = None
    controller.rename(0)

    assert controller.library.paintjobs[0].name == "alpha"


def test_set_author_writes_new_value(controller, fake_message, fake_files, fake_prompt):
    _seed_two_paintjobs(controller)
    fake_prompt.get_text.return_value = "Garma"
    controller.set_author(1)

    assert controller.library.paintjobs[1].author == "Garma"


def test_apply_metadata_writes_all_three_fields(controller):
    _seed_two_paintjobs(controller)

    controller.apply_metadata(0, MetadataEdit(
        name="renamed", author="Garma", base_character_id="cortex",
    ))

    paintjob = controller.library.paintjobs[0]
    assert paintjob.name == "renamed"
    assert paintjob.author == "Garma"
    assert paintjob.base_character_id == "cortex"


def test_apply_metadata_supports_unbinding_base_character(controller):
    _seed_two_paintjobs(controller)

    controller.apply_metadata(0, MetadataEdit(
        name="alpha", author="", base_character_id=None,
    ))

    assert controller.library.paintjobs[0].base_character_id is None


def test_apply_metadata_ignores_out_of_range_index(controller):
    _seed_two_paintjobs(controller)
    before = [p.name for p in controller.library.paintjobs]

    controller.apply_metadata(99, MetadataEdit(
        name="ghost", author="x", base_character_id=None,
    ))

    assert [p.name for p in controller.library.paintjobs] == before


def test_export_library_skips_when_empty(controller, fake_message, fake_files, fake_prompt):
    controller.export_library()

    fake_message.info.assert_called_once()
    fake_files.pick_directory.assert_not_called()


def test_export_library_writes_files(controller, fake_message, fake_files, fake_prompt, tmp_path):
    _seed_two_paintjobs(controller)
    fake_files.pick_directory.return_value = tmp_path

    controller.export_library()

    written = sorted(p.name for p in tmp_path.iterdir())
    assert written == ["00_alpha.json", "01_beta.json"]


def test_import_file_appends_to_library(controller, tmp_path: Path):
    path = tmp_path / "imported.json"
    path.write_text("{}")

    controller.import_file(path)

    assert controller.library.count() == 1
    assert controller.library.paintjobs[0].name == "imported"


def test_import_file_reports_error_on_load_failure(
    controller, fake_project_handler, fake_message, fake_files, fake_prompt, tmp_path,
):
    fake_project_handler.load.side_effect = ValueError("bad json")

    controller.import_file(tmp_path / "bad.json")

    fake_message.error.assert_called_once()
    assert controller.library.count() == 0


def test_reorder_moves_in_library(controller):
    _seed_two_paintjobs(controller)
    controller._on_reordered(0, 1)

    assert controller.library.paintjobs[0].name == "beta"
    assert controller.library.paintjobs[1].name == "alpha"


def test_signals_emit_on_replace(controller, qapp):
    library_changed = []
    mutated = []
    controller.library_changed.connect(lambda: library_changed.append(True))
    controller.mutated.connect(lambda: mutated.append(True))

    library = PaintjobLibrary()
    library.add(Paintjob(name="x", kart_type=KartType.KART, slots={}))
    controller.replace_library(library)

    assert library_changed == [True]
    assert mutated == []
