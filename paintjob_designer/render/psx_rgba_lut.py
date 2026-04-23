# coding: utf-8

import numpy as np

from paintjob_designer.constants import (
    PSX_BLUE_SHIFT,
    PSX_COMPONENT_MASK,
    PSX_GREEN_SHIFT,
    PSX_RGB_MASK,
    PSX_U16_MASK,
    RGB_COMPONENT_MAX,
)


class PsxRgbaLut:
    """Precomputed PSX u16 → packed RGBA uint32 lookup table."""

    LENGTH = PSX_U16_MASK + 1

    def __init__(self) -> None:
        self._values = self._build()

    def as_array(self) -> np.ndarray:
        """Raw (65536,) uint32 LUT. Callers index with a `np.uint16` buffer."""
        return self._values

    def __getitem__(self, key):
        return self._values[key]

    @staticmethod
    def _build() -> np.ndarray:
        values = np.arange(PsxRgbaLut.LENGTH, dtype=np.uint32)
        r5 = values & PSX_COMPONENT_MASK
        g5 = (values >> PSX_GREEN_SHIFT) & PSX_COMPONENT_MASK
        b5 = (values >> PSX_BLUE_SHIFT) & PSX_COMPONENT_MASK
        r8 = (r5 << 3) | (r5 >> 2)
        g8 = (g5 << 3) | (g5 >> 2)
        b8 = (b5 << 3) | (b5 >> 2)

        # CTR renders any black texel (RGB 0,0,0) as transparent in-game,
        # regardless of the stp bit, so both 0x0000 and 0x8000 must produce
        # alpha=0 in the preview. Masking off bit 15 handles both.
        a8 = np.where((values & PSX_RGB_MASK) == 0, 0, RGB_COMPONENT_MAX).astype(np.uint32)

        # Host is little-endian on every platform we care about, so packing as
        # `r | g<<8 | b<<16 | a<<24` lays the bytes out R, G, B, A — matches
        # QImage.Format_RGBA8888 and the GL texture upload format.
        return (r8 | (g8 << 8) | (b8 << 16) | (a8 << 24)).astype(np.uint32)
