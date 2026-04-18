# coding: utf-8

from paintjob_designer.color.converter import ColorConverter
from paintjob_designer.models import BitDepth, PsxColor, SlotRegion, VramPage


class VramRegionDecoder:
    """Writes one `SlotRegion` worth of 4bpp texels into an RGBA atlas buffer.

    Split out of `AtlasRenderer` so the per-region CLUT-indexing loop can be
    tested with synthesized VRAM + CLUT inputs and no full atlas pipeline.

    The atlas this writes into is wider than VRAM by `stretch_x` (currently 4
    for 4bpp texel visibility) — each VRAM u16 contains 4 CLUT indices that
    expand to 4 consecutive atlas pixels.
    """

    BYTES_PER_PIXEL = 4  # RGBA

    def __init__(
        self,
        color_converter: ColorConverter,
        atlas_width: int,
        atlas_height: int,
        stretch_x: int = 4,
    ) -> None:
        self._colors = color_converter
        self._atlas_width = atlas_width
        self._atlas_height = atlas_height
        self._stretch_x = stretch_x

    def decode_into(
        self,
        vram: VramPage,
        region: SlotRegion,
        clut: list[int],
        rgba: bytearray,
    ) -> None:
        """Walk `region`'s VRAM cells and emit `stretch_x` atlas pixels per cell.

        Only 4bpp regions are supported; 8bpp/16bpp regions are skipped and
        the atlas keeps whatever the baseline pass wrote there. That's
        deliberate — every kart-paintjob slot we care about is 4bpp, and
        mixing bit depths in one decoder would balloon it without payoff.
        """
        if region.bpp != BitDepth.Bit4:
            return

        stretch_x = self._stretch_x
        bpp_out = self.BYTES_PER_PIXEL

        for row in range(region.vram_height):
            atlas_y = region.vram_y + row
            if atlas_y >= self._atlas_height:
                break

            atlas_row_base = atlas_y * self._atlas_width * bpp_out
            vram_row_base = atlas_y * VramPage.WIDTH * VramPage.BYTES_PER_PIXEL

            for col in range(region.vram_width):
                vram_x = region.vram_x + col
                if vram_x >= VramPage.WIDTH:
                    break

                off = vram_row_base + vram_x * VramPage.BYTES_PER_PIXEL
                u16 = vram.data[off] | (vram.data[off + 1] << 8)

                atlas_x = vram_x * stretch_x
                for nibble in range(stretch_x):
                    index = (u16 >> (nibble * 4)) & 0xF
                    pixel = self._psx_to_rgba(clut[index])
                    atlas_off = atlas_row_base + (atlas_x + nibble) * bpp_out
                    rgba[atlas_off:atlas_off + bpp_out] = pixel

    def _psx_to_rgba(self, value: int) -> bytes:
        # Mirrors the LUT path for value==0 (transparent sentinel) while
        # reusing ColorConverter's bit math for the general case — the
        # per-region path is colder than the baseline decode so we don't
        # bother with the vectorized LUT here.
        if value == 0:
            return b"\x00\x00\x00\x00"

        rgb = self._colors.psx_to_rgb(PsxColor(value=value))
        return bytes((rgb.r, rgb.g, rgb.b, 0xFF))
