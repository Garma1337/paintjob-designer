# coding: utf-8

import struct

from paintjob_designer.exporters.binary_exporter import BinaryExporter
from paintjob_designer.models import (
    CharacterPaintjob,
    CharacterProfile,
    Paintjob,
    Profile,
    PsxColor,
    SlotColors,
)
from tests.conftest import slot_of as _solid_slot

_SLOT_ORDER = (
    "front", "back", "floor", "brown",
    "motorside", "motortop", "bridge", "exhaust",
)


def _profile(character_ids: list[str]) -> Profile:
    return Profile(
        id="vanilla-ntsc-u",
        characters=[
            CharacterProfile(id=cid, slots=[]) for cid in character_ids
        ],
    )


def _read_u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


class TestOutputSize:

    def test_one_paintjob_is_256_bytes(self, binary_exporter, tmp_path):
        paintjob = Paintjob(characters={
            "crash": CharacterPaintjob(slots={s: _solid_slot(0) for s in _SLOT_ORDER}),
        })
        dest = tmp_path / "paintjobs.bin"

        binary_exporter.export(paintjob, _profile(["crash"]), dest)

        assert dest.stat().st_size == 256
        assert BinaryExporter.BYTES_PER_PAINTJOB == 256

    def test_size_scales_with_profile_character_count(self, binary_exporter, tmp_path):
        paintjob = Paintjob()
        dest = tmp_path / "paintjobs.bin"

        binary_exporter.export(paintjob, _profile(["a", "b", "c"]), dest)

        assert dest.stat().st_size == 3 * 256


class TestLayout:

    def test_paintjob_order_matches_profile_character_order(
        self, binary_exporter, tmp_path,
    ):
        # Distinct marker values per character so we can spot misplacement.
        paintjob = Paintjob(characters={
            "crash":  CharacterPaintjob(slots={s: _solid_slot(0x1111) for s in _SLOT_ORDER}),
            "cortex": CharacterPaintjob(slots={s: _solid_slot(0x2222) for s in _SLOT_ORDER}),
        })
        dest = tmp_path / "paintjobs.bin"

        binary_exporter.export(paintjob, _profile(["crash", "cortex"]), dest)

        data = dest.read_bytes()
        assert _read_u16(data, 0) == 0x1111
        assert _read_u16(data, 256) == 0x2222

    def test_slot_order_is_canonical(self, binary_exporter, tmp_path):
        # Each slot gets a distinct marker so we can verify they land in the
        # canonical `front, back, floor, ...` layout regardless of dict order.
        slots = {
            "exhaust":   _solid_slot(0xAAA1),
            "front":     _solid_slot(0xAAA2),
            "bridge":    _solid_slot(0xAAA3),
            "back":      _solid_slot(0xAAA4),
            "motorside": _solid_slot(0xAAA5),
            "brown":     _solid_slot(0xAAA6),
            "motortop":  _solid_slot(0xAAA7),
            "floor":     _solid_slot(0xAAA8),
        }
        paintjob = Paintjob(characters={"crash": CharacterPaintjob(slots=slots)})
        dest = tmp_path / "paintjobs.bin"

        binary_exporter.export(paintjob, _profile(["crash"]), dest)

        data = dest.read_bytes()
        # Each slot's first color sits at slot_index * 32.
        expected_order = [0xAAA2, 0xAAA4, 0xAAA8, 0xAAA6, 0xAAA5, 0xAAA7, 0xAAA3, 0xAAA1]
        for i, expected in enumerate(expected_order):
            assert _read_u16(data, i * 32) == expected, f"slot {i}: {_SLOT_ORDER[i]}"

    def test_sixteen_colors_per_slot_in_order(self, binary_exporter, tmp_path):
        # A slot whose 16 colors are 0..15 should appear verbatim.
        slot = SlotColors(colors=[PsxColor(value=i) for i in range(16)])
        paintjob = Paintjob(characters={
            "crash": CharacterPaintjob(slots={"front": slot}),
        })
        dest = tmp_path / "paintjobs.bin"

        binary_exporter.export(paintjob, _profile(["crash"]), dest)

        data = dest.read_bytes()
        for i in range(16):
            assert _read_u16(data, i * 2) == i

    def test_missing_character_zero_fills_its_paintjob(self, binary_exporter, tmp_path):
        # Only `cortex` has data; `crash` is absent in the paintjob dict.
        paintjob = Paintjob(characters={
            "cortex": CharacterPaintjob(slots={s: _solid_slot(0x7FFF) for s in _SLOT_ORDER}),
        })
        dest = tmp_path / "paintjobs.bin"

        binary_exporter.export(paintjob, _profile(["crash", "cortex"]), dest)

        data = dest.read_bytes()
        # First 256 bytes (crash) entirely zero.
        assert data[:256] == b"\x00" * 256
        # Second 256 bytes (cortex) carry the 0x7FFF marker.
        assert _read_u16(data, 256) == 0x7FFF

    def test_missing_slot_zero_fills_its_32_bytes(self, binary_exporter, tmp_path):
        # Only `front` populated; other slots fall back to zero.
        paintjob = Paintjob(characters={
            "crash": CharacterPaintjob(slots={"front": _solid_slot(0x1234)}),
        })
        dest = tmp_path / "paintjobs.bin"

        binary_exporter.export(paintjob, _profile(["crash"]), dest)

        data = dest.read_bytes()
        # front occupies bytes 0..31.
        assert _read_u16(data, 0) == 0x1234
        # back through exhaust all zeroed.
        assert data[32:256] == b"\x00" * (256 - 32)


class TestEmptyProfile:

    def test_empty_profile_writes_empty_file(self, binary_exporter, tmp_path):
        dest = tmp_path / "paintjobs.bin"

        binary_exporter.export(Paintjob(), _profile([]), dest)

        assert dest.exists()
        assert dest.stat().st_size == 0


class TestParentDirCreation:

    def test_creates_missing_parent_directory(self, binary_exporter, tmp_path):
        dest = tmp_path / "deeply" / "nested" / "paintjobs.bin"

        binary_exporter.export(Paintjob(), _profile(["crash"]), dest)

        assert dest.exists()
