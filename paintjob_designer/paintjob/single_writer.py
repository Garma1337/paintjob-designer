# coding: utf-8

import json

from paintjob_designer.color.converter import ColorConverter
from paintjob_designer.models import SinglePaintjob, SlotColors


class SinglePaintjobWriter:
    """Serializes a `SinglePaintjob` to JSON.

    Each slot's 16 colors are written as the PSX 16-bit value in hex
    (`#xxxx`). This preserves the stp bit so colors roundtrip exactly — a
    black CLUT entry with stp=1 (opaque) survives save/load without becoming
    value=0 (which renders transparent).
    """

    def __init__(self, color_converter: ColorConverter) -> None:
        self._colors = color_converter

    def serialize(self, paintjob: SinglePaintjob, indent: int = 2) -> str:
        return json.dumps(self._to_dict(paintjob), indent=indent, ensure_ascii=False)

    def _to_dict(self, paintjob: SinglePaintjob) -> dict:
        return {
            "schema_version": paintjob.schema_version,
            "name": paintjob.name,
            "author": paintjob.author,
            "slots": {
                name: self._slot_to_list(colors)
                for name, colors in paintjob.slots.items()
            },
        }

    def _slot_to_list(self, slot: SlotColors) -> list[str]:
        return [self._colors.psx_to_u16_hex(c) for c in slot.colors]
