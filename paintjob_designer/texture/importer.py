# coding: utf-8

from enum import Enum
from pathlib import Path

from PIL import Image

from paintjob_designer.texture.quantizer import QuantizedTexture, TextureQuantizer


class SizeMismatchMode(Enum):
    """How to handle a source image that doesn't match the target dimensions."""

    REJECT = "reject"
    SCALE = "scale"       # Lanczos-resize to target (ignores aspect ratio)
    CENTER_CROP = "crop"  # Center-crop; requires source >= target on both axes


class TextureImporter:
    """Loads a PNG file and produces a target-sized `QuantizedTexture`.

    Separates file I/O + resize policy from the quantization step so the
    pure quantizer stays easy to test. The UI layer passes a user-chosen
    `SizeMismatchMode` through to this class; the class raises a clear
    `ValueError` when the policy can't be satisfied (e.g. crop requested
    on a too-small source).
    """

    def __init__(self, quantizer: TextureQuantizer) -> None:
        self._quantizer = quantizer

    def import_from_path(
        self,
        path: Path,
        width: int,
        height: int,
        mode: SizeMismatchMode = SizeMismatchMode.REJECT,
    ) -> QuantizedTexture:
        """Open `path`, resolve size mismatches via `mode`, return a quantized texture."""
        with Image.open(path) as source:
            prepared = self._prepare(source, width, height, mode)
            return self._quantizer.quantize(prepared, width, height)

    def _prepare(
        self,
        source: Image.Image,
        width: int,
        height: int,
        mode: SizeMismatchMode,
    ) -> Image.Image:
        rgba = source.convert("RGBA")

        if rgba.size == (width, height):
            return rgba

        if mode is SizeMismatchMode.REJECT:
            raise ValueError(
                f"Source image is {rgba.size[0]}x{rgba.size[1]} but target "
                f"is {width}x{height}; choose 'scale' or 'crop' to import anyway",
            )

        if mode is SizeMismatchMode.SCALE:
            return rgba.resize((width, height), Image.Resampling.LANCZOS)

        if mode is SizeMismatchMode.CENTER_CROP:
            sw, sh = rgba.size
            if sw < width or sh < height:
                raise ValueError(
                    f"Can't center-crop {sw}x{sh} to {width}x{height}; "
                    f"source must be >= target on both axes",
                )

            left = (sw - width) // 2
            top = (sh - height) // 2
            return rgba.crop((left, top, left + width, top + height))

        raise ValueError(f"Unknown size-mismatch mode: {mode!r}")
