# coding: utf-8

from dataclasses import dataclass


@dataclass
class RotatedTexture:
    """Output of `TextureRotator.rotate`: rotated 4bpp pixels + new dimensions."""
    pixels: bytes
    width: int
    height: int
