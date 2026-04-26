# coding: utf-8

from PIL import Image

from paintjob_designer.color.converter import ColorConverter
from paintjob_designer.models import PsxColor
from paintjob_designer.texture.four_bpp_codec import FourBppCodec


class TextureExporter:
    """Decodes 4bpp packed pixel data + a 16-entry CLUT into an RGBA `PIL.Image`.

    Inverse of `TextureQuantizer.quantize` — round-trips a slot's pixels back
    to a PNG so artists can edit in their tool of choice and re-import.
    """

    def __init__(
        self, color_converter: ColorConverter, codec: FourBppCodec,
    ) -> None:
        self._converter = color_converter
        self._codec = codec

    def to_image(
        self,
        pixels: bytes,
        width: int,
        height: int,
        clut: list[PsxColor],
    ) -> Image.Image:
        if width <= 0 or height <= 0:
            raise ValueError(f"Width/height must be positive, got {width}x{height}")

        indices = self._codec.unpack(pixels, width * height)

        rgba = bytearray(width * height * 4)
        for i, idx in enumerate(indices):
            color = clut[idx] if idx < len(clut) else PsxColor()
            if color.is_transparent:
                continue

            rgb = self._converter.psx_to_rgb(color)
            base = i * 4
            rgba[base] = rgb.r
            rgba[base + 1] = rgb.g
            rgba[base + 2] = rgb.b
            rgba[base + 3] = 0xFF

        return Image.frombytes("RGBA", (width, height), bytes(rgba))
