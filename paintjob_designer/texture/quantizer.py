# coding: utf-8

from dataclasses import dataclass

from PIL import Image

from paintjob_designer.color.converter import ColorConverter
from paintjob_designer.models import PsxColor, Rgb888


@dataclass
class QuantizedTexture:
    """PSX-ready 4bpp texture: packed pixel indices + 16-entry CLUT.

    `pixels` is the 4bpp packed pixel buffer — two pixels per byte, low
    nibble = left pixel, matching the vanilla CTR texture layout the GPU
    samples. Size is `(width * height) / 2` bytes; width must be even.

    `palette` always has exactly 16 entries. Index 0 is the PSX
    per-pixel transparency sentinel (value `0x0000`); the remaining 15
    slots hold colors quantized from the source image.
    """
    width: int
    height: int
    pixels: bytes
    palette: list[PsxColor]


class TextureQuantizer:
    """Converts an RGBA image into PSX 4bpp pixels + a 16-entry CLUT.

    Reserves palette slot 0 for transparency (value `0x0000`) following
    the PSX convention the in-race renderer uses; pixels with alpha
    below the threshold map to index 0, fully-opaque pixels quantize
    into slots 1..15. Source images must already match the target
    dimensions — scaling / cropping happens in the import dialog,
    not here, so this class stays pure and trivially testable.
    """

    _ALPHA_THRESHOLD = 128
    _PALETTE_SIZE = 16
    _NON_TRANSPARENT_SLOTS = _PALETTE_SIZE - 1  # slot 0 reserved

    def __init__(self, color_converter: ColorConverter) -> None:
        self._converter = color_converter

    def quantize(
        self, image: Image.Image, width: int, height: int,
    ) -> QuantizedTexture:
        """Quantize `image` into a 4bpp PSX texture at `width` x `height`.

        Raises `ValueError` when the image dimensions don't match, or
        when `width` is odd (4bpp packs two pixels per byte, so odd
        widths would straddle bytes across rows and misalign VRAM
        uploads).
        """
        if width <= 0 or height <= 0:
            raise ValueError(f"Width/height must be positive, got {width}x{height}")

        if width % 2 != 0:
            raise ValueError(
                f"4bpp width must be even, got {width} — "
                f"PSX packs 2 pixels per byte",
            )

        rgba = image.convert("RGBA")
        if rgba.size != (width, height):
            raise ValueError(
                f"Image is {rgba.size[0]}x{rgba.size[1]}, expected "
                f"{width}x{height} — resize/crop before quantizing",
            )

        indices, palette = self._build_palette_and_indices(rgba)
        pixels = self._pack_4bpp(indices, width, height)

        return QuantizedTexture(
            width=width, height=height, pixels=pixels, palette=palette,
        )

    def _build_palette_and_indices(
        self, rgba: Image.Image,
    ) -> tuple[list[int], list[PsxColor]]:
        """Quantize the opaque pixels into 15 colors, reserving slot 0 for transparent.

        PIL's `quantize` handles the palette clustering; we shift its
        indices up by one so index 0 stays free, then re-map any pixel
        whose source alpha is below the threshold down to index 0.
        """
        # Quantize as RGB (alpha ignored); we'll re-merge alpha after.
        rgb = rgba.convert("RGB")
        quantized = rgb.quantize(
            colors=self._NON_TRANSPARENT_SLOTS,
            method=Image.Quantize.MEDIANCUT,
            dither=Image.Dither.NONE,
        )

        pil_palette_rgb = self._extract_pil_palette(quantized)

        # Shift: PIL's 0..14 become our 1..15 so index 0 stays transparent.
        source_indices = quantized.tobytes()
        alpha_bytes = rgba.split()[3].tobytes()

        indices: list[int] = []
        for i, alpha in enumerate(alpha_bytes):
            if alpha < self._ALPHA_THRESHOLD:
                indices.append(0)
            else:
                indices.append(source_indices[i] + 1)

        palette: list[PsxColor] = [PsxColor(value=0)]  # slot 0: transparent
        for r, g, b in pil_palette_rgb:
            palette.append(self._converter.rgb_to_psx(Rgb888(r=r, g=g, b=b)))

        # Pad if PIL returned fewer than 15 colors (small / low-color images).
        while len(palette) < self._PALETTE_SIZE:
            palette.append(PsxColor(value=0))

        return indices, palette

    def _extract_pil_palette(self, quantized: Image.Image) -> list[tuple[int, int, int]]:
        """Read PIL's packed palette bytes into RGB triples.

        `quantized.getpalette()` returns a flat list of `3 * 256` ints (even
        if the image uses fewer colors); we slice to the number of distinct
        entries the image actually references so we don't pad our 15-slot
        space with junk colors.
        """
        raw = quantized.getpalette()
        if raw is None:
            return []

        # Distinct indices the image actually uses. `getextrema` on a palette
        # image returns (min, max) of indices — max + 1 is the used count.
        min_idx, max_idx = quantized.getextrema()
        used = max_idx + 1 if max_idx is not None else 0
        used = min(used, self._NON_TRANSPARENT_SLOTS)

        return [
            (raw[i * 3], raw[i * 3 + 1], raw[i * 3 + 2])
            for i in range(used)
        ]

    def _pack_4bpp(self, indices: list[int], width: int, height: int) -> bytes:
        """Pack a list of 0..15 indices into 4bpp bytes, two pixels per byte.

        Low nibble = left pixel, high nibble = right pixel — the order the
        PSX GPU samples when reading a 4bpp texture page.
        """
        if len(indices) != width * height:
            raise ValueError(
                f"Expected {width * height} indices, got {len(indices)}",
            )

        out = bytearray(width * height // 2)
        for i in range(0, len(indices), 2):
            low = indices[i] & 0x0F
            high = indices[i + 1] & 0x0F
            out[i // 2] = (high << 4) | low

        return bytes(out)
