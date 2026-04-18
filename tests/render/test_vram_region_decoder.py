# coding: utf-8

import struct

from paintjob_designer.models import BitDepth, BlendingMode, SlotRegion, VramPage
from paintjob_designer.render.vram_region_decoder import VramRegionDecoder


def _empty_atlas(w: int, h: int) -> bytearray:
    return bytearray(w * h * 4)


def _vram_with_cells(cells: dict[tuple[int, int], int]) -> VramPage:
    """Write (x, y) → u16 into a fresh VRAM page and return it."""
    page = VramPage()
    for (x, y), value in cells.items():
        off = (y * VramPage.WIDTH + x) * VramPage.BYTES_PER_PIXEL
        struct.pack_into("<H", page.data, off, value)

    return page


class TestDecodeInto:

    def test_skips_non_4bpp_regions(self, color_converter):
        # An 8bpp region is no-op: decoder only handles 4bpp.
        atlas_w, atlas_h = 64, 4
        decoder = VramRegionDecoder(color_converter, atlas_w, atlas_h, stretch_x=4)
        vram = _vram_with_cells({(0, 0): 0x7FFF})
        atlas = _empty_atlas(atlas_w, atlas_h)

        region = SlotRegion(
            vram_x=0, vram_y=0, vram_width=1, vram_height=1,
            bpp=BitDepth.Bit8, blending=BlendingMode.Standard,
        )
        decoder.decode_into(vram, region, [0] * 16, atlas)

        # Untouched buffer stays zero.
        assert bytes(atlas) == b"\x00" * len(atlas)

    def test_emits_one_clut_indexed_pixel_per_nibble(self, color_converter):
        # One VRAM u16 = four 4-bit indices = four atlas pixels.
        atlas_w, atlas_h = 16, 1
        decoder = VramRegionDecoder(color_converter, atlas_w, atlas_h, stretch_x=4)
        # Indices 3,2,1,0 packed low→high.
        vram = _vram_with_cells({(0, 0): 0x0123})
        atlas = _empty_atlas(atlas_w, atlas_h)

        # PSX 15-bit layout is [b5 g5 r5] (low bits = red), so:
        #   0x001F = pure red, 0x03E0 = pure green, 0x7C00 = pure blue.
        clut = [0] * 16
        clut[0] = 0x7FFF   # white
        clut[1] = 0x7C00   # blue
        clut[2] = 0x03E0   # green
        clut[3] = 0x001F   # red

        region = SlotRegion(
            vram_x=0, vram_y=0, vram_width=1, vram_height=1,
            bpp=BitDepth.Bit4, blending=BlendingMode.Standard,
        )
        decoder.decode_into(vram, region, clut, atlas)

        # Low nibble (3) is leftmost, so we expect red, green, blue, white.
        assert atlas[0:4]   == bytes((0xFF, 0x00, 0x00, 0xFF))  # red
        assert atlas[4:8]   == bytes((0x00, 0xFF, 0x00, 0xFF))  # green
        assert atlas[8:12]  == bytes((0x00, 0x00, 0xFF, 0xFF))  # blue
        assert atlas[12:16] == bytes((0xFF, 0xFF, 0xFF, 0xFF))  # white

    def test_clut_index_zero_renders_transparent(self, color_converter):
        atlas_w, atlas_h = 4, 1
        decoder = VramRegionDecoder(color_converter, atlas_w, atlas_h, stretch_x=4)
        vram = _vram_with_cells({(0, 0): 0x0000})  # all four nibbles = 0
        atlas = _empty_atlas(atlas_w, atlas_h)
        # Even if CLUT[0] names a non-zero value, the decoder writes the
        # transparent sentinel when the value itself is zero — same contract
        # as the LUT path.
        clut = [0] * 16

        region = SlotRegion(
            vram_x=0, vram_y=0, vram_width=1, vram_height=1,
            bpp=BitDepth.Bit4, blending=BlendingMode.Standard,
        )
        decoder.decode_into(vram, region, clut, atlas)

        assert bytes(atlas) == b"\x00" * len(atlas)
