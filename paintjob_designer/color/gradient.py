# coding: utf-8

import colorsys
from enum import Enum

from paintjob_designer.color.converter import ColorConverter
from paintjob_designer.models import PsxColor, Rgb888


class GradientSpace(Enum):
    """Color space the interpolation is carried out in.

    RGB is linear-in-channel — simplest, works for most palette ramps.
    HSV interpolates hue along the shorter arc of the wheel, which produces
    more saturated midpoints for gradients that cross primary colors (e.g.
    red → blue through purple instead of the desaturated mid-RGB lerp).
    """

    RGB = "rgb"
    HSV = "hsv"


class GradientGenerator:
    """Produces PSX-quantized gradients between two `PsxColor` endpoints.

    Stateless, but a class rather than a free function so it can be
    registered in the DI container and injected where needed — keeps the
    rest of the codebase consistent with the `ColorConverter` /
    `ColorTransformer` pattern.

    Converts via an injected `ColorConverter`: the converter already owns
    the authoritative 5-5-5 ↔ 8-8-8 conversion and the u16 pack/unpack, so
    the gradient module has no reason to reimplement either.
    """

    def __init__(self, color_converter: ColorConverter) -> None:
        self._converter = color_converter

    def generate(
        self,
        start: PsxColor,
        end: PsxColor,
        count: int,
        space: GradientSpace,
    ) -> list[PsxColor]:
        """Produce `count` PSX-quantized colors along the gradient.

        Both endpoints are included (so `count >= 2`). Intermediate colors
        inherit `start.stp` — a single slot typically shares its
        transparency-bit state, so a gradient that mixes a `stp=0` and
        `stp=1` endpoint would otherwise produce a confusing
        half-transparent ramp. If the artist needs the other stp state,
        they can fix the endpoint post-fill.
        """
        if count <= 0:
            return []

        if count == 1:
            return [start]

        start_rgb = self._converter.psx_to_rgb(start)
        end_rgb = self._converter.psx_to_rgb(end)

        result: list[PsxColor] = []
        for i in range(count):
            t = i / (count - 1)

            if space == GradientSpace.HSV:
                r, g, b = self._lerp_hsv(start_rgb, end_rgb, t)
            else:
                r = round(start_rgb.r + (end_rgb.r - start_rgb.r) * t)
                g = round(start_rgb.g + (end_rgb.g - start_rgb.g) * t)
                b = round(start_rgb.b + (end_rgb.b - start_rgb.b) * t)

            result.append(self._converter.rgb_to_psx(
                Rgb888(r=r, g=g, b=b), stp=start.stp,
            ))

        return result

    def _lerp_hsv(
        self, start: Rgb888, end: Rgb888, t: float,
    ) -> tuple[int, int, int]:
        sh, ss, sv = colorsys.rgb_to_hsv(
            start.r / 255.0, start.g / 255.0, start.b / 255.0,
        )
        eh, es, ev = colorsys.rgb_to_hsv(
            end.r / 255.0, end.g / 255.0, end.b / 255.0,
        )

        # Take the shorter arc around the hue wheel (e.g. red→magenta, not
        # the long way through green). Without this, a red-to-blue gradient
        # goes through yellow/green, which is almost never what artists want.
        dh = eh - sh
        if dh > 0.5:
            dh -= 1.0
        elif dh < -0.5:
            dh += 1.0

        h = (sh + dh * t) % 1.0
        s = ss + (es - ss) * t
        v = sv + (ev - sv) * t

        r_f, g_f, b_f = colorsys.hsv_to_rgb(h, s, v)
        return round(r_f * 255), round(g_f * 255), round(b_f * 255)
