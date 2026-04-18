# coding: utf-8

from paintjob_designer.models import (
    CharacterPaintjob,
    Paintjob,
    PsxColor,
    SinglePaintjob,
    SlotColors,
)
from tests.conftest import slot_of


class TestStandaloneRoundTrip:

    def test_save_then_open_preserves_slots(self, project_handler, tmp_path):
        original = SinglePaintjob(
            name="Lime",
            author="Garma",
            slots={"front": slot_of(value=0x03EB)},
        )
        path = tmp_path / "lime.json"

        project_handler.save_standalone(path, original)
        loaded = project_handler.open_standalone(path)

        assert loaded.name == "Lime"
        assert loaded.slots["front"].colors[0].value == 0x03EB

    def test_save_creates_parent_directory(self, project_handler, tmp_path):
        deep = tmp_path / "a" / "b" / "c" / "mine.json"

        project_handler.save_standalone(deep, SinglePaintjob())

        assert deep.exists()


class TestExtractCharacterAsStandalone:

    def test_copies_slots_for_the_requested_character(self, project_handler):
        project = Paintjob(characters={
            "crash":  CharacterPaintjob(slots={"front": slot_of(value=0x03EB)}),
            "cortex": CharacterPaintjob(slots={"front": slot_of(value=0x7C00)}),
        })

        single = project_handler.extract_character_as_standalone(project, "crash")

        assert single.slots["front"].colors[0].value == 0x03EB

    def test_missing_character_returns_empty_slots(self, project_handler):
        single = project_handler.extract_character_as_standalone(Paintjob(), "crash")

        assert single.slots == {}

    def test_returned_slots_are_independent_of_project(self, project_handler):
        project = Paintjob(characters={
            "crash": CharacterPaintjob(slots={"front": slot_of()}),
        })

        single = project_handler.extract_character_as_standalone(project, "crash")
        single.slots["back"] = slot_of(value=0x7FFF)

        assert "back" not in project.characters["crash"].slots

    def test_defaults_backfill_missing_slots(self, project_handler):
        project = Paintjob(characters={
            "crash": CharacterPaintjob(slots={"front": slot_of(value=0x03EB)}),
        })
        defaults = {
            "front": [PsxColor(value=0)] * SlotColors.SIZE,
            "back":  [PsxColor(value=0x7C00)] * SlotColors.SIZE,
        }

        single = project_handler.extract_character_as_standalone(
            project, "crash", defaults_by_slot=defaults,
        )

        # Edited slot wins over default.
        assert single.slots["front"].colors[0].value == 0x03EB
        # Un-edited slot is backfilled from the defaults.
        assert single.slots["back"].colors[0].value == 0x7C00


class TestApplyStandaloneToCharacter:

    def test_overwrites_character_slots(self, project_handler):
        project = Paintjob(characters={
            "crash": CharacterPaintjob(slots={"front": slot_of(value=0x1111)}),
        })
        standalone = SinglePaintjob(slots={"back": slot_of(value=0x2222)})

        project_handler.apply_standalone_to_character(project, "crash", standalone)

        assert "front" not in project.characters["crash"].slots
        assert project.characters["crash"].slots["back"].colors[0].value == 0x2222

    def test_creates_character_entry_when_missing(self, project_handler):
        project = Paintjob()
        standalone = SinglePaintjob(slots={"front": slot_of(value=0x3333)})

        project_handler.apply_standalone_to_character(project, "cortex", standalone)

        assert "cortex" in project.characters
        assert project.characters["cortex"].slots["front"].colors[0].value == 0x3333
