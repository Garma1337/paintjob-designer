# coding: utf-8

import pytest

from paintjob_designer.color.transform import (
    ColorTransformer,
    TransformMode,
    TransformParams,
)
from paintjob_designer.models import PsxColor, Rgb888


@pytest.fixture
def transformer(color_converter):
    return ColorTransformer(color_converter)


@pytest.fixture
def psx(color_converter):
    """Build a PSX color from 8-bit RGB using the real converter.

    Avoids the previous `_psx()` test helper that re-implemented
    `ColorConverter.rgb_to_psx` by hand, which is the kind of drift-prone
    duplication we want to keep out of the test suite.
    """
    def _build(r: int, g: int, b: int, stp: int = 0) -> PsxColor:
        return color_converter.rgb_to_psx(Rgb888(r=r, g=g, b=b), stp=stp)

    return _build


class TestTransparencySentinel:

    def test_u16_zero_is_preserved_for_every_mode(self, transformer, psx):
        sentinel = PsxColor(value=0)

        for mode in TransformMode:
            params = TransformParams(
                mode=mode,
                match_color=sentinel,
                replace_with=psx(255, 0, 0),
                hue_shift_degrees=90,
                brightness_shift=0.5,
                saturation_shift=-0.5,
                rgb_delta_r=10, rgb_delta_g=10, rgb_delta_b=10,
            )

            result = transformer.transform(sentinel, params)

            assert result.value == 0, (
                f"sentinel must pass through unchanged for mode={mode.name}"
            )

    def test_opaque_black_is_not_the_sentinel(self, transformer):
        # stp=1 black (value=0x8000) is opaque-black, different from the
        # transparency sentinel (value=0). Must still transform normally.
        opaque_black = PsxColor(value=0x8000)
        params = TransformParams(
            mode=TransformMode.SHIFT_BRIGHTNESS,
            brightness_shift=0.5,
        )

        result = transformer.transform(opaque_black, params)

        assert result.value != 0x8000
        assert result.stp == 1  # stp bit preserved


class TestReplaceMatches:

    def test_replaces_exact_u16_match(self, transformer, psx):
        red = psx(255, 0, 0)
        blue = psx(0, 0, 255)
        params = TransformParams(
            mode=TransformMode.REPLACE_MATCHES,
            match_color=red,
            replace_with=blue,
        )

        assert transformer.transform(red, params).value == blue.value

    def test_leaves_non_matching_colors_alone(self, transformer, psx):
        red = psx(255, 0, 0)
        green = psx(0, 255, 0)
        blue = psx(0, 0, 255)
        params = TransformParams(
            mode=TransformMode.REPLACE_MATCHES,
            match_color=red,
            replace_with=blue,
        )

        assert transformer.transform(green, params).value == green.value

    def test_stp_bit_is_part_of_the_match(self, transformer, psx):
        # Two colors with the same RGB but different stp bits must not collide
        # — matching by full u16 preserves the CTR in-game distinction between
        # transparent-black and opaque-black.
        stp0_red = PsxColor(value=0x0000 | 0x1F)   # RGB=red, stp=0
        stp1_red = PsxColor(value=0x8000 | 0x1F)   # RGB=red, stp=1
        params = TransformParams(
            mode=TransformMode.REPLACE_MATCHES,
            match_color=stp0_red,
            replace_with=psx(0, 255, 0),
        )

        assert transformer.transform(stp1_red, params).value == stp1_red.value

    def test_noop_when_params_incomplete(self, transformer, psx):
        red = psx(255, 0, 0)
        params = TransformParams(mode=TransformMode.REPLACE_MATCHES)

        # Neither match_color nor replace_with provided -> pass through.
        assert transformer.transform(red, params).value == red.value


