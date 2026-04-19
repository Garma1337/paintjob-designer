# coding: utf-8

import colorsys
from dataclasses import dataclass
from enum import Enum

from paintjob_designer.models import PsxColor


class TransformMode(Enum):
    """Bulk operations the Transform Colors dialog can apply across a scope."""

    REPLACE_MATCHES = "replace_matches"
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


class ColorTransformer:
    """Applies a `TransformParams` to a single `PsxColor`.

    Quantizes back to the PSX 5-bit grid on the way out, preserving the stp
    (transparency) bit from the input color. Entries whose full u16 value is 0
    are the PSX transparency sentinel — they're passed through untouched so
    that HSV shifts don't silently promote a row's transparent index to a
    solid-colored pixel (the CLUT would stop rendering as transparent in-game).
    """

    _TRANSPARENT_SENTINEL = 0

    def transform(self, color: PsxColor, params: TransformParams) -> PsxColor:
        if color.value == self._TRANSPARENT_SENTINEL:
            return color

        if params.mode == TransformMode.REPLACE_MATCHES:
            return self._replace(color, params)

        r, g, b = self._unpack_rgb(color)
        stp = color.stp

        if params.mode == TransformMode.RGB_DELTA:
            r = _clamp_u8(r + params.rgb_delta_r)
            g = _clamp_u8(g + params.rgb_delta_g)
            b = _clamp_u8(b + params.rgb_delta_b)
        else:
            h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)

            if params.mode == TransformMode.SHIFT_HUE:
                h = (h + params.hue_shift_degrees / 360.0) % 1.0
            elif params.mode == TransformMode.SHIFT_SATURATION:
                s = _clamp_unit(s + params.saturation_shift)
            elif params.mode == TransformMode.SHIFT_BRIGHTNESS:
                v = _clamp_unit(v + params.brightness_shift)

            r_f, g_f, b_f = colorsys.hsv_to_rgb(h, s, v)
            r, g, b = round(r_f * 255), round(g_f * 255), round(b_f * 255)

        return self._pack(r, g, b, stp)

    def _replace(self, color: PsxColor, params: TransformParams) -> PsxColor:
        if params.match_color is None or params.replace_with is None:
            return color

        if color.value == params.match_color.value:
            return params.replace_with

        return color

    def _unpack_rgb(self, color: PsxColor) -> tuple[int, int, int]:
        # Bit-replication 5→8 matches `ColorConverter._expand_5_to_8` — we don't
        # inject the converter because the transform module must stay headless /
        # pure-Python for tests and to avoid a DI dependency on a trivial helper.
        return (
            _expand_5_to_8(color.r5),
            _expand_5_to_8(color.g5),
            _expand_5_to_8(color.b5),
        )

    def _pack(self, r: int, g: int, b: int, stp: int) -> PsxColor:
        r5 = (r >> 3) & 0x1F
        g5 = (g >> 3) & 0x1F
        b5 = (b >> 3) & 0x1F
        return PsxColor(value=((stp & 0x1) << 15) | (b5 << 10) | (g5 << 5) | r5)


def _expand_5_to_8(v5: int) -> int:
    return ((v5 << 3) | (v5 >> 2)) & 0xFF


def _clamp_u8(v: int) -> int:
    return max(0, min(255, v))


def _clamp_unit(v: float) -> float:
    return max(0.0, min(1.0, v))
