# coding: utf-8

import colorsys
from dataclasses import dataclass
from enum import Enum

from paintjob_designer.color.converter import ColorConverter
from paintjob_designer.models import PsxColor, Rgb888


class TransformMode(Enum):
    """Bulk operations the Transform Colors dialog can apply across a scope."""

    REPLACE_MATCHES = "replace_matches"
    REPLACE_HUE = "replace_hue"
    SHIFT_HUE = "shift_hue"
    SHIFT_BRIGHTNESS = "shift_brightness"
    SHIFT_SATURATION = "shift_saturation"
    RGB_DELTA = "rgb_delta"


@dataclass
class TransformParams:
    """Parameters for one invocation of `ColorTransformer.transform`.

    Only the fields relevant to `mode` are read; others are ignored. Ranges:
      - `hue_shift_degrees`: [-180, 180] (wraps around 360°).
      - `brightness_shift` / `saturation_shift`: [-1, 1] (additive on HSV V/S).
      - `rgb_delta_*`: [-255, 255] (clamped after addition).
      - `match_color`, `replace_with`: for REPLACE_MATCHES. Matching is by
        full u16 equality so stp-bit state is respected.
      - `source_color`, `target_color`, `hue_tolerance_degrees`: for
        REPLACE_HUE. Colors whose hue is within ±tolerance of
        `source_color`'s hue get rotated by (target_hue - source_hue);
        saturation and value are preserved.
    """

    mode: TransformMode
    match_color: PsxColor | None = None
    replace_with: PsxColor | None = None
    hue_shift_degrees: float = 0.0
    brightness_shift: float = 0.0
    saturation_shift: float = 0.0
    rgb_delta_r: int = 0
    rgb_delta_g: int = 0
    rgb_delta_b: int = 0
    source_color: PsxColor | None = None
    target_color: PsxColor | None = None
    hue_tolerance_degrees: float = 30.0


class ColorTransformer:
    """Applies a `TransformParams` to a single `PsxColor`.

    Quantizes back to the PSX 5-bit grid on the way out, preserving the stp
    (transparency) bit from the input color. Entries whose full u16 value
    is 0 are the PSX transparency sentinel — they're passed through
    untouched so that HSV shifts don't silently promote a row's transparent
    index to a solid-colored pixel (the CLUT would stop rendering as
    transparent in-game).

    Delegates 5-5-5 ↔ 8-8-8 conversion + u16 packing to the injected
    `ColorConverter`: that class owns the authoritative PSX-grid math, and
    duplicating it here made the two implementations drift whenever one of
    them was fixed.
    """

    _TRANSPARENT_SENTINEL = 0

    # Below this saturation, a color's hue is numerical noise — the RGB→HSV
    # conversion yields essentially arbitrary angles for near-grays. Used to
    # gate REPLACE_HUE so we don't shift whites/grays along with chromatic
    # colors that happen to share their (meaningless) hue.
    _HUE_SATURATION_FLOOR = 0.05

    def __init__(self, color_converter: ColorConverter) -> None:
        self._converter = color_converter

    def transform(self, color: PsxColor, params: TransformParams) -> PsxColor:
        if color.value == self._TRANSPARENT_SENTINEL:
            return color

        if params.mode == TransformMode.REPLACE_MATCHES:
            return self._replace(color, params)

        if params.mode == TransformMode.REPLACE_HUE:
            return self._replace_hue(color, params)

        rgb = self._converter.psx_to_rgb(color)
        r, g, b = rgb.r, rgb.g, rgb.b

        if params.mode == TransformMode.RGB_DELTA:
            r = self.clamp_u8(r + params.rgb_delta_r)
            g = self.clamp_u8(g + params.rgb_delta_g)
            b = self.clamp_u8(b + params.rgb_delta_b)
        else:
            h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)

            if params.mode == TransformMode.SHIFT_HUE:
                h = (h + params.hue_shift_degrees / 360.0) % 1.0
            elif params.mode == TransformMode.SHIFT_SATURATION:
                s = self.clamp_unit(s + params.saturation_shift)
            elif params.mode == TransformMode.SHIFT_BRIGHTNESS:
                v = self.clamp_unit(v + params.brightness_shift)

            r_f, g_f, b_f = colorsys.hsv_to_rgb(h, s, v)
            r, g, b = round(r_f * 255), round(g_f * 255), round(b_f * 255)

        return self._converter.rgb_to_psx(Rgb888(r=r, g=g, b=b), stp=color.stp)

    def _replace(self, color: PsxColor, params: TransformParams) -> PsxColor:
        if params.match_color is None or params.replace_with is None:
            return color

        if color.value == params.match_color.value:
            return params.replace_with

        return color

    def _replace_hue(self, color: PsxColor, params: TransformParams) -> PsxColor:
        """Rotate hues inside a tolerance band of `source_color`'s hue.

        Preserves saturation and value, so a paintjob's gradient structure
        survives the swap — "replace green with red" keeps the relative
        shading between the greens intact when they land in the reds.
        """
        if params.source_color is None or params.target_color is None:
            return color

        src_rgb = self._converter.psx_to_rgb(params.source_color)
        src_h, src_s, _ = colorsys.rgb_to_hsv(
            src_rgb.r / 255.0, src_rgb.g / 255.0, src_rgb.b / 255.0,
        )
        if src_s < self._HUE_SATURATION_FLOOR:
            # Source is near-gray — no meaningful hue to match against.
            return color

        tgt_rgb = self._converter.psx_to_rgb(params.target_color)
        tgt_h, _, _ = colorsys.rgb_to_hsv(
            tgt_rgb.r / 255.0, tgt_rgb.g / 255.0, tgt_rgb.b / 255.0,
        )

        rgb = self._converter.psx_to_rgb(color)
        h, s, v = colorsys.rgb_to_hsv(rgb.r / 255.0, rgb.g / 255.0, rgb.b / 255.0)
        if s < self._HUE_SATURATION_FLOOR:
            return color

        tolerance = max(0.0, min(180.0, params.hue_tolerance_degrees)) / 360.0
        if self.hue_distance(h, src_h) > tolerance:
            return color

        delta = tgt_h - src_h
        new_h = (h + delta) % 1.0

        r_f, g_f, b_f = colorsys.hsv_to_rgb(new_h, s, v)
        return self._converter.rgb_to_psx(
            Rgb888(r=round(r_f * 255), g=round(g_f * 255), b=round(b_f * 255)),
            stp=color.stp,
        )

    @staticmethod
    def hue_distance(a: float, b: float) -> float:
        """Shortest angular distance between two hues in [0, 1) space, in [0, 0.5]."""
        d = abs(a - b) % 1.0
        return min(d, 1.0 - d)

    @staticmethod
    def clamp_u8(v: int) -> int:
        return max(0, min(255, v))

    @staticmethod
    def clamp_unit(v: float) -> float:
        return max(0.0, min(1.0, v))
