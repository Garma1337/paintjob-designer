# coding: utf-8

import json

import pytest

from paintjob_designer.models import Rgb888, SlotColors


def _colors_only_slot() -> dict:
    return {"colors": ["#7fff"] * SlotColors.SIZE}


def _skin_json(**overrides) -> str:
    doc = {
        "schema_version": 1,
        "name": "Crash with red shirt",
        "author": "Garma",
        "character_id": "crash",
        "slots": {
            "extra_112_253": _colors_only_slot(),
        },
        "vertex_overrides": {
            "0": {"r": 255, "g": 0, "b": 0},
            "5": {"r": 0, "g": 255, "b": 0},
        },
    }

    doc.update(overrides)
    return json.dumps(doc)


class TestSkinReader:

    def test_reads_metadata(self, skin_reader):
        skin = skin_reader.read(_skin_json())

        # Reader normalizes the in-memory schema_version to current.
        assert skin.schema_version == 1
        assert skin.name == "Crash with red shirt"
        assert skin.author == "Garma"
        assert skin.character_id == "crash"

    def test_reads_slots(self, skin_reader):
        skin = skin_reader.read(_skin_json())

        assert set(skin.slots.keys()) == {"extra_112_253"}
        assert isinstance(skin.slots["extra_112_253"], SlotColors)
        assert len(skin.slots["extra_112_253"].colors) == 16

    def test_reads_vertex_overrides_with_int_keys(self, skin_reader):
        # JSON object keys are strings, but the model exposes int keys for
        # gouraud-table indexing — pydantic must coerce.
        skin = skin_reader.read(_skin_json())

        assert set(skin.vertex_overrides.keys()) == {0, 5}
        assert all(isinstance(k, int) for k in skin.vertex_overrides.keys())
        assert skin.vertex_overrides[0] == Rgb888(r=255, g=0, b=0)
        assert skin.vertex_overrides[5] == Rgb888(r=0, g=255, b=0)

    def test_accepts_bytes_input(self, skin_reader):
        skin = skin_reader.read(_skin_json().encode("utf-8"))

        assert skin.character_id == "crash"

    def test_rejects_missing_character_id(self, skin_reader):
        # Skins are character-bound, so the field is required (vs paintjob's
        # optional `base_character_id` hint).
        doc = json.dumps({"schema_version": 1, "name": "x"})

        with pytest.raises(ValueError, match="character_id"):
            skin_reader.read(doc)

    def test_rejects_empty_character_id(self, skin_reader):
        with pytest.raises(ValueError, match="character_id"):
            skin_reader.read(_skin_json(character_id=""))

    def test_rejects_non_object_root(self, skin_reader):
        with pytest.raises(ValueError, match="root must be a JSON object"):
            skin_reader.read("[]")

    def test_rejects_future_schema(self, skin_reader):
        with pytest.raises(ValueError, match="schema_version"):
            skin_reader.read(_skin_json(schema_version=999))

    def test_rejects_slot_with_wrong_color_count(self, skin_reader):
        doc = _skin_json(slots={"extra_112_253": {"colors": ["#7fff"] * 5}})

        with pytest.raises(ValueError, match="exactly 16 colors"):
            skin_reader.read(doc)

    def test_rejects_non_object_vertex_overrides(self, skin_reader):
        doc = _skin_json(vertex_overrides=[])

        with pytest.raises(ValueError, match="vertex_overrides"):
            skin_reader.read(doc)

    def test_empty_vertex_overrides_when_missing(self, skin_reader):
        # CLUT-only skins (no Gouraud edits) are valid — the field defaults
        # to an empty dict.
        doc = json.dumps({
            "schema_version": 1,
            "name": "x", "author": "", "character_id": "crash",
            "slots": {},
        })

        skin = skin_reader.read(doc)

        assert skin.vertex_overrides == {}
