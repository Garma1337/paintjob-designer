# coding: utf-8

import base64
import json

from paintjob_designer.models import Paintjob, SlotColors, SlotRegionPixels
from tests.conftest import slot_of


class TestPaintjobWriter:

    def test_serializes_metadata(self, paintjob_writer):
        paintjob = Paintjob(name="Lime", author="Garma")

        doc = json.loads(paintjob_writer.serialize(paintjob))

        assert doc["schema_version"] == 1
        assert doc["name"] == "Lime"
        assert doc["author"] == "Garma"
        assert doc["base_character_id"] is None
        assert doc["slots"] == {}

    def test_serializes_slot_as_object_with_colors_and_pixels(self, paintjob_writer):
        paintjob = Paintjob(
            name="White",
            slots={"front": slot_of(value=0x7FFF)},
        )

        doc = json.loads(paintjob_writer.serialize(paintjob))

        assert doc["slots"]["front"] == {
            "colors": ["#7fff"] * 16,
            "pixels": [],
        }

    def test_preserves_stp_bit(self, paintjob_writer):
        paintjob = Paintjob(
            slots={"front": slot_of(value=0x8000)},
        )

        doc = json.loads(paintjob_writer.serialize(paintjob))

        # stp=1, RGB=0: without u16 preservation this would collapse to
        # `#000000` and re-read as value=0 (transparent) — the specific bug
        # this format change fixes.
        assert doc["slots"]["front"]["colors"] == ["#8000"] * 16

    def test_serializes_pixel_region_as_base64(self, paintjob_writer):
        raw = bytes([0x21, 0x43])
        paintjob = Paintjob(
            slots={
                "front": SlotColors(
                    colors=slot_of(value=0x7FFF).colors,
                    pixels=[
                        SlotRegionPixels(
                            vram_x=320, vram_y=128,
                            width=4, height=1,
                            pixels=raw,
                        ),
                    ],
                ),
            },
        )

        doc = json.loads(paintjob_writer.serialize(paintjob))

        region = doc["slots"]["front"]["pixels"][0]
        assert region["vram_x"] == 320
        assert region["vram_y"] == 128
        assert region["width"] == 4
        assert region["height"] == 1
        assert base64.b64decode(region["data"]) == raw

    def test_pixel_region_round_trip(
        self, paintjob_reader, paintjob_writer,
    ):
        raw = bytes([0xAB, 0xCD, 0xEF])
        original = Paintjob(
            slots={
                "front": SlotColors(
                    colors=slot_of(value=0x7FFF).colors,
                    pixels=[
                        SlotRegionPixels(
                            vram_x=100, vram_y=50,
                            width=6, height=1,
                            pixels=raw,
                        ),
                    ],
                ),
            },
        )

        text = paintjob_writer.serialize(original)
        loaded = paintjob_reader.read(text)

        assert loaded.slots["front"].pixels[0].pixels == raw
        assert loaded.slots["front"].pixels[0].vram_x == 100

    def test_round_trip_preserves_colors(
        self, paintjob_reader, paintjob_writer,
    ):
        original = Paintjob(
            name="Round",
            author="Garma",
            slots={
                "front": slot_of(value=0x03EB),
                "back": slot_of(value=0x7C00),
            },
        )

        text = paintjob_writer.serialize(original)
        loaded = paintjob_reader.read(text)

        assert loaded.name == original.name
        assert loaded.author == original.author
        assert loaded.slots["front"].colors[0].value == 0x03EB
        assert loaded.slots["back"].colors[0].value == 0x7C00

    def test_emits_base_character_when_set(self, paintjob_writer):
        paintjob = Paintjob(name="Crash", base_character_id="crash")

        doc = json.loads(paintjob_writer.serialize(paintjob))

        assert doc["base_character_id"] == "crash"

    def test_base_character_round_trip(
        self, paintjob_reader, paintjob_writer,
    ):
        original = Paintjob(
            name="Crash defaults",
            base_character_id="crash",
            slots={"front": slot_of(value=0x7FFF)},
        )

        text = paintjob_writer.serialize(original)
        loaded = paintjob_reader.read(text)

        assert loaded.base_character_id == "crash"
