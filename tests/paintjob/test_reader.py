# coding: utf-8

import base64
import json

import pytest

from paintjob_designer.models import Paintjob, SlotColors


def _sixteen_hex() -> list[str]:
    return [f"#{v:02x}{v:02x}{v:02x}" for v in range(16)]


def _colors_only_slot() -> dict:
    return {"colors": _sixteen_hex(), "pixels": []}


def _paintjob_json(**overrides) -> str:
    doc = {
        "schema_version": 1,
        "name": "Lime Racer",
        "author": "Garma",
        "slots": {
            "front": _colors_only_slot(),
            "back": _colors_only_slot(),
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
        doc = _paintjob_json(
            slots={"front": {"colors": ["#5aff00"] * 16, "pixels": []}},
        )

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

    def test_unknown_top_level_fields_are_ignored(self, paintjob_reader):
        # Forward-compat: a JSON with extra fields should still parse.
        # Reader doesn't error, doesn't lose known data.
        doc = _paintjob_json(locked_character_id="crash", mystery_flag=True)

        paintjob = paintjob_reader.read(doc)

        assert paintjob.name == "Lime Racer"

    def test_slots_with_no_pixels_have_empty_pixel_list(self, paintjob_reader):
        paintjob = paintjob_reader.read(_paintjob_json())

        assert paintjob.slots["front"].pixels == []

    def test_reads_per_region_pixel_payload(self, paintjob_reader):
        # 4bpp packed: 2x1 → 1 byte.
        raw_bytes = bytes([0x21])
        doc = _paintjob_json(
            slots={
                "front": {
                    "colors": _sixteen_hex(),
                    "pixels": [
                        {
                            "vram_x": 320,
                            "vram_y": 128,
                            "width": 2,
                            "height": 1,
                            "data": base64.b64encode(raw_bytes).decode("ascii"),
                        },
                    ],
                },
            },
        )

        paintjob = paintjob_reader.read(doc)

        regions = paintjob.slots["front"].pixels
        assert len(regions) == 1
        assert regions[0].vram_x == 320
        assert regions[0].vram_y == 128
        assert regions[0].width == 2
        assert regions[0].height == 1
        assert regions[0].pixels == raw_bytes

    def test_rejects_non_object_root(self, paintjob_reader):
        with pytest.raises(ValueError, match="root must be a JSON object"):
            paintjob_reader.read("[]")

    def test_rejects_future_schema(self, paintjob_reader):
        with pytest.raises(ValueError, match="newer than this tool supports"):
            paintjob_reader.read(_paintjob_json(schema_version=999))

    def test_in_memory_object_reports_current_schema(self, paintjob_reader):
        doc = _paintjob_json(schema_version=0)
        paintjob = paintjob_reader.read(doc)

        assert paintjob.schema_version == Paintjob.SCHEMA_VERSION

    def test_rejects_non_dict_slots(self, paintjob_reader):
        doc = json.dumps({"schema_version": 1, "slots": []})

        with pytest.raises(ValueError, match="'slots' must be an object"):
            paintjob_reader.read(doc)

    def test_rejects_slot_as_list(self, paintjob_reader):
        # Old list-shape slot is no longer accepted — the format is always
        # an object with 'colors' and 'pixels'. Clear error so artists know
        # they're hitting a pre-release format file.
        doc = json.dumps(
            {
                "schema_version": 1,
                "slots": {"front": _sixteen_hex()},
            },
        )

        with pytest.raises(ValueError, match="must be an object"):
            paintjob_reader.read(doc)

    def test_rejects_wrong_color_count(self, paintjob_reader):
        doc = _paintjob_json(
            slots={"front": {"colors": ["#000000"] * 8, "pixels": []}},
        )

        with pytest.raises(ValueError, match="exactly 16 colors"):
            paintjob_reader.read(doc)

    def test_rejects_invalid_base64_pixels(self, paintjob_reader):
        doc = _paintjob_json(
            slots={
                "front": {
                    "colors": _sixteen_hex(),
                    "pixels": [
                        {
                            "vram_x": 0, "vram_y": 0, "width": 2, "height": 1,
                            "data": "not valid base64!!",
                        },
                    ],
                },
            },
        )

        with pytest.raises(ValueError, match="base64"):
            paintjob_reader.read(doc)
