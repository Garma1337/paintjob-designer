# coding: utf-8

import struct
from dataclasses import dataclass
from pathlib import Path

from paintjob_designer.models import Profile, SlotColors


# Canonical slot order used by the in-game `Texture` union. Every pointer
# table in PAINTALL.BIN indexes by this position, so the profile's slot list
# is reshuffled into this order at export time regardless of authoring
# sequence.
_CANONICAL_SLOT_ORDER = (
    "front", "back", "floor", "brown",
    "motorside", "motortop", "bridge", "exhaust",
)

_POINTERS_PER_TEXTURE = len(_CANONICAL_SLOT_ORDER)     # 8
_POINTER_BYTES = 4
_TEXTURE_BYTES = _POINTERS_PER_TEXTURE * _POINTER_BYTES   # 32 — one `Texture` union

_COLORS_PER_SLOT = 16
_BYTES_PER_COLOR = 2
_CLUT_BYTES = _COLORS_PER_SLOT * _BYTES_PER_COLOR         # 32 — one 4bpp CLUT payload

# PSX RECT: four little-endian shorts (x, y, w, h). For paintjob CLUTs the
# width is always 16 u16-pixels (16 colors packed as one VRAM scanline) and
# height is always 1. Only (x, y) varies per character/slot.
_RECT_BYTES = 8
_CLUT_RECT_WIDTH = 16
_CLUT_RECT_HEIGHT = 1

# PS1 RAM address the vanilla CTR loads PAINTALL.BIN at —
# see `LOAD_XnfFile("\\PAINTALL.BIN;1", (void*)0x801CE000, 0)`. The pointer
# tables in the file are absolute: after load, the game casts the raw buffer
# to `TexData*` and dereferences pointers directly, so we have to pre-compute
# every pointer as `_LOAD_ADDR + byte_offset_within_file`.
_LOAD_ADDR = 0x801CE000


@dataclass
class _Layout:
    """Precomputed byte offsets of every region within the PAINTALL.BIN buffer.

    Three pointer tables up front (paintjob CLUTs + two character-indexed
    RECT tables), then the payloads they reference. Pointer tables have
    different sizes because the game's `TexData` struct keeps paintjob
    count and character count independent — e.g. Saphi has 16 paintjobs
    shared across 15 characters.
    """

    num_paintjobs: int
    num_characters: int
    colors_table_offset: int
    menu_pos_table_offset: int
    race_pos_table_offset: int
    clut_data_offset: int
    menu_rect_data_offset: int
    race_rect_data_offset: int
    total_size: int


