# coding: utf-8

from dataclasses import dataclass, field


@dataclass
class VramPage:
    """A 1024x512 u16 VRAM buffer (1 MB).

    Pixels are stored raw as little-endian u16s. In 4bpp mode, each u16
    packs four 4-bit CLUT indices (low nibble is the leftmost pixel).
    CLUTs themselves live in the same buffer as runs of 16 u16 entries at
    the coordinates referenced by each face's TextureLayout.

    Interpretation is deferred to consumers — this model just owns the bytes.
    """
    WIDTH = 1024
    HEIGHT = 512
    BYTES_PER_PIXEL = 2

    data: bytearray = field(
        default_factory=lambda: bytearray(
            VramPage.WIDTH * VramPage.HEIGHT * VramPage.BYTES_PER_PIXEL,
        ),
    )

    @property
    def byte_size(self) -> int:
        return len(self.data)

    def u16_at(self, x: int, y: int) -> int:
        offset = (y * self.WIDTH + x) * self.BYTES_PER_PIXEL
        return self.data[offset] | (self.data[offset + 1] << 8)
