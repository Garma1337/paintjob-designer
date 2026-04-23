# coding: utf-8

import json

from pydantic import ValidationError

from paintjob_designer.models import Skin, SlotColors


class SkinReader:
    """Parses a skin JSON file into a `Skin`."""

    def read(self, data: str | bytes) -> Skin:
        if isinstance(data, bytes):
            data = data.decode("utf-8")

        raw = json.loads(data)
        self._validate_shape(raw)

        # Force the in-memory object's `schema_version` to current — same
        # pattern as PaintjobReader. If the on-disk version were outright
        # incompatible the shape check above would already reject.
        raw["schema_version"] = Skin.SCHEMA_VERSION

        try:
            return Skin.model_validate(raw)
        except ValidationError as exc:
            raise ValueError(f"Skin is not valid: {exc}") from exc

    def _validate_shape(self, raw: object) -> None:
        if not isinstance(raw, dict):
            raise ValueError("Skin root must be a JSON object")

        schema_version = int(raw.get("schema_version", Skin.SCHEMA_VERSION))
        if schema_version > Skin.SCHEMA_VERSION:
            raise ValueError(
                f"Skin schema_version {schema_version} is newer than this "
                f"tool supports (max {Skin.SCHEMA_VERSION}). "
                "Upgrade Paintjob Designer to open this file."
            )

        character_id = raw.get("character_id", "")
        if not character_id:
            raise ValueError(
                "Skin 'character_id' is required — skins are bound to one "
                "specific character"
            )

        slots_raw = raw.get("slots", {})
        if not isinstance(slots_raw, dict):
            raise ValueError("Skin 'slots' must be an object")

        for slot_name, slot_raw in slots_raw.items():
            if not isinstance(slot_raw, dict):
                raise ValueError(
                    f"Slot {slot_name!r} must be an object with 'colors' "
                    f"(and optional 'pixels')"
                )

            colors_raw = slot_raw.get("colors")
            if colors_raw is None or len(colors_raw) != SlotColors.SIZE:
                raise ValueError(
                    f"Slot {slot_name!r} must have exactly {SlotColors.SIZE} "
                    f"colors, got {len(colors_raw) if colors_raw is not None else 0}"
                )

        vertex_overrides_raw = raw.get("vertex_overrides", {})
        if not isinstance(vertex_overrides_raw, dict):
            raise ValueError("Skin 'vertex_overrides' must be an object")