class TestShiftHue:

    def test_180_degree_shift_flips_red_to_cyan(self, transformer, psx):
        red = psx(248, 0, 0)  # PSX-snapped red
        params = TransformParams(
            mode=TransformMode.SHIFT_HUE,
            hue_shift_degrees=180.0,
        )

        result = transformer.transform(red, params)

        # Red (hue 0) + 180° -> cyan (hue 180). Some quantization wobble is
        # expected, so compare 5-bit components loosely.
        assert result.r5 < 4
        assert result.g5 > 24
        assert result.b5 > 24

    def test_hue_shift_wraps_at_360(self, transformer, psx):
        red = psx(248, 0, 0)
        once = transformer.transform(red, TransformParams(
            mode=TransformMode.SHIFT_HUE, hue_shift_degrees=90,
        ))
        wrapped = transformer.transform(red, TransformParams(
            mode=TransformMode.SHIFT_HUE, hue_shift_degrees=450,   # 360 + 90
        ))

        assert once.value == wrapped.value

    def test_preserves_stp_bit(self, transformer):
        opaque_red = PsxColor(value=0x8000 | 0x1F)
        params = TransformParams(
            mode=TransformMode.SHIFT_HUE, hue_shift_degrees=90,
        )

        assert transformer.transform(opaque_red, params).stp == 1


class TestShiftBrightness:

    def test_positive_shift_brightens(self, transformer, psx):
        dim = psx(64, 64, 64)
        params = TransformParams(
            mode=TransformMode.SHIFT_BRIGHTNESS, brightness_shift=0.5,
        )

        result = transformer.transform(dim, params)

        assert result.r5 > dim.r5
        assert result.g5 > dim.g5
        assert result.b5 > dim.b5

    def test_negative_shift_dims(self, transformer, psx):
        bright = psx(200, 200, 200)
        params = TransformParams(
            mode=TransformMode.SHIFT_BRIGHTNESS, brightness_shift=-0.5,
        )

        result = transformer.transform(bright, params)

        assert result.r5 < bright.r5
        assert result.g5 < bright.g5
        assert result.b5 < bright.b5

    def test_clamps_at_full_brightness(self, transformer, psx):
        # An already-bright color pushed further must not overflow past max.
        bright = psx(248, 248, 248)
        params = TransformParams(
            mode=TransformMode.SHIFT_BRIGHTNESS, brightness_shift=0.9,
        )

        result = transformer.transform(bright, params)

        assert result.r5 <= PsxColor.MAX_COMPONENT
        assert result.g5 <= PsxColor.MAX_COMPONENT
        assert result.b5 <= PsxColor.MAX_COMPONENT


class TestShiftSaturation:

    def test_negative_shift_desaturates_toward_grey(self, transformer, psx):
        orange = psx(255, 128, 0)
        params = TransformParams(
            mode=TransformMode.SHIFT_SATURATION, saturation_shift=-0.8,
        )

        result = transformer.transform(orange, params)

        # After heavy desat, R/G/B should be much closer together than before.
        spread_before = max(orange.r5, orange.g5, orange.b5) - min(orange.r5, orange.g5, orange.b5)
        spread_after = max(result.r5, result.g5, result.b5) - min(result.r5, result.g5, result.b5)
        assert spread_after < spread_before

    def test_full_desaturation_produces_grey(self, transformer, psx):
        orange = psx(255, 128, 0)
        params = TransformParams(
            mode=TransformMode.SHIFT_SATURATION, saturation_shift=-1.0,
        )

        result = transformer.transform(orange, params)

        assert result.r5 == result.g5 == result.b5


class TestRgbDelta:

    def test_adds_independently_per_channel(self, transformer, psx):
        color = psx(100, 100, 100)
        params = TransformParams(
            mode=TransformMode.RGB_DELTA,
            rgb_delta_r=50, rgb_delta_g=-50, rgb_delta_b=0,
        )

        result = transformer.transform(color, params)

        assert result.r5 > color.r5
        assert result.g5 < color.g5
        # Blue unchanged modulo PSX quantization — allow 1 LSB of wobble.
        assert abs(result.b5 - color.b5) <= 1

    def test_clamps_to_0_255(self, transformer, psx):
        color = psx(200, 200, 200)
        params = TransformParams(
            mode=TransformMode.RGB_DELTA,
            rgb_delta_r=200, rgb_delta_g=-500, rgb_delta_b=0,
        )

        result = transformer.transform(color, params)

        assert result.r5 == PsxColor.MAX_COMPONENT
        assert result.g5 == 0


