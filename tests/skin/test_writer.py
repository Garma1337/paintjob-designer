# coding: utf-8

import json

from paintjob_designer.models import PsxColor, Rgb888, Skin, SlotColors


def _slot_of(value: int = 0x7FFF) -> SlotColors:
    return SlotColors(colors=[PsxColor(value=value) for _ in range(SlotColors.SIZE)])


class TestSkinWriter:

    def test_serializes_metadata(self, skin_writer):
        skin = Skin(name="Crash skin", author="Garma", character_id="crash")

        doc = json.loads(skin_writer.serialize(skin))

        assert doc["schema_version"] == 1
        assert doc["name"] == "Crash skin"
        assert doc["author"] == "Garma"
        assert doc["character_id"] == "crash"
        assert doc["slots"] == {}
        assert doc["vertex_overrides"] == {}

    def test_serializes_slot_as_object_with_colors_and_pixels(self, skin_writer):
        skin = Skin(
            name="x", character_id="crash",
            slots={"extra_112_253": _slot_of(value=0x7FFF)},
        )

        doc = json.loads(skin_writer.serialize(skin))

        assert doc["slots"]["extra_112_253"] == {
            "colors": ["#7fff"] * 16,
            "pixels": [],
        }

    def test_serializes_vertex_overrides_with_string_keys(self, skin_writer):
        # JSON only allows string object keys — pydantic emits the int as
        # its string repr. The reader test verifies the round-trip back to
        # int.
        skin = Skin(
            name="x", character_id="crash",
            vertex_overrides={
                0: Rgb888(r=255, g=0, b=0),
                12: Rgb888(r=0, g=128, b=255),
            },
        )

        doc = json.loads(skin_writer.serialize(skin))

        assert doc["vertex_overrides"] == {
            "0": {"r": 255, "g": 0, "b": 0},
            "12": {"r": 0, "g": 128, "b": 255},
        }
