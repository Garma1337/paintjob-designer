# coding: utf-8

import pytest

from paintjob_designer.models import PsxColor, Rgb888


class TestPsxToRgb:

    def test_zero_is_black(self, color_converter):
        rgb = color_converter.psx_to_rgb(PsxColor(value=0x0000))

        assert (rgb.r, rgb.g, rgb.b) == (0, 0, 0)

    def test_max_each_component_is_white(self, color_converter):
        # b=31, g=31, r=31  ->  0 11111 11111 11111  =  0x7FFF
        rgb = color_converter.psx_to_rgb(PsxColor(value=0x7FFF))

        assert (rgb.r, rgb.g, rgb.b) == (255, 255, 255)

    def test_5_to_8_bit_replication(self, color_converter):
        # r=1 -> (1<<3)|(1>>2) = 8
        # r=16 -> (16<<3)|(16>>2) = 128|4 = 132
        rgb = color_converter.psx_to_rgb(PsxColor(value=0x0001))

        assert rgb.r == 8
        assert rgb.g == 0
        assert rgb.b == 0


class TestRgbToPsx:

    def test_black_is_zero(self, color_converter):
        color = color_converter.rgb_to_psx(Rgb888(r=0, g=0, b=0))

        assert color.value == 0

    def test_white_is_max(self, color_converter):
        color = color_converter.rgb_to_psx(Rgb888(r=255, g=255, b=255))

        assert color.value == 0x7FFF

    def test_quantizes_to_5_bit_grid(self, color_converter):
        # 0x5A = 90; 90>>3 = 11  -> stored as 5-bit 11 in r slot
        color = color_converter.rgb_to_psx(Rgb888(r=0x5A, g=0, b=0))

        assert color.r5 == 11

    def test_stp_bit_controls_bit_15(self, color_converter):
        color_off = color_converter.rgb_to_psx(Rgb888(), stp=0)
        color_on = color_converter.rgb_to_psx(Rgb888(), stp=1)

        assert color_off.stp == 0
        assert color_on.stp == 1


class TestSnapRgb:

    def test_snap_is_idempotent(self, color_converter):
        original = Rgb888(r=123, g=200, b=50)

        snapped = color_converter.snap_rgb(original)
        snapped_again = color_converter.snap_rgb(snapped)

        assert snapped == snapped_again

    def test_snap_never_changes_psx_reachable_values(self, color_converter):
        exact = Rgb888(r=0, g=0, b=0)

        assert color_converter.snap_rgb(exact) == exact


class TestHexRoundTrip:

    def test_rgb_to_hex(self, color_converter):
        assert color_converter.rgb_to_hex(Rgb888(r=0xFF, g=0x80, b=0x00)) == "#ff8000"

    def test_hex_to_rgb_with_hash(self, color_converter):
        rgb = color_converter.hex_to_rgb("#5aff00")

        assert (rgb.r, rgb.g, rgb.b) == (0x5A, 0xFF, 0x00)

    def test_hex_to_rgb_without_hash(self, color_converter):
        rgb = color_converter.hex_to_rgb("5aff00")

        assert (rgb.r, rgb.g, rgb.b) == (0x5A, 0xFF, 0x00)

    def test_hex_to_rgb_strips_whitespace(self, color_converter):
        rgb = color_converter.hex_to_rgb("  #5aff00  ")

        assert (rgb.r, rgb.g, rgb.b) == (0x5A, 0xFF, 0x00)

    @pytest.mark.parametrize("bad", ["", "#", "#12345", "#1234567", "gggggg", "#zzzzzz"])
    def test_hex_to_rgb_rejects_malformed(self, color_converter, bad):
        with pytest.raises(ValueError):
            color_converter.hex_to_rgb(bad)


class TestPsxHexRoundTrip:

    def test_psx_to_hex_is_snap_equivalent(self, color_converter):
        color = PsxColor(value=0x7FFF)

        assert color_converter.psx_to_hex(color) == "#ffffff"

    def test_hex_to_psx_quantizes(self, color_converter):
        # #5aff00 -> r=90, g=255, b=0
        #   r5 = 90>>3 = 11
        #   g5 = 255>>3 = 31
        #   b5 = 0
        #   value = (31<<5) | 11 = 0x03EB
        color = color_converter.hex_to_psx("#5aff00")

        assert color.value == 0x03EB

    def test_round_trip_is_stable_after_one_snap(self, color_converter):
        original_hex = "#123456"

        # First pass quantizes.
        psx = color_converter.hex_to_psx(original_hex)
        snapped_hex = color_converter.psx_to_hex(psx)

        # Subsequent round-trips never drift.
        psx2 = color_converter.hex_to_psx(snapped_hex)
        snapped_hex2 = color_converter.psx_to_hex(psx2)

        assert snapped_hex == snapped_hex2