class TestReplaceHue:

    def test_green_in_tolerance_rotates_to_red_family(self, transformer, psx):
        green = psx(0, 255, 0)
        source = psx(0, 255, 0)   # hue 120°
        target = psx(255, 0, 0)   # hue 0° (target −120° from source)

        params = TransformParams(
            mode=TransformMode.REPLACE_HUE,
            source_color=source,
            target_color=target,
            hue_tolerance_degrees=30.0,
        )

        result = transformer.transform(green, params)

        # Pure green rotated to the red end of the spectrum — red dominates.
        assert result.r5 > result.g5
        assert result.r5 > result.b5

    def test_relative_shading_preserved(self, transformer, psx):
        """Two greens of different brightness must stay distinct after the swap."""
        bright_green = psx(0, 255, 0)
        dim_green = psx(0, 96, 0)
        source = psx(0, 255, 0)
        target = psx(255, 0, 0)

        params = TransformParams(
            mode=TransformMode.REPLACE_HUE,
            source_color=source,
            target_color=target,
            hue_tolerance_degrees=30.0,
        )

        bright_result = transformer.transform(bright_green, params)
        dim_result = transformer.transform(dim_green, params)

        # The brighter green should land as a brighter red.
        assert bright_result.r5 > dim_result.r5

    def test_color_outside_tolerance_is_untouched(self, transformer, psx):
        blue = psx(0, 0, 255)     # hue 240°
        source = psx(0, 255, 0)   # hue 120°, |240-120| = 120° > tolerance
        target = psx(255, 0, 0)

        params = TransformParams(
            mode=TransformMode.REPLACE_HUE,
            source_color=source,
            target_color=target,
            hue_tolerance_degrees=30.0,
        )

        assert transformer.transform(blue, params).value == blue.value

    def test_near_gray_input_is_untouched(self, transformer, psx):
        # s≈0 → hue is meaningless, skip even if the nominal hue matches.
        near_white = psx(240, 240, 240)
        source = psx(0, 255, 0)
        target = psx(255, 0, 0)

        params = TransformParams(
            mode=TransformMode.REPLACE_HUE,
            source_color=source,
            target_color=target,
            hue_tolerance_degrees=180.0,
        )

        assert transformer.transform(near_white, params).value == near_white.value

    def test_near_gray_source_is_noop(self, transformer, psx):
        # Gray source has no hue to match — op should pass everything through.
        bright_red = psx(255, 0, 0)
        source = psx(128, 128, 128)
        target = psx(0, 255, 0)

        params = TransformParams(
            mode=TransformMode.REPLACE_HUE,
            source_color=source,
            target_color=target,
            hue_tolerance_degrees=180.0,
        )

        assert transformer.transform(bright_red, params).value == bright_red.value

    def test_noop_when_params_incomplete(self, transformer, psx):
        red = psx(255, 0, 0)
        params = TransformParams(mode=TransformMode.REPLACE_HUE)

        assert transformer.transform(red, params).value == red.value

    def test_stp_bit_is_preserved(self, transformer, psx):
        opaque_green = transformer._converter.rgb_to_psx(
            Rgb888(r=0, g=255, b=0), stp=1,
        )
        params = TransformParams(
            mode=TransformMode.REPLACE_HUE,
            source_color=psx(0, 255, 0),
            target_color=psx(255, 0, 0),
            hue_tolerance_degrees=30.0,
        )

        assert transformer.transform(opaque_green, params).stp == 1


class TestQuantization:

    def test_output_snaps_to_psx_grid(self, transformer, psx):
        # Every returned PsxColor must be PSX-representable — i.e. already
        # constrained to the 5-bit-per-component grid. Implicit from the
        # constructor, but assert that no quantization junk leaks out.
        color = psx(123, 45, 67)
        for mode in TransformMode:
            params = TransformParams(
                mode=mode,
                match_color=color,
                replace_with=psx(200, 100, 50),
                hue_shift_degrees=37,
                brightness_shift=0.13,
                saturation_shift=-0.27,
                rgb_delta_r=11, rgb_delta_g=-17, rgb_delta_b=3,
            )
            result = transformer.transform(color, params)

            assert 0 <= result.r5 <= PsxColor.MAX_COMPONENT
            assert 0 <= result.g5 <= PsxColor.MAX_COMPONENT
            assert 0 <= result.b5 <= PsxColor.MAX_COMPONENT
            assert result.stp in (0, 1)