class BinaryExporter:
    """Writes a PAINTALL.BIN file targeting a profile.

    PAINTALL.BIN is loaded at a fixed PS1 RAM address and cast directly to
    a `TexData` struct:

        typedef struct {
            Texture colors[N];         // CLUT pointers — one entry per paintjob
            Texture colorsMenuPos[M];  // RECT pointers — menu-screen VRAM positions per character
            Texture colorsRacePos[M];  // RECT pointers — in-race VRAM positions per character
        } TexData;

    where `Texture` is a union of 8 `void*` (one per slot: front/back/floor/
    brown/motorside/motortop/bridge/exhaust). The exporter lays out the
    three pointer tables + the CLUT and RECT payloads into one contiguous
    buffer and fixes up each pointer to the absolute PS1 address it'll
    resolve to after load.

    The paintjob count `N` comes from `profile.paintjob_slots` (which
    must match the caller-supplied `paintjob_colors` length); the
    character count `M` comes from `profile.characters`. They're
    independent — any character can wear any paintjob at runtime.
    """

    CANONICAL_SLOT_ORDER = _CANONICAL_SLOT_ORDER
    SLOT_COUNT = _POINTERS_PER_TEXTURE
    LOAD_ADDR = _LOAD_ADDR

    def export(
        self,
        paintjob_colors: list[dict[str, SlotColors]],
        profile: Profile,
        dest: Path,
    ) -> None:
        """Write PAINTALL.BIN to `dest`.

        `paintjob_colors[i]` is the fully-populated 8-slot CLUT map for
        library paintjob `i` — one `SlotColors` per canonical slot name.
        The caller (typically the main window) backfills unedited slots
        from the home character's VRAM before handing them here so the
        exporter stays pure (no ISO / VRAM I/O).

        Raises `ValueError` listing every missing piece of data when the
        library size doesn't match `profile.paintjob_slots`, a paintjob
        is missing a canonical slot, or a character is missing its
        canonical slots / `clut_menu` coordinates. Produces no output
        on validation failure.
        """
        self._validate(paintjob_colors, profile)

        layout = self._compute_layout(
            num_paintjobs=len(paintjob_colors),
            num_characters=len(profile.characters),
        )
        buffer = bytearray(layout.total_size)

        self._write_paintjob_cluts(buffer, layout, paintjob_colors)
        self._write_character_rects(buffer, layout, profile)

        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(bytes(buffer))

    def _write_paintjob_cluts(
        self,
        buffer: bytearray,
        layout: _Layout,
        paintjob_colors: list[dict[str, SlotColors]],
    ) -> None:
        """Emit the `colors[N]` pointer table + the 32-byte CLUT payloads it points at."""
        for paintjob_index, slot_colors in enumerate(paintjob_colors):
            for slot_index, slot_name in enumerate(_CANONICAL_SLOT_ORDER):
                clut_off = (
                    layout.clut_data_offset
                    + (paintjob_index * self.SLOT_COUNT + slot_index) * _CLUT_BYTES
                )
                self._write_clut(buffer, clut_off, slot_colors.get(slot_name))

                ptr_off = (
                    layout.colors_table_offset
                    + paintjob_index * _TEXTURE_BYTES
                    + slot_index * _POINTER_BYTES
                )
                struct.pack_into("<I", buffer, ptr_off, _LOAD_ADDR + clut_off)

    def _write_character_rects(
        self,
        buffer: bytearray,
        layout: _Layout,
        profile: Profile,
    ) -> None:
        """Emit both per-character RECT tables + the RECT payloads they reference."""
        for char_index, character in enumerate(profile.characters):
            slots_by_name = {slot.name: slot for slot in character.slots}
            for slot_index, slot_name in enumerate(_CANONICAL_SLOT_ORDER):
                slot = slots_by_name[slot_name]   # presence checked in _validate

                menu_off = (
                    layout.menu_rect_data_offset
                    + (char_index * self.SLOT_COUNT + slot_index) * _RECT_BYTES
                )
                race_off = (
                    layout.race_rect_data_offset
                    + (char_index * self.SLOT_COUNT + slot_index) * _RECT_BYTES
                )
                self._write_rect(buffer, menu_off, slot.clut_menu.x, slot.clut_menu.y)
                self._write_rect(buffer, race_off, slot.clut.x, slot.clut.y)

                menu_ptr_off = (
                    layout.menu_pos_table_offset
                    + char_index * _TEXTURE_BYTES
                    + slot_index * _POINTER_BYTES
                )
                race_ptr_off = (
                    layout.race_pos_table_offset
                    + char_index * _TEXTURE_BYTES
                    + slot_index * _POINTER_BYTES
                )
                struct.pack_into("<I", buffer, menu_ptr_off, _LOAD_ADDR + menu_off)
                struct.pack_into("<I", buffer, race_ptr_off, _LOAD_ADDR + race_off)

    def _compute_layout(
        self, num_paintjobs: int, num_characters: int,
    ) -> _Layout:
        paintjob_table_bytes = num_paintjobs * _TEXTURE_BYTES
        character_table_bytes = num_characters * _TEXTURE_BYTES
        clut_bytes = num_paintjobs * self.SLOT_COUNT * _CLUT_BYTES
        rect_bytes = num_characters * self.SLOT_COUNT * _RECT_BYTES

        colors_table_offset = 0
        menu_pos_table_offset = colors_table_offset + paintjob_table_bytes
        race_pos_table_offset = menu_pos_table_offset + character_table_bytes
        clut_data_offset = race_pos_table_offset + character_table_bytes
        menu_rect_data_offset = clut_data_offset + clut_bytes
        race_rect_data_offset = menu_rect_data_offset + rect_bytes
        total_size = race_rect_data_offset + rect_bytes

        return _Layout(
            num_paintjobs=num_paintjobs,
            num_characters=num_characters,
            colors_table_offset=colors_table_offset,
            menu_pos_table_offset=menu_pos_table_offset,
            race_pos_table_offset=race_pos_table_offset,
            clut_data_offset=clut_data_offset,
            menu_rect_data_offset=menu_rect_data_offset,
            race_rect_data_offset=race_rect_data_offset,
            total_size=total_size,
        )

    def _validate(
        self,
        paintjob_colors: list[dict[str, SlotColors]],
        profile: Profile,
    ) -> None:
        """Raise a clear error listing every missing piece of profile / library data.

        Checking up front (rather than discovering gaps mid-export) lets
        the caller surface a single actionable message instead of a
        half-written PAINTALL.BIN + one cryptic traceback per missing
        slot.
        """
        problems: list[str] = []

        num_paintjobs = len(paintjob_colors)
        num_declared = len(profile.paintjob_slots)
        if num_paintjobs != num_declared:
            problems.append(
                f"library has {num_paintjobs} paintjob(s) but "
                f"profile.paintjob_slots declares {num_declared} — the "
                f"counts must match"
            )

        for i, slots in enumerate(paintjob_colors):
            for slot_name in _CANONICAL_SLOT_ORDER:
                if slot_name not in slots:
                    problems.append(
                        f"paintjob {i} is missing slot '{slot_name}'"
                    )

        for character in profile.characters:
            slots_by_name = {slot.name: slot for slot in character.slots}

            for slot_name in _CANONICAL_SLOT_ORDER:
                slot = slots_by_name.get(slot_name)
                if slot is None:
                    problems.append(
                        f"character '{character.id}' is missing slot '{slot_name}'"
                    )
                    continue

                if slot.clut_menu is None:
                    problems.append(
                        f"character '{character.id}' slot '{slot_name}' has "
                        f"no clut_menu coord — required for PAINTALL.BIN"
                    )

        if problems:
            raise ValueError(
                "Profile / library is not ready for PAINTALL.BIN export:\n  "
                + "\n  ".join(problems)
            )

    def _write_clut(
        self,
        buffer: bytearray,
        offset: int,
        colors: SlotColors | None,
    ) -> None:
        # Pad missing colors with 0x0000 (PSX transparent-index convention)
        # — a half-filled slot still occupies its 32 bytes so later offsets
        # stay predictable.
        color_values: list[int] = []
        if colors is not None:
            color_values = [c.value for c in colors.colors]

        for i in range(_COLORS_PER_SLOT):
            value = color_values[i] if i < len(color_values) else 0
            struct.pack_into(
                "<H", buffer, offset + i * _BYTES_PER_COLOR, value & 0xFFFF,
            )

    def _write_rect(
        self, buffer: bytearray, offset: int, x: int, y: int,
    ) -> None:
        struct.pack_into(
            "<hhhh", buffer, offset,
            x & 0xFFFF, y & 0xFFFF,
            _CLUT_RECT_WIDTH, _CLUT_RECT_HEIGHT,
        )
