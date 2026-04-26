# coding: utf-8

from dataclasses import dataclass

from paintjob_designer.models.color import PsxColor


@dataclass
class QuantizedTexture:
    """PSX-ready 4bpp texture: packed pixel indices + 16-entry CLUT."""
    width: int
    height: int
    pixels: bytes
    palette: list[PsxColor]
