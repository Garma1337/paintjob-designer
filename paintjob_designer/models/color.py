# coding: utf-8

from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, model_serializer, model_validator
from pydantic.json_schema import GetJsonSchemaHandler
from pydantic_core import CoreSchema


class PsxColor(BaseModel):
    """PSX 15-bit BGR color with stencil bit.

    Bit layout (16-bit little-endian short):
        stp | bbbbb | ggggg | rrrrr
         15 | 14-10 |  9-5  |  4-0

    Stored as a single `value: int` so the stp bit round-trips losslessly
    through serialization. Serializes as a 4-digit PSX u16 hex string
    `"#xxxx"` (preserving stp) and accepts either that form or legacy
    6-digit RGB hex (`"#rrggbb"`, treated as stp=0) when validating
    from JSON.
    """

    model_config = ConfigDict(frozen=False)

    BITS_PER_COMPONENT: ClassVar[int] = 5
    MAX_COMPONENT: ClassVar[int] = 31

    value: int = 0

    @property
    def r5(self) -> int:
        return self.value & 0x1F

    @property
    def g5(self) -> int:
        return (self.value >> 5) & 0x1F

    @property
    def b5(self) -> int:
        return (self.value >> 10) & 0x1F

    @property
    def stp(self) -> int:
        return (self.value >> 15) & 0x1

    @staticmethod
    def parse_hex(hex_str: str) -> int:
        """Parse PSX u16 hex (`#xxxx`) or legacy RGB hex (`#rrggbb`) into a u16 value.

        RGB hex maps to stp=0 + 5-bit-per-channel quantization, matching the
        pre-pydantic reader's backward-compat behavior. Exposed on the class
        (rather than a module-level helper) so the hex-format contract stays
        co-located with the type that defines it.
        """
        s = hex_str.strip().lstrip("#")

        if len(s) == 4:
            try:
                return int(s, 16) & 0xFFFF
            except ValueError as exc:
                raise ValueError(f"Invalid PSX hex color {hex_str!r}") from exc

        if len(s) == 6:
            try:
                r = int(s[0:2], 16)
                g = int(s[2:4], 16)
                b = int(s[4:6], 16)
            except ValueError as exc:
                raise ValueError(f"Invalid RGB hex color {hex_str!r}") from exc

            r5 = (r >> 3) & 0x1F
            g5 = (g >> 3) & 0x1F
            b5 = (b >> 3) & 0x1F
            return (b5 << 10) | (g5 << 5) | r5

        raise ValueError(
            f"Expected 4-digit PSX hex (#xxxx) or 6-digit RGB hex, got {hex_str!r}"
        )

    @model_serializer
    def _to_hex(self) -> str:
        return f"#{self.value & 0xFFFF:04x}"

    @model_validator(mode="before")
    @classmethod
    def _from_hex(cls, data: Any) -> Any:
        """Accept a hex string or existing dict/model — anything else passes through.

        Strings are the library JSON's native color format; dicts are what
        pydantic itself produces when round-tripping through `model_dump()`
        (we override the dump to a string, but existing `PsxColor(value=...)`
        constructions pass a dict-like kwarg flow that hits this path).
        """
        if isinstance(data, str):
            return {"value": cls.parse_hex(data)}

        return data

    @classmethod
    def __get_pydantic_json_schema__(
        cls, schema: CoreSchema, handler: GetJsonSchemaHandler,
    ) -> dict:
        """Emit a string schema that matches the serialized hex form.

        Pydantic's default schema generator describes the underlying
        `value: int` field, but the JSON this model actually produces
        (via `_to_hex`) is a string like `"#7fff"`. Override the schema
        so external consumers see the correct on-the-wire shape.
        """
        return {
            "type": "string",
            "title": "PsxColor",
            "description": (
                "PSX 15-bit BGR color as a 4-digit hex string `#xxxx`. "
                "Bit 15 is the stp (stencil / semi-transparency) flag, "
                "bits 14-10 blue, 9-5 green, 4-0 red. Value `#0000` is "
                "the PSX transparency sentinel. Legacy 6-digit RGB hex "
                "(`#rrggbb`) is accepted on input and treated as stp=0."
            ),
            "pattern": r"^#[0-9a-fA-F]{4}([0-9a-fA-F]{2})?$",
            "examples": ["#0000", "#7fff", "#8000"],
        }


class Rgb888(BaseModel):
    model_config = ConfigDict(frozen=False)

    r: int = 0
    g: int = 0
    b: int = 0
