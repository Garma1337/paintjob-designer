# coding: utf-8

import struct
from pathlib import Path

from paintjob_designer.models import Paintjob, Profile, PsxColor

# Canonical 8-slot order used across CTR kart paintjobs.
_CANONICAL_SLOT_ORDER = (
    "front", "back", "floor", "brown",
    "motorside", "motortop", "bridge", "exhaust",
)

_COLORS_PER_SLOT = 16
_BYTES_PER_COLOR = 2                                          # PSX u16 little-endian
_SLOT_BYTES = _COLORS_PER_SLOT * _BYTES_PER_COLOR             # 32
_PAINTJOB_BYTES = len(_CANONICAL_SLOT_ORDER) * _SLOT_BYTES    # 256


class BinaryExporter:
    """Writes a compact binary dump of paintjob CLUT colors.

    The output is the color data itself, in profile character order, with no
    metadata, pointers, or layout specific to any one mod. For each paintjob
    the 8 slots are written in canonical order
    (front, back, floor, brown, motorside, motortop, bridge, exhaust); each
    slot is 16 PSX 15-bit colors as little-endian u16s. That's 256 bytes per
    paintjob, `N × 256` bytes total for `N` characters in the profile.

    The consuming tool knows where each CLUT should land in the target ISO —
    those positions are fixed for base CTR NTSC-U and don't travel with the
    binary. Any patcher that wants to write these CLUTs into the ISO can read
    the paintjob-order/slot-order convention out of the profile JSON and seek
    to its own known offsets.
    """

    BYTES_PER_PAINTJOB = _PAINTJOB_BYTES
    SLOT_ORDER = _CANONICAL_SLOT_ORDER

    def export(self, paintjob: Paintjob, profile: Profile, dest: Path) -> None:
        character_order = [c.id for c in profile.characters]
        buffer = bytearray(len(character_order) * _PAINTJOB_BYTES)

        for paintjob_index, character_id in enumerate(character_order):
            character_paintjob = paintjob.characters.get(character_id)
            base = paintjob_index * _PAINTJOB_BYTES
            for slot_index, slot_name in enumerate(_CANONICAL_SLOT_ORDER):
                slot_offset = base + slot_index * _SLOT_BYTES
                colors = self._colors_for(character_paintjob, slot_name)
                self._write_slot(buffer, slot_offset, colors)

        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(bytes(buffer))

    def _colors_for(self, character_paintjob, slot_name: str) -> list[PsxColor]:
        if character_paintjob is None:
            return []

        slot = character_paintjob.slots.get(slot_name)
        if slot is None:
            return []

        return list(slot.colors)

    def _write_slot(
        self,
        buffer: bytearray,
        offset: int,
        colors: list[PsxColor],
    ) -> None:
        # Pad missing colors with 0x0000 (PSX transparent-index convention) so
        # a half-filled slot still occupies its 32 bytes and later paintjobs'
        # offsets stay predictable.
        for i in range(_COLORS_PER_SLOT):
            value = colors[i].value if i < len(colors) else 0
            struct.pack_into("<H", buffer, offset + i * 2, value & 0xFFFF)
