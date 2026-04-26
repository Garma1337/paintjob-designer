# coding: utf-8

from PIL import Image

from paintjob_designer.models import Palette
from paintjob_designer.texture.texture_quantizer import TextureQuantizer


class PaletteFromImageCreator:
    """Quantizes any RGBA image down to a saved 16-color PSX palette.

    Reuses `TextureQuantizer` for the colour reduction (giving identical
    palette behaviour to a textured slot import) and discards the pixel
    payload — only the 16-entry CLUT is kept.

    Source images don't have to match a slot's pixel dimensions: the
    quantizer is fed the raw image at its native size, so palette quality
    isn't degraded by an arbitrary resize policy.
    """

    # Quantizer requires 4bpp-friendly width (multiple of 2). Pad to even.
    _MIN_WIDTH = 2

    def __init__(self, quantizer: TextureQuantizer) -> None:
        self._quantizer = quantizer

    def create(self, image: Image.Image, name: str) -> Palette:
        prepared = self._prepare(image)
        quantized = self._quantizer.quantize(
            prepared, prepared.size[0], prepared.size[1],
        )

        return Palette(name=name.strip(), colors=list(quantized.palette))

    def _prepare(self, image: Image.Image) -> Image.Image:
        rgba = image.convert("RGBA")
        width, height = rgba.size

        if width < self._MIN_WIDTH or width % 2 != 0:
            new_width = max(self._MIN_WIDTH, width + (width % 2))
            padded = Image.new("RGBA", (new_width, height), (0, 0, 0, 0))
            padded.paste(rgba, (0, 0))
            return padded

        return rgba
