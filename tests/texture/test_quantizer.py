# coding: utf-8

import pytest

pytest.importorskip("PIL")

from PIL import Image

from paintjob_designer.color.converter import ColorConverter
from paintjob_designer.texture.quantizer import TextureQuantizer


def _solid_rgba(width: int, height: int, rgba: tuple[int, int, int, int]) -> Image.Image:
    img = Image.new("RGBA", (width, height), rgba)
    return img


class TestTextureQuantizer:

    def setup_method(self) -> None:
        self._quantizer = TextureQuantizer(ColorConverter())

    def test_output_dimensions_match_input(self) -> None:
        img = _solid_rgba(8, 4, (255, 0, 0, 255))

        result = self._quantizer.quantize(img, 8, 4)

        assert result.width == 8
        assert result.height == 4

    def test_palette_is_always_16_entries(self) -> None:
        img = _solid_rgba(4, 4, (255, 0, 0, 255))

        result = self._quantizer.quantize(img, 4, 4)

        assert len(result.palette) == 16

    def test_palette_slot_zero_is_transparent_sentinel(self) -> None:
        img = _solid_rgba(4, 4, (255, 0, 0, 255))

        result = self._quantizer.quantize(img, 4, 4)

        assert result.palette[0].value == 0x0000

    def test_solid_opaque_color_packs_into_nonzero_index(self) -> None:
        # Every pixel is fully opaque red, so every nibble should be a
        # non-zero palette index (since index 0 is reserved for transparent).
        img = _solid_rgba(4, 2, (255, 0, 0, 255))

        result = self._quantizer.quantize(img, 4, 2)

        for byte in result.pixels:
            low = byte & 0x0F
            high = (byte >> 4) & 0x0F
            assert low != 0
            assert high != 0

    def test_transparent_pixels_map_to_index_zero(self) -> None:
        # Fully transparent canvas → every pixel must be index 0.
        img = _solid_rgba(4, 2, (255, 0, 0, 0))

        result = self._quantizer.quantize(img, 4, 2)

        for byte in result.pixels:
            assert byte == 0x00

    def test_packed_buffer_is_half_the_pixel_count(self) -> None:
        img = _solid_rgba(8, 4, (128, 128, 128, 255))

        result = self._quantizer.quantize(img, 8, 4)

        assert len(result.pixels) == (8 * 4) // 2

    def test_low_nibble_stores_left_pixel(self) -> None:
        # Left column transparent, right column opaque — left nibble = 0,
        # right nibble != 0 for every byte. Validates the pack order the
        # PSX GPU expects.
        img = Image.new("RGBA", (2, 1), (0, 0, 0, 0))
        img.putpixel((1, 0), (255, 0, 0, 255))

        result = self._quantizer.quantize(img, 2, 1)

        assert len(result.pixels) == 1
        byte = result.pixels[0]
        assert (byte & 0x0F) == 0              # left pixel: transparent (index 0)
        assert (byte >> 4) & 0x0F != 0         # right pixel: opaque

    def test_opaque_color_round_trips_through_palette(self) -> None:
        # Put a single opaque pixel in and check that the index it ends up
        # on decodes back to (roughly) the input color. PSX 15-bit BGR is
        # lossy, so we compare after snapping through the converter.
        img = Image.new("RGBA", (2, 1), (0, 0, 0, 0))
        img.putpixel((0, 0), (255, 128, 64, 255))

        result = self._quantizer.quantize(img, 2, 1)

        index = result.pixels[0] & 0x0F
        assert index != 0
        color = result.palette[index]
        # 15-bit BGR with 5 bits per channel → snaps to nearest 8-level step.
        assert abs(color.r5 - (255 >> 3)) <= 1
        assert abs(color.g5 - (128 >> 3)) <= 1
        assert abs(color.b5 - (64 >> 3)) <= 1

    def test_rejects_odd_width(self) -> None:
        img = _solid_rgba(3, 2, (255, 0, 0, 255))

        with pytest.raises(ValueError, match="even"):
            self._quantizer.quantize(img, 3, 2)

    def test_rejects_zero_dimensions(self) -> None:
        img = _solid_rgba(4, 4, (255, 0, 0, 255))

        with pytest.raises(ValueError, match="positive"):
            self._quantizer.quantize(img, 0, 4)

    def test_rejects_image_size_mismatch(self) -> None:
        img = _solid_rgba(4, 4, (255, 0, 0, 255))

        with pytest.raises(ValueError, match="expected"):
            self._quantizer.quantize(img, 8, 4)

    def test_accepts_non_rgba_input_by_converting(self) -> None:
        # A plain "RGB" mode image has no alpha channel — all pixels should
        # treat as opaque and the quantizer shouldn't crash on the conversion.
        img = Image.new("RGB", (4, 2), (0, 200, 0))

        result = self._quantizer.quantize(img, 4, 2)

        # Every pixel opaque → no index 0 in the pixel buffer.
        for byte in result.pixels:
            assert (byte & 0x0F) != 0
            assert ((byte >> 4) & 0x0F) != 0

    def test_unused_palette_slots_are_transparent_padding(self) -> None:
        # A 2-color image only fills 2 non-transparent slots; the remaining
        # slots should be 0x0000 so the exported CLUT has no junk.
        img = Image.new("RGBA", (4, 2), (255, 0, 0, 255))
        for x in range(2):
            img.putpixel((x, 0), (0, 0, 255, 255))

        result = self._quantizer.quantize(img, 4, 2)

        used_indices = set()
        for byte in result.pixels:
            used_indices.add(byte & 0x0F)
            used_indices.add((byte >> 4) & 0x0F)

        for i in range(16):
            if i not in used_indices and i != 0:
                assert result.palette[i].value == 0x0000
