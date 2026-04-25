# coding: utf-8

from paintjob_designer.constants import (
    PSX_BLUE_SHIFT,
    PSX_COMPONENT_MASK,
    PSX_GREEN_SHIFT,
    PSX_STP_SHIFT,
    PSX_U16_MASK,
    RGB_COMPONENT_MAX,
)
from paintjob_designer.models import PsxColor, Rgb888


class ColorConverter:
    """Converts between PSX 15-bit BGR and RGB888, and parses/formats hex strings."""

    def psx_to_rgb(self, color: PsxColor) -> Rgb888:
        return Rgb888(
            r=self._expand_5_to_8(color.r5),
            g=self._expand_5_to_8(color.g5),
            b=self._expand_5_to_8(color.b5),
        )

    def rgb_to_psx(self, rgb: Rgb888, stp: int = 0) -> PsxColor:
        r5 = (rgb.r >> 3) & PSX_COMPONENT_MASK
        g5 = (rgb.g >> 3) & PSX_COMPONENT_MASK
        b5 = (rgb.b >> 3) & PSX_COMPONENT_MASK
        value = (
            ((stp & 0x1) << PSX_STP_SHIFT)
            | (b5 << PSX_BLUE_SHIFT)
            | (g5 << PSX_GREEN_SHIFT)
            | r5
        )

        return PsxColor(value=value)

    def rgb_to_hex(self, rgb: Rgb888) -> str:
        return f"#{rgb.r:02x}{rgb.g:02x}{rgb.b:02x}"

    def hex_to_rgb(self, hex_str: str) -> Rgb888:
        s = hex_str.strip().lstrip("#")
        if len(s) != 6:
            raise ValueError(f"Expected 6-char hex color, got {hex_str!r}")

        try:
            return Rgb888(
                r=int(s[0:2], 16),
                g=int(s[2:4], 16),
                b=int(s[4:6], 16),
            )
        except ValueError as exc:
            raise ValueError(f"Invalid hex color {hex_str!r}") from exc

    def snap_rgb(self, rgb: Rgb888) -> Rgb888:
        """Round an RGB value to the nearest PSX-representable value."""
        return self.psx_to_rgb(self.rgb_to_psx(rgb))

    def psx_to_hex(self, color: PsxColor) -> str:
        return self.rgb_to_hex(self.psx_to_rgb(color))

    def hex_to_psx(self, hex_str: str, stp: int = 0) -> PsxColor:
        return self.rgb_to_psx(self.hex_to_rgb(hex_str), stp=stp)

    def psx_to_u16_hex(self, color: PsxColor) -> str:
        """Serialize the full 16-bit PSX value as a `#xxxx` hex string."""
        return f"#{color.value:04x}"

    def u16_hex_to_psx(self, hex_str: str) -> PsxColor:
        """Parse a `#xxxx` u16 hex string (produced by `psx_to_u16_hex`)."""
        s = hex_str.strip().lstrip("#")
        if len(s) == 4:
            try:
                return PsxColor(value=int(s, 16) & PSX_U16_MASK)
            except ValueError as exc:
                raise ValueError(f"Invalid PSX hex color {hex_str!r}") from exc

        if len(s) == 6:
            return self.hex_to_psx(hex_str)

        raise ValueError(
            f"Expected 4-digit PSX hex (#xxxx) or 6-digit RGB hex, got {hex_str!r}"
        )

    def _expand_5_to_8(self, v5: int) -> int:
        """Expand a 5-bit component to 8 bits using bit-replication: (v<<3)|(v>>2)."""
        return ((v5 << 3) | (v5 >> 2)) & RGB_COMPONENT_MAX
