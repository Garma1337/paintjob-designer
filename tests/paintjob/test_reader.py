# coding: utf-8

import json

import pytest

from paintjob_designer.models import Paintjob, SlotColors


def _sixteen_hex() -> list[str]:
    return [f"#{v:02x}{v:02x}{v:02x}" for v in range(16)]


def _paintjob_json(**overrides) -> str:
    doc = {
        "schema_version": 1,
        "name": "Lime Racer",
        "author": "Garma",
        "slots": {
            "front": _sixteen_hex(),
            "back": _sixteen_hex(),
        },
    }

    doc.update(overrides)
    return json.dumps(doc)


class TestPaintjobReader:

    def test_reads_metadata(self, paintjob_reader):
        paintjob = paintjob_reader.read(_paintjob_json())

        assert paintjob.schema_version == 1
        assert paintjob.name == "Lime Racer"
        assert paintjob.author == "Garma"

    def test_reads_slots(self, paintjob_reader):
        paintjob = paintjob_reader.read(_paintjob_json())

        assert set(paintjob.slots.keys()) == {"front", "back"}
        assert isinstance(paintjob.slots["front"], SlotColors)
        assert len(paintjob.slots["front"].colors) == 16

    def test_quantizes_colors_to_psx(self, paintjob_reader):
        # #5aff00 -> PSX value 0x03EB (see ColorConverter tests).
        doc = _paintjob_json(slots={"front": ["#5aff00"] * 16})

        paintjob = paintjob_reader.read(doc)

        assert all(c.value == 0x03EB for c in paintjob.slots["front"].colors)

    def test_reads_base_character_id(self, paintjob_reader):
        doc = _paintjob_json(base_character_id="crash")

        paintjob = paintjob_reader.read(doc)

        assert paintjob.base_character_id == "crash"

    def test_missing_base_character_id_is_none(self, paintjob_reader):
        paintjob = paintjob_reader.read(_paintjob_json())

        assert paintjob.base_character_id is None

    def test_null_base_character_id_is_none(self, paintjob_reader):
        doc = _paintjob_json(base_character_id=None)

        paintjob = paintjob_reader.read(doc)

        assert paintjob.base_character_id is None

    def test_rejects_non_object_root(self, paintjob_reader):
        with pytest.raises(ValueError, match="root must be a JSON object"):
            paintjob_reader.read("[]")

    def test_rejects_future_schema(self, paintjob_reader):
        with pytest.raises(ValueError, match="newer than this tool supports"):
            paintjob_reader.read(_paintjob_json(schema_version=999))

    def test_in_memory_object_reports_current_schema(self, paintjob_reader):
        # Even when the on-disk file declared a lower version (a hypothetical
        # future migration path), the returned Paintjob should report the
        # reader's current SCHEMA_VERSION.
        doc = _paintjob_json(schema_version=0)
        paintjob = paintjob_reader.read(doc)

        assert paintjob.schema_version == Paintjob.SCHEMA_VERSION

    def test_rejects_non_dict_slots(self, paintjob_reader):
        doc = json.dumps({"schema_version": 1, "slots": []})

        with pytest.raises(ValueError, match="'slots' must be an object"):
            paintjob_reader.read(doc)

    def test_rejects_wrong_color_count(self, paintjob_reader):
        doc = _paintjob_json(slots={"front": ["#000000"] * 8})

        with pytest.raises(ValueError, match="exactly 16 colors"):
            paintjob_reader.read(doc)
