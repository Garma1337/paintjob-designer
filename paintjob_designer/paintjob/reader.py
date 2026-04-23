# coding: utf-8

import json

from pydantic import ValidationError

from paintjob_designer.models import Paintjob, SlotColors
from paintjob_designer.schema_keys import CommonKey, PaintjobKey


class PaintjobReader:
    """Parses a paintjob JSON file into a `Paintjob`."""

    def read(self, data: str | bytes) -> Paintjob:
        if isinstance(data, bytes):
            data = data.decode("utf-8")

        raw = json.loads(data)
        self._validate_shape(raw)

        # Force the in-memory object's `schema_version` to current. An older
        # JSON that declared a lower version (e.g. a hypothetical migration
        # path) loads into a "current" model without a separate migration
        # step — if the format had actually changed incompatibly the shape
        # check above would have already rejected the file.
        raw[CommonKey.SCHEMA_VERSION] = Paintjob.SCHEMA_VERSION

        try:
            return Paintjob.model_validate(raw)
        except ValidationError as exc:
            raise ValueError(f"Paintjob is not valid: {exc}") from exc

    def _validate_shape(self, raw: object) -> None:
        if not isinstance(raw, dict):
            raise ValueError("Paintjob root must be a JSON object")

        schema_version = int(
            raw.get(CommonKey.SCHEMA_VERSION, Paintjob.SCHEMA_VERSION),
        )
        if schema_version > Paintjob.SCHEMA_VERSION:
            raise ValueError(
                f"Paintjob schema_version {schema_version} is newer than this "
                f"tool supports (max {Paintjob.SCHEMA_VERSION}). "
                "Upgrade Paintjob Designer to open this file."
            )

        slots_raw = raw.get(PaintjobKey.SLOTS, {})
        if not isinstance(slots_raw, dict):
            raise ValueError("Paintjob 'slots' must be an object")

        for slot_name, slot_raw in slots_raw.items():
            if not isinstance(slot_raw, dict):
                raise ValueError(
                    f"Slot {slot_name!r} must be an object with 'colors' "
                    f"(and optional 'pixels')"
                )

            colors_raw = slot_raw.get(PaintjobKey.COLORS)
            if colors_raw is None or len(colors_raw) != SlotColors.SIZE:
                raise ValueError(
                    f"Slot {slot_name!r} must have exactly {SlotColors.SIZE} colors, "
                    f"got {len(colors_raw) if colors_raw is not None else 0}"
                )
