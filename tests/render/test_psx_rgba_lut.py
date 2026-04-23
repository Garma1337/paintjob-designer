# coding: utf-8

import numpy as np

from paintjob_designer.models import PsxColor
from paintjob_designer.render.psx_rgba_lut import PsxRgbaLut


class TestPsxRgbaLut:

    def test_length_covers_every_u16(self):
        lut = PsxRgbaLut()

        assert lut.as_array().shape == (PsxRgbaLut.LENGTH,)
        assert lut.as_array().dtype == np.uint32

    def test_black_values_are_fully_transparent(self):
        lut = PsxRgbaLut()

        # CTR renders any RGB(0,0,0) texel as transparent regardless of
        # the stp bit, so both 0x0000 and 0x8000 must have alpha=0.
        for value in (0x0000, 0x8000):
            packed = int(lut[value])

            # Byte layout R, G, B, A in little-endian uint32.
            assert packed & 0xFF == 0              # R
            assert (packed >> 8) & 0xFF == 0       # G
            assert (packed >> 16) & 0xFF == 0      # B
            assert (packed >> 24) & 0xFF == 0      # A

    def test_non_black_values_are_fully_opaque(self):
        lut = PsxRgbaLut()

        # Any value whose RGB portion is non-zero should end up with alpha
        # = 0xFF, regardless of the stp bit.
        assert (int(lut[1]) >> 24) & 0xFF == 0xFF
        assert (int(lut[0x7FFF]) >> 24) & 0xFF == 0xFF
        assert (int(lut[0x8001]) >> 24) & 0xFF == 0xFF
        assert (int(lut[0xFFFF]) >> 24) & 0xFF == 0xFF

    def test_matches_color_converter_for_representative_values(self, color_converter):
        # Vectorized LUT must stay byte-identical to the per-pixel
        # ColorConverter path; any drift would silently change previews.
        lut = PsxRgbaLut()
        probes = [
            0x0000, 0x0001, 0x001F, 0x03E0, 0x7C00, 0x7FFF,
            0x03EB, 0x1234, 0x8000, 0x8001, 0xFFFF,
        ]

        for value in probes:
            packed = int(lut[value])
            lut_bytes = (
                packed & 0xFF,
                (packed >> 8) & 0xFF,
                (packed >> 16) & 0xFF,
                (packed >> 24) & 0xFF,
            )
            if (value & 0x7FFF) == 0:
                expected = (0, 0, 0, 0)
            else:
                rgb = color_converter.psx_to_rgb(PsxColor(value=value))
                expected = (rgb.r, rgb.g, rgb.b, 0xFF)

            assert lut_bytes == expected, f"drift at 0x{value:04X}: {lut_bytes} != {expected}"
