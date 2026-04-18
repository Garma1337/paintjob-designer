# coding: utf-8

from paintjob_designer.models import PsxColor, Rgb888


class TestPsxColor:

    def test_defaults_to_zero(self):
        color = PsxColor()

        assert color.value == 0
        assert color.r5 == 0
        assert color.g5 == 0
        assert color.b5 == 0
        assert color.stp == 0

    def test_decomposes_components(self):
        # stp=1, b=31, g=14, r=6  ->  1 11111 01110 00110  = 0xFDC6
        color = PsxColor(value=0xFDC6)

        assert color.r5 == 6
        assert color.g5 == 14
        assert color.b5 == 31
        assert color.stp == 1

    def test_masks_out_of_range_bits(self):
        color = PsxColor(value=0x1FFFF)

        # Only the low 16 bits are meaningful; properties mask independently.
        assert color.r5 == 31
        assert color.g5 == 31
        assert color.b5 == 31
        assert color.stp == 1


class TestRgb888:

    def test_defaults_to_zero(self):
        rgb = Rgb888()

        assert rgb.r == 0
        assert rgb.g == 0
        assert rgb.b == 0

    def test_stores_components(self):
        rgb = Rgb888(r=10, g=20, b=30)

        assert (rgb.r, rgb.g, rgb.b) == (10, 20, 30)
