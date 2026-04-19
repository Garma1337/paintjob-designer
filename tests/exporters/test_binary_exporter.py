# coding: utf-8

import struct

import pytest

from paintjob_designer.exporters.binary_exporter import BinaryExporter
from paintjob_designer.models import (
    CharacterProfile,
    ClutCoord,
    PaintjobSlotProfile,
    Profile,
    PsxColor,
    SlotColors,
    SlotProfile,
)

_SLOT_ORDER = BinaryExporter.CANONICAL_SLOT_ORDER
_LOAD_ADDR = BinaryExporter.LOAD_ADDR
_TEXTURE_BYTES = 32    # 8 pointers × 4 bytes
_CLUT_BYTES = 32
_RECT_BYTES = 8


def _full_slot(value: int) -> SlotColors:
    return SlotColors(colors=[PsxColor(value=value) for _ in range(16)])


def _character_profile(character_id: str, clut_offset: int = 0) -> CharacterProfile:
    """Build a minimal valid CharacterProfile: all 8 canonical slots, each
    with its own `clut` and `clut_menu` so the exporter's validator
    passes. `clut_offset` spreads distinct (x, y) pairs across characters
    so tests can identify which RECT came from which character.
    """
    return CharacterProfile(
        id=character_id,
        slots=[
            SlotProfile(
                name=name,
                clut=ClutCoord(x=(i * 16) + clut_offset, y=100 + i),
                clut_menu=ClutCoord(x=(i * 16) + clut_offset + 8, y=200 + i),
            )
            for i, name in enumerate(_SLOT_ORDER)
        ],
    )


def _profile(character_ids: list[str], paintjob_count: int | None = None) -> Profile:
    """Build a Profile with `paintjob_slots` sized to match the library.

    When `paintjob_count` is None it defaults to `len(character_ids)` — the
    "every character has one home paintjob" layout (vanilla CTR shape).
    Pass a different value to exercise the N ≠ M path.
    """
    if paintjob_count is None:
        paintjob_count = len(character_ids)

    return Profile(
        characters=[_character_profile(cid, clut_offset=i * 256)
                    for i, cid in enumerate(character_ids)],
        paintjob_slots=[
            PaintjobSlotProfile(name=f"slot_{i}")
            for i in range(paintjob_count)
        ],
    )


def _full_paintjob(marker: int) -> dict[str, SlotColors]:
    return {name: _full_slot(marker) for name in _SLOT_ORDER}


def _read_u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def _read_u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def _read_rect(data: bytes, offset: int) -> tuple[int, int, int, int]:
    return struct.unpack_from("<hhhh", data, offset)


class TestLayoutSize:

    def test_empty_library_and_profile_writes_empty_file(
        self, binary_exporter, tmp_path,
    ):
        dest = tmp_path / "PAINTALL.bin"

        binary_exporter.export([], Profile(), dest)

        assert dest.exists()
        assert dest.stat().st_size == 0

    def test_file_size_matches_layout_formula(self, binary_exporter, tmp_path):
        # 3 characters × 1 paintjob each (N=M=3):
        #   pointer tables:   3 × 32 * 3 = 288 bytes
        #   CLUT payloads:    3 × 8 × 32 = 768 bytes
        #   2 RECT blobs:     3 × 8 × 8 × 2 = 384 bytes
        #   total = 1440
        profile = _profile(["a", "b", "c"])
        paintjob_colors = [_full_paintjob(0) for _ in range(3)]
        dest = tmp_path / "PAINTALL.bin"

        binary_exporter.export(paintjob_colors, profile, dest)

        assert dest.stat().st_size == 1440

    def test_paintjob_and_character_counts_can_differ(
        self, binary_exporter, tmp_path,
    ):
        # 2 characters, 3 paintjobs — the Saphi shape where some paintjobs
        # are shared across characters.
        profile = _profile(["a", "b"], paintjob_count=3)
        paintjob_colors = [_full_paintjob(i) for i in range(3)]
        dest = tmp_path / "PAINTALL.bin"

        binary_exporter.export(paintjob_colors, profile, dest)

        # 3 × 32 + 2 × 2 × 32 + 3 × 8 × 32 + 2 × 2 × 8 × 8
        # = 96 + 128 + 768 + 256 = 1248
        assert dest.stat().st_size == 1248


