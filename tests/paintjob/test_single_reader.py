# coding: utf-8

import json

import pytest

from paintjob_designer.models import SlotColors


def _sixteen_hex() -> list[str]:
    return [f"#{v:02x}{v:02x}{v:02x}" for v in range(16)]


def _single_paintjob_json(**overrides) -> str:
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


class TestSinglePaintjobReader:

    def test_reads_metadata(self, single_paintjob_reader):
        paintjob = single_paintjob_reader.read(_single_paintjob_json())

        assert paintjob.schema_version == 1
        assert paintjob.name == "Lime Racer"
        assert paintjob.author == "Garma"

    def test_reads_slots(self, single_paintjob_reader):
        paintjob = single_paintjob_reader.read(_single_paintjob_json())

        assert set(paintjob.slots.keys()) == {"front", "back"}
        assert isinstance(paintjob.slots["front"], SlotColors)
        assert len(paintjob.slots["front"].colors) == 16

    def test_quantizes_colors_to_psx(self, single_paintjob_reader):
        # #5aff00 -> PSX value 0x03EB (see ColorConverter tests).
        doc = _single_paintjob_json(slots={"front": ["#5aff00"] * 16})

        paintjob = single_paintjob_reader.read(doc)

        assert all(c.value == 0x03EB for c in paintjob.slots["front"].colors)

    def test_rejects_non_object_root(self, single_paintjob_reader):
        with pytest.raises(ValueError, match="root must be a JSON object"):
            single_paintjob_reader.read("[]")

    def test_rejects_future_schema(self, single_paintjob_reader):
        with pytest.raises(ValueError, match="newer than this tool supports"):
            single_paintjob_reader.read(_single_paintjob_json(schema_version=999))

    def test_accepts_older_schema_via_migration(self, single_paintjob_reader):
        # `_migrate` is a no-op at v1, but a file declaring an older version
        # should still load without the reader rejecting it — the migration
        # pipeline exists precisely so we can keep reading old files.
        doc = _single_paintjob_json(schema_version=0)
        paintjob = single_paintjob_reader.read(doc)

        # After migration the in-memory object always reports the current
        # schema, regardless of what was on disk.
        from paintjob_designer.models import SinglePaintjob
        assert paintjob.schema_version == SinglePaintjob.SCHEMA_VERSION

    def test_rejects_non_dict_slots(self, single_paintjob_reader):
        doc = json.dumps({"schema_version": 1, "slots": []})

        with pytest.raises(ValueError, match="'slots' must be an object"):
            single_paintjob_reader.read(doc)

    def test_rejects_wrong_color_count(self, single_paintjob_reader):
        doc = _single_paintjob_json(slots={"front": ["#000000"] * 8})

        with pytest.raises(ValueError, match="exactly 16 colors"):
            single_paintjob_reader.read(doc)
