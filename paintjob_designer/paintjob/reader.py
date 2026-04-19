# coding: utf-8

import json

from paintjob_designer.color.converter import ColorConverter
from paintjob_designer.models import Paintjob, SlotColors


class PaintjobReader:
    """Parses a paintjob JSON file into a `Paintjob`.

    Each file is one paintjob — a character-agnostic 8-slot palette with
    metadata. The library-level format (N paintjobs in a directory, or one
    combined file) lives above this reader; this class handles the unit.
    """

    def __init__(self, color_converter: ColorConverter) -> None:
        self._colors = color_converter

    def read(self, data: str | bytes) -> Paintjob:
        if isinstance(data, bytes):
            data = data.decode("utf-8")

        return self._parse(json.loads(data))

    def _parse(self, raw: dict) -> Paintjob:
        if not isinstance(raw, dict):
            raise ValueError("Paintjob root must be a JSON object")

        schema_version = int(raw.get("schema_version", Paintjob.SCHEMA_VERSION))
        if schema_version > Paintjob.SCHEMA_VERSION:
            raise ValueError(
                f"Paintjob schema_version {schema_version} is newer than this "
                f"tool supports (max {Paintjob.SCHEMA_VERSION}). "
                "Upgrade Paintjob Designer to open this file."
            )

        slots_raw = raw.get("slots", {})
        if not isinstance(slots_raw, dict):
            raise ValueError("Paintjob 'slots' must be an object")

        slots = {
            str(name): self._parse_slot(name, colors_raw)
            for name, colors_raw in slots_raw.items()
        }

        base_character_id = raw.get("base_character_id")

        return Paintjob(
            schema_version=Paintjob.SCHEMA_VERSION,
            name=str(raw.get("name", "")),
            author=str(raw.get("author", "")),
            base_character_id=(
                str(base_character_id) if base_character_id else None
            ),
            slots=slots,
        )

    def _parse_slot(self, slot_name: str, raw_colors: list) -> SlotColors:
        if not isinstance(raw_colors, list):
            raise ValueError(f"Slot {slot_name!r} colors must be a list")

        if len(raw_colors) != SlotColors.SIZE:
            raise ValueError(
                f"Slot {slot_name!r} must have exactly {SlotColors.SIZE} colors, "
                f"got {len(raw_colors)}"
            )

        return SlotColors(colors=[self._colors.u16_hex_to_psx(h) for h in raw_colors])