class TestPointerTables:

    def test_colors_pointer_resolves_to_clut_payload(
        self, binary_exporter, tmp_path,
    ):
        profile = _profile(["crash"])
        paintjob_colors = [_full_paintjob(0xCAFE)]
        dest = tmp_path / "PAINTALL.bin"

        binary_exporter.export(paintjob_colors, profile, dest)

        data = dest.read_bytes()

        # Slot 0 of paintjob 0's colors-table entry → first CLUT payload.
        colors_table_slot0 = 0
        clut_ptr = _read_u32(data, colors_table_slot0)
        clut_offset = clut_ptr - _LOAD_ADDR
        assert 0 <= clut_offset < len(data)
        assert _read_u16(data, clut_offset) == 0xCAFE

    def test_menu_and_race_pointers_resolve_to_distinct_rects(
        self, binary_exporter, tmp_path,
    ):
        profile = _profile(["crash"])
        paintjob_colors = [_full_paintjob(0)]
        dest = tmp_path / "PAINTALL.bin"

        binary_exporter.export(paintjob_colors, profile, dest)

        data = dest.read_bytes()
        num_paintjobs = 1
        num_characters = 1

        menu_table_base = num_paintjobs * _TEXTURE_BYTES
        race_table_base = menu_table_base + num_characters * _TEXTURE_BYTES

        menu_ptr = _read_u32(data, menu_table_base)
        race_ptr = _read_u32(data, race_table_base)
        assert menu_ptr != race_ptr

        menu_rect = _read_rect(data, menu_ptr - _LOAD_ADDR)
        race_rect = _read_rect(data, race_ptr - _LOAD_ADDR)

        # Slot 0 of character crash: race.x=0, race.y=100, menu.x=8, menu.y=200.
        assert race_rect == (0, 100, 16, 1)
        assert menu_rect == (8, 200, 16, 1)


class TestPaintjobOrder:

    def test_clut_data_is_in_library_order(self, binary_exporter, tmp_path):
        profile = _profile(["a", "b", "c"])
        paintjob_colors = [
            _full_paintjob(0xAAAA),
            _full_paintjob(0xBBBB),
            _full_paintjob(0xCCCC),
        ]
        dest = tmp_path / "PAINTALL.bin"

        binary_exporter.export(paintjob_colors, profile, dest)

        data = dest.read_bytes()
        num_paintjobs = 3
        num_characters = 3
        clut_base = (
            num_paintjobs * _TEXTURE_BYTES          # colors[] table
            + 2 * num_characters * _TEXTURE_BYTES   # menu + race tables
        )

        bytes_per_paintjob_clut_block = BinaryExporter.SLOT_COUNT * _CLUT_BYTES
        assert _read_u16(data, clut_base + 0 * bytes_per_paintjob_clut_block) == 0xAAAA
        assert _read_u16(data, clut_base + 1 * bytes_per_paintjob_clut_block) == 0xBBBB
        assert _read_u16(data, clut_base + 2 * bytes_per_paintjob_clut_block) == 0xCCCC


class TestSlotOrder:

    def test_clut_data_is_in_canonical_slot_order(
        self, binary_exporter, tmp_path,
    ):
        profile = _profile(["crash"])

        # Authoring order shuffled; exporter should re-align to canonical.
        markers = {name: 0xA000 + i for i, name in enumerate(_SLOT_ORDER)}
        paintjob_colors = [{
            name: _full_slot(markers[name])
            for name in reversed(_SLOT_ORDER)
        }]
        dest = tmp_path / "PAINTALL.bin"

        binary_exporter.export(paintjob_colors, profile, dest)

        data = dest.read_bytes()
        num_paintjobs = 1
        num_characters = 1
        clut_base = (
            num_paintjobs * _TEXTURE_BYTES
            + 2 * num_characters * _TEXTURE_BYTES
        )

        for slot_index, name in enumerate(_SLOT_ORDER):
            first_color_offset = clut_base + slot_index * _CLUT_BYTES
            assert _read_u16(data, first_color_offset) == markers[name], (
                f"slot {slot_index} ({name}) in wrong position"
            )


