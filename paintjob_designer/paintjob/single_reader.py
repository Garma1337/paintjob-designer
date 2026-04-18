# coding: utf-8

import json

from paintjob_designer.color.converter import ColorConverter
from paintjob_designer.models import SinglePaintjob, SlotColors


class SinglePaintjobReader:
    """Parses a paintjob JSON file into a `SinglePaintjob`.

    Older schema versions are migrated up to the current shape on load — future
    format changes should plug their upgrade step into `_migrate` rather than
    forcing users to re-author files. Newer-than-supported versions are
    rejected since there's no safe way to downgrade.
    """

    def __init__(self, color_converter: ColorConverter) -> None:
        self._colors = color_converter

    def read(self, data: str | bytes) -> SinglePaintjob:
        if isinstance(data, bytes):
            data = data.decode("utf-8")

        return self._parse(json.loads(data))

    def _parse(self, raw: dict) -> SinglePaintjob:
        if not isinstance(raw, dict):
            raise ValueError("Single-paintjob root must be a JSON object")

        schema_version = int(raw.get("schema_version", SinglePaintjob.SCHEMA_VERSION))
        if schema_version > SinglePaintjob.SCHEMA_VERSION:
            raise ValueError(
                f"Paintjob schema_version {schema_version} is newer than this "
                f"tool supports (max {SinglePaintjob.SCHEMA_VERSION}). "
                "Upgrade Paintjob Designer to open this file."
            )

        raw = self._migrate(raw, schema_version)

        slots_raw = raw.get("slots", {})
        if not isinstance(slots_raw, dict):
            raise ValueError("Single-paintjob 'slots' must be an object")

        slots = {
            str(name): self._parse_slot(name, colors_raw)
            for name, colors_raw in slots_raw.items()
        }

        return SinglePaintjob(
            schema_version=SinglePaintjob.SCHEMA_VERSION,
            name=str(raw.get("name", "")),
            author=str(raw.get("author", "")),
            slots=slots,
        )

    def _migrate(self, raw: dict, from_version: int) -> dict:
        """Walk `raw` up to the current schema version.

        Each step mutates/returns `raw` in place; only the shape-level tweaks
        happen here (renamed keys, moved sections, defaulted fields). Pure
        color-format changes live in `_parse_slot` where the per-color reader
        already handles both legacy 6-digit hex and current 4-digit u16 hex.

        Today this is a no-op since v1 is the only version; the method exists
        so future bumps don't have to re-introduce the migration concept.
        """
        # Future pattern:
        # if from_version < 2:
        #     raw = _v1_to_v2(raw)
        return raw

    def _parse_slot(self, slot_name: str, raw_colors: list) -> SlotColors:
        if not isinstance(raw_colors, list):
            raise ValueError(f"Slot {slot_name!r} colors must be a list")

        if len(raw_colors) != SlotColors.SIZE:
            raise ValueError(
                f"Slot {slot_name!r} must have exactly {SlotColors.SIZE} colors, "
                f"got {len(raw_colors)}"
            )

        return SlotColors(colors=[self._colors.u16_hex_to_psx(h) for h in raw_colors])
