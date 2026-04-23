# coding: utf-8

from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, model_serializer, model_validator
from pydantic.json_schema import GetJsonSchemaHandler
from pydantic_core import CoreSchema

from paintjob_designer.constants import (
    PSX_BITS_PER_COMPONENT,
    PSX_BLUE_SHIFT,
    PSX_COMPONENT_MASK,
    PSX_COMPONENT_MAX,
    PSX_GREEN_SHIFT,
    PSX_RED_SHIFT,
    PSX_RGB_MASK,
    PSX_STP_SHIFT,
    PSX_U16_MASK,
)


class PsxColor(BaseModel):
    """PSX 15-bit BGR color with stencil bit."""

    model_config = ConfigDict(frozen=False)

    BITS_PER_COMPONENT: ClassVar[int] = PSX_BITS_PER_COMPONENT
    MAX_COMPONENT: ClassVar[int] = PSX_COMPONENT_MAX

    value: int = 0

    @property
    def r5(self) -> int:
        return (self.value >> PSX_RED_SHIFT) & PSX_COMPONENT_MASK

    @property
    def g5(self) -> int:
        return (self.value >> PSX_GREEN_SHIFT) & PSX_COMPONENT_MASK

    @property
    def b5(self) -> int:
        return (self.value >> PSX_BLUE_SHIFT) & PSX_COMPONENT_MASK

    @property
    def stp(self) -> int:
        return (self.value >> PSX_STP_SHIFT) & 0x1

    @property
    def is_transparent(self) -> bool:
        """True when CTR will render this texel as transparent in-game."""
        return (self.value & PSX_RGB_MASK) == 0

    @staticmethod
    def parse_hex(hex_str: str) -> int:
        """Parse PSX u16 hex (`#xxxx`) or legacy RGB hex (`#rrggbb`) into a u16 value."""
        s = hex_str.strip().lstrip("#")

        if len(s) == 4:
            try:
                return int(s, 16) & PSX_U16_MASK
            except ValueError as exc:
                raise ValueError(f"Invalid PSX hex color {hex_str!r}") from exc

        if len(s) == 6:
            try:
                r = int(s[0:2], 16)
                g = int(s[2:4], 16)
                b = int(s[4:6], 16)
            except ValueError as exc:
                raise ValueError(f"Invalid RGB hex color {hex_str!r}") from exc

            r5 = (r >> 3) & PSX_COMPONENT_MASK
            g5 = (g >> 3) & PSX_COMPONENT_MASK
            b5 = (b >> 3) & PSX_COMPONENT_MASK
            return (b5 << PSX_BLUE_SHIFT) | (g5 << PSX_GREEN_SHIFT) | r5

        raise ValueError(
            f"Expected 4-digit PSX hex (#xxxx) or 6-digit RGB hex, got {hex_str!r}"
        )

    @model_serializer
    def _to_hex(self) -> str:
        return f"#{self.value & PSX_U16_MASK:04x}"

    @model_validator(mode="before")
    @classmethod
    def _from_hex(cls, data: Any) -> Any:
        """Accept a hex string or existing dict/model — anything else passes through."""
        if isinstance(data, str):
            return {"value": cls.parse_hex(data)}

        return data

    @classmethod
    def __get_pydantic_json_schema__(
        cls, schema: CoreSchema, handler: GetJsonSchemaHandler,
    ) -> dict:
        """Emit a string schema that matches the serialized hex form."""
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
