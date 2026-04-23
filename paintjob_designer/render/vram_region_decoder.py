# coding: utf-8

from paintjob_designer.color.converter import ColorConverter
from paintjob_designer.constants import PSX_RGB_MASK, RGB_COMPONENT_MAX
from paintjob_designer.models import BitDepth, PsxColor, SlotRegion, VramPage


class VramRegionDecoder:
    """Writes one `SlotRegion` worth of 4bpp texels into an RGBA atlas buffer."""

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
        """Walk `region`'s VRAM cells and emit `stretch_x` atlas pixels per cell."""
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

    def decode_pixels_into(
        self,
        region: SlotRegion,
        pixel_bytes: bytes,
        clut: list[int],
        rgba: bytearray,
    ) -> bool:
        """Write a paintjob-authored 4bpp pixel payload into the atlas."""
        if region.bpp != BitDepth.Bit4:
            return False

        stretch_x = self._stretch_x
        bpp_out = self.BYTES_PER_PIXEL
        pixel_width = region.vram_width * stretch_x
        bytes_per_row = pixel_width // 2

        if len(pixel_bytes) != bytes_per_row * region.vram_height:
            return False

        atlas_x_base = region.vram_x * stretch_x

        for row in range(region.vram_height):
            atlas_y = region.vram_y + row
            if atlas_y >= self._atlas_height:
                break

            atlas_row_base = atlas_y * self._atlas_width * bpp_out
            byte_row_base = row * bytes_per_row

            for byte_col in range(bytes_per_row):
                byte = pixel_bytes[byte_row_base + byte_col]
                low_index = byte & 0x0F
                high_index = (byte >> 4) & 0x0F

                atlas_x = atlas_x_base + byte_col * 2
                if atlas_x + 1 >= self._atlas_width:
                    break

                atlas_off = atlas_row_base + atlas_x * bpp_out
                rgba[atlas_off:atlas_off + bpp_out] = self._psx_to_rgba(
                    clut[low_index],
                )
                rgba[atlas_off + bpp_out:atlas_off + 2 * bpp_out] = self._psx_to_rgba(
                    clut[high_index],
                )

        return True

    def _psx_to_rgba(self, value: int) -> bytes:
        # Mirrors the LUT: any black texel (RGB 0,0,0) renders transparent
        # in-game regardless of the stp bit, so both 0x0000 and 0x8000
        # become alpha=0 here. ColorConverter handles the non-black cases.
        if (value & PSX_RGB_MASK) == 0:
            return b"\x00\x00\x00\x00"

        rgb = self._colors.psx_to_rgb(PsxColor(value=value))
        return bytes((rgb.r, rgb.g, rgb.b, RGB_COMPONENT_MAX))
