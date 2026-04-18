# coding: utf-8

import numpy as np


class PsxRgbaLut:
    """Precomputed PSX u16 → packed RGBA uint32 lookup table.

    One entry per possible 16-bit PSX color value (65536 total). The indexed
    fetch `lut[u16]` is the vectorized path the atlas renderer uses — orders
    of magnitude faster than calling `ColorConverter.psx_to_rgb` per pixel.

    Split out of `AtlasRenderer` so the bit-twiddling has its own home: the
    formula here duplicates what `ColorConverter` computes per-color, and
    `tests/render/test_psx_rgba_lut.py` pins the two together so a change to
    either can't silently drift.
    """

    LENGTH = 65536

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
        r5 = values & 0x1F
        g5 = (values >> 5) & 0x1F
        b5 = (values >> 10) & 0x1F
        r8 = (r5 << 3) | (r5 >> 2)
        g8 = (g5 << 3) | (g5 >> 2)
        b8 = (b5 << 3) | (b5 >> 2)
        # value == 0 is PSX's "fully transparent" sentinel; everything else
        # gets full alpha. The stp bit (bit 15) is ignored — blend context
        # isn't meaningful in a static preview.
        a8 = np.where(values == 0, 0, 0xFF).astype(np.uint32)
        # Host is little-endian on every platform we care about, so packing as
        # `r | g<<8 | b<<16 | a<<24` lays the bytes out R, G, B, A — matches
        # QImage.Format_RGBA8888 and the GL texture upload format.
        return (r8 | (g8 << 8) | (b8 << 16) | (a8 << 24)).astype(np.uint32)
