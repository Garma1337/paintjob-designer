# coding: utf-8

import pytest

from paintjob_designer.color.gradient import GradientGenerator, GradientSpace
from paintjob_designer.models import PsxColor, Rgb888


@pytest.fixture
def generator(color_converter):
    return GradientGenerator(color_converter)


@pytest.fixture
def psx(color_converter):
    """Build a PSX color via the real converter — avoids duplicating its
    packing logic in the test file."""
    def _build(r: int, g: int, b: int, stp: int = 0) -> PsxColor:
        return color_converter.rgb_to_psx(Rgb888(r=r, g=g, b=b), stp=stp)

    return _build


class TestEndpointsAndLength:

    def test_produces_requested_count(self, generator, psx):
        start = psx(0, 0, 0)
        end = psx(248, 248, 248)

        result = generator.generate(start, end, 5, GradientSpace.RGB)

        assert len(result) == 5

    def test_zero_count_is_empty(self, generator, psx):
        result = generator.generate(
            psx(0, 0, 0), psx(248, 248, 248), 0, GradientSpace.RGB,
        )

        assert result == []

    def test_single_count_returns_start_only(self, generator, psx):
        start = psx(128, 64, 32)

        result = generator.generate(
            start, psx(248, 248, 248), 1, GradientSpace.RGB,
        )

        assert result == [start]

    def test_endpoints_are_preserved(self, generator, psx):
        start = psx(248, 0, 0)
        end = psx(0, 0, 248)

        result = generator.generate(start, end, 4, GradientSpace.RGB)

        # Endpoints may be re-quantized; their 5-bit components should match
        # the input's 5-bit components exactly.
        assert (result[0].r5, result[0].g5, result[0].b5) == (start.r5, start.g5, start.b5)
        assert (result[-1].r5, result[-1].g5, result[-1].b5) == (end.r5, end.g5, end.b5)


class TestRgbInterpolation:

    def test_midpoint_is_channel_average(self, generator, psx):
        # Black to white in 3 steps: mid should be ~50% grey.
        result = generator.generate(
            psx(0, 0, 0), psx(248, 248, 248), 3, GradientSpace.RGB,
        )

        mid = result[1]
        assert 14 <= mid.r5 <= 17  # ~50% of 31
        assert 14 <= mid.g5 <= 17
        assert 14 <= mid.b5 <= 17

    def test_monotonic_on_one_channel(self, generator, psx):
        # Pure-red ramp: red5 should increase monotonically, g/b stay low.
        result = generator.generate(
            psx(0, 0, 0), psx(248, 0, 0), 6, GradientSpace.RGB,
        )

        red_vals = [c.r5 for c in result]
        assert red_vals == sorted(red_vals)
        assert red_vals[0] == 0
        assert red_vals[-1] == 31
        for c in result:
            assert c.g5 == 0
            assert c.b5 == 0


class TestHsvInterpolation:

    def test_takes_short_arc_around_hue_wheel(self, generator, psx):
        # Red (hue 0) → blue (hue ~0.67): shorter arc goes through magenta
        # (0→1, wrapping) at the -180° direction. Midpoint should have
        # non-trivial red AND blue, no green.
        result = generator.generate(
            psx(248, 0, 0), psx(0, 0, 248), 3, GradientSpace.HSV,
        )

        mid = result[1]
        assert mid.r5 > 4
        assert mid.b5 > 4
        # Green stays dim on the magenta arc; should be much smaller than r/b.
        assert mid.g5 < max(mid.r5, mid.b5)

    def test_midpoint_stays_saturated(self, generator, psx):
        # HSV lerp of red→yellow should hold saturation up (pass through
        # orange), not desaturate toward grey.
        result = generator.generate(
            psx(248, 0, 0), psx(248, 248, 0), 3, GradientSpace.HSV,
        )

        mid = result[1]
        # At least one channel should be at max saturation.
        assert mid.r5 == 31


class TestStpPreservation:

    def test_all_colors_inherit_start_stp(self, generator, color_converter):
        # stp=1 red vs stp=0 blue. Gradient should carry stp=1 through.
        start = color_converter.rgb_to_psx(Rgb888(r=248, g=0, b=0), stp=1)
        end = color_converter.rgb_to_psx(Rgb888(r=0, g=0, b=248), stp=0)

        result = generator.generate(start, end, 4, GradientSpace.RGB)

        for c in result:
            assert c.stp == 1
