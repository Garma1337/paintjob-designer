# coding: utf-8

import json

from paintjob_designer.models import SinglePaintjob
from tests.conftest import slot_of


class TestSinglePaintjobWriter:

    def test_serializes_metadata(self, single_paintjob_writer):
        paintjob = SinglePaintjob(name="Lime", author="Garma")

        doc = json.loads(single_paintjob_writer.serialize(paintjob))

        assert doc["schema_version"] == 1
        assert doc["name"] == "Lime"
        assert doc["author"] == "Garma"
        assert doc["slots"] == {}

    def test_serializes_slots_as_hex_lists(self, single_paintjob_writer):
        paintjob = SinglePaintjob(
            name="White",
            slots={"front": slot_of(value=0x7FFF)},
        )

        doc = json.loads(single_paintjob_writer.serialize(paintjob))

        assert doc["slots"]["front"] == ["#7fff"] * 16

    def test_preserves_stp_bit(self, single_paintjob_writer):
        paintjob = SinglePaintjob(
            slots={"front": slot_of(value=0x8000)},
        )

        doc = json.loads(single_paintjob_writer.serialize(paintjob))

        # stp=1, RGB=0: without u16 preservation this would collapse to
        # `#000000` and re-read as value=0 (transparent) — the specific bug
        # this format change fixes.
        assert doc["slots"]["front"] == ["#8000"] * 16

    def test_round_trip_preserves_colors(
        self, single_paintjob_reader, single_paintjob_writer,
    ):
        original = SinglePaintjob(
            name="Round",
            author="Garma",
            slots={
                "front": slot_of(value=0x03EB),
                "back": slot_of(value=0x7C00),
            },
        )

        text = single_paintjob_writer.serialize(original)
        loaded = single_paintjob_reader.read(text)

        assert loaded.name == original.name
        assert loaded.author == original.author
        assert loaded.slots["front"].colors[0].value == 0x03EB
        assert loaded.slots["back"].colors[0].value == 0x7C00
