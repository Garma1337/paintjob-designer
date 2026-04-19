# coding: utf-8

import pytest

from paintjob_designer.color.transform import (
    ColorTransformer,
    TransformMode,
    TransformParams,
)
from paintjob_designer.models import PsxColor


def _psx(r: int, g: int, b: int, stp: int = 0) -> PsxColor:
    r5 = (r >> 3) & 0x1F
    g5 = (g >> 3) & 0x1F
    b5 = (b >> 3) & 0x1F
    return PsxColor(value=((stp & 0x1) << 15) | (b5 << 10) | (g5 << 5) | r5)


@pytest.fixture
def transformer():
    return ColorTransformer()


class TestTransparencySentinel:

    def test_u16_zero_is_preserved_for_every_mode(self, transformer):
        sentinel = PsxColor(value=0)

        for mode in TransformMode:
            params = TransformParams(
                mode=mode,
                match_color=sentinel,
                replace_with=_psx(255, 0, 0),
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

    def test_replaces_exact_u16_match(self, transformer):
        red = _psx(255, 0, 0)
        blue = _psx(0, 0, 255)
        params = TransformParams(
            mode=TransformMode.REPLACE_MATCHES,
            match_color=red,
            replace_with=blue,
        )

        assert transformer.transform(red, params).value == blue.value

    def test_leaves_non_matching_colors_alone(self, transformer):
        red = _psx(255, 0, 0)
        green = _psx(0, 255, 0)
        blue = _psx(0, 0, 255)
        params = TransformParams(
            mode=TransformMode.REPLACE_MATCHES,
            match_color=red,
            replace_with=blue,
        )

        assert transformer.transform(green, params).value == green.value

    def test_stp_bit_is_part_of_the_match(self, transformer):
        # Two colors with the same RGB but different stp bits must not collide
        # — matching by full u16 preserves the CTR in-game distinction between
        # transparent-black and opaque-black.
        stp0_red = PsxColor(value=0x0000 | 0x1F)   # RGB=red, stp=0
        stp1_red = PsxColor(value=0x8000 | 0x1F)   # RGB=red, stp=1
        params = TransformParams(
            mode=TransformMode.REPLACE_MATCHES,
            match_color=stp0_red,
            replace_with=_psx(0, 255, 0),
        )

        assert transformer.transform(stp1_red, params).value == stp1_red.value

    def test_noop_when_params_incomplete(self, transformer):
        red = _psx(255, 0, 0)
        params = TransformParams(mode=TransformMode.REPLACE_MATCHES)

        # Neither match_color nor replace_with provided -> pass through.
        assert transformer.transform(red, params).value == red.value


class TestShiftHue:

    def test_180_degree_shift_flips_red_to_cyan(self, transformer):
        red = _psx(248, 0, 0)  # PSX-snapped red
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

    def test_hue_shift_wraps_at_360(self, transformer):
        red = _psx(248, 0, 0)
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

    def test_positive_shift_brightens(self, transformer):
        dim = _psx(64, 64, 64)
        params = TransformParams(
            mode=TransformMode.SHIFT_BRIGHTNESS, brightness_shift=0.5,
        )

        result = transformer.transform(dim, params)

        assert result.r5 > dim.r5
        assert result.g5 > dim.g5
        assert result.b5 > dim.b5

    def test_negative_shift_dims(self, transformer):
        bright = _psx(200, 200, 200)
        params = TransformParams(
            mode=TransformMode.SHIFT_BRIGHTNESS, brightness_shift=-0.5,
        )

        result = transformer.transform(bright, params)

        assert result.r5 < bright.r5
        assert result.g5 < bright.g5
        assert result.b5 < bright.b5

    def test_clamps_at_full_brightness(self, transformer):
        # An already-bright color pushed further must not overflow past max.
        bright = _psx(248, 248, 248)
        params = TransformParams(
            mode=TransformMode.SHIFT_BRIGHTNESS, brightness_shift=0.9,
        )

        result = transformer.transform(bright, params)

        assert result.r5 <= PsxColor.MAX_COMPONENT
        assert result.g5 <= PsxColor.MAX_COMPONENT
        assert result.b5 <= PsxColor.MAX_COMPONENT


class TestShiftSaturation:

    def test_negative_shift_desaturates_toward_grey(self, transformer):
        orange = _psx(255, 128, 0)
        params = TransformParams(
            mode=TransformMode.SHIFT_SATURATION, saturation_shift=-0.8,
        )

        result = transformer.transform(orange, params)

        # After heavy desat, R/G/B should be much closer together than before.
        spread_before = max(orange.r5, orange.g5, orange.b5) - min(orange.r5, orange.g5, orange.b5)
        spread_after = max(result.r5, result.g5, result.b5) - min(result.r5, result.g5, result.b5)
        assert spread_after < spread_before

    def test_full_desaturation_produces_grey(self, transformer):
        orange = _psx(255, 128, 0)
        params = TransformParams(
            mode=TransformMode.SHIFT_SATURATION, saturation_shift=-1.0,
        )

        result = transformer.transform(orange, params)

        assert result.r5 == result.g5 == result.b5


class TestRgbDelta:

    def test_adds_independently_per_channel(self, transformer):
        color = _psx(100, 100, 100)
        params = TransformParams(
            mode=TransformMode.RGB_DELTA,
            rgb_delta_r=50, rgb_delta_g=-50, rgb_delta_b=0,
        )

        result = transformer.transform(color, params)

        assert result.r5 > color.r5
        assert result.g5 < color.g5
        # Blue unchanged modulo PSX quantization — allow 1 LSB of wobble.
        assert abs(result.b5 - color.b5) <= 1

    def test_clamps_to_0_255(self, transformer):
        color = _psx(200, 200, 200)
        params = TransformParams(
            mode=TransformMode.RGB_DELTA,
            rgb_delta_r=200, rgb_delta_g=-500, rgb_delta_b=0,
        )

        result = transformer.transform(color, params)

        assert result.r5 == PsxColor.MAX_COMPONENT
        assert result.g5 == 0


class TestQuantization:

    def test_output_snaps_to_psx_grid(self, transformer):
        # Every returned PsxColor must be PSX-representable — i.e. already
        # constrained to the 5-bit-per-component grid. Implicit from the
        # constructor, but assert that no quantization junk leaks out.
        color = _psx(123, 45, 67)
        for mode in TransformMode:
            params = TransformParams(
                mode=mode,
                match_color=color,
                replace_with=_psx(200, 100, 50),
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
