# coding: utf-8

import json

from paintjob_designer.models import Paintjob
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

    def test_serializes_slots_as_hex_lists(self, paintjob_writer):
        paintjob = Paintjob(
            name="White",
            slots={"front": slot_of(value=0x7FFF)},
        )

        doc = json.loads(paintjob_writer.serialize(paintjob))

        assert doc["slots"]["front"] == ["#7fff"] * 16

    def test_preserves_stp_bit(self, paintjob_writer):
        paintjob = Paintjob(
            slots={"front": slot_of(value=0x8000)},
        )

        doc = json.loads(paintjob_writer.serialize(paintjob))

        # stp=1, RGB=0: without u16 preservation this would collapse to
        # `#000000` and re-read as value=0 (transparent) — the specific bug
        # this format change fixes.
        assert doc["slots"]["front"] == ["#8000"] * 16

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