class TestValidation:

    def test_library_count_must_match_paintjob_slots(
        self, binary_exporter, tmp_path,
    ):
        # Profile declares 2 paintjob slots, library only provides 1.
        profile = _profile(["a", "b"], paintjob_count=2)
        paintjob_colors = [_full_paintjob(0)]

        with pytest.raises(ValueError) as exc_info:
            binary_exporter.export(
                paintjob_colors, profile, tmp_path / "PAINTALL.bin",
            )

        message = str(exc_info.value)
        assert "1 paintjob" in message
        assert "declares 2" in message

    def test_missing_canonical_slot_on_paintjob_raises(
        self, binary_exporter, tmp_path,
    ):
        profile = _profile(["crash"])
        # Library paintjob is missing 'back'.
        partial = _full_paintjob(0)
        del partial["back"]

        with pytest.raises(ValueError) as exc_info:
            binary_exporter.export(
                [partial], profile, tmp_path / "PAINTALL.bin",
            )

        assert "paintjob 0" in str(exc_info.value)
        assert "back" in str(exc_info.value)

    def test_missing_canonical_slot_on_character_raises(
        self, binary_exporter, tmp_path,
    ):
        character = CharacterProfile(
            id="crash",
            slots=[SlotProfile(
                name="front",
                clut=ClutCoord(x=0, y=0),
                clut_menu=ClutCoord(x=0, y=0),
            )],
        )
        profile = Profile(
            characters=[character],
            paintjob_slots=[PaintjobSlotProfile()],
        )
        paintjob_colors = [_full_paintjob(0)]

        with pytest.raises(ValueError) as exc_info:
            binary_exporter.export(
                paintjob_colors, profile, tmp_path / "PAINTALL.bin",
            )

        assert "back" in str(exc_info.value)
        assert "crash" in str(exc_info.value)

    def test_missing_clut_menu_raises(self, binary_exporter, tmp_path):
        character = CharacterProfile(
            id="crash",
            slots=[SlotProfile(name=name, clut=ClutCoord(x=0, y=0))
                   for name in _SLOT_ORDER],
        )
        profile = Profile(
            characters=[character],
            paintjob_slots=[PaintjobSlotProfile()],
        )
        paintjob_colors = [_full_paintjob(0)]

        with pytest.raises(ValueError) as exc_info:
            binary_exporter.export(
                paintjob_colors, profile, tmp_path / "PAINTALL.bin",
            )

        assert "clut_menu" in str(exc_info.value)


class TestSixteenColors:

    def test_slot_writes_all_sixteen_colors_in_order(
        self, binary_exporter, tmp_path,
    ):
        profile = _profile(["crash"])
        ascending = SlotColors(colors=[PsxColor(value=i) for i in range(16)])
        paintjob_colors = [{name: ascending for name in _SLOT_ORDER}]
        dest = tmp_path / "PAINTALL.bin"

        binary_exporter.export(paintjob_colors, profile, dest)

        data = dest.read_bytes()
        num_paintjobs = 1
        num_characters = 1
        clut_base = (
            num_paintjobs * _TEXTURE_BYTES
            + 2 * num_characters * _TEXTURE_BYTES
        )

        for i in range(16):
            assert _read_u16(data, clut_base + i * 2) == i


class TestParentDirCreation:

    def test_creates_missing_parent_directory(self, binary_exporter, tmp_path):
        dest = tmp_path / "deeply" / "nested" / "PAINTALL.bin"

        binary_exporter.export([], Profile(), dest)

        assert dest.exists()
