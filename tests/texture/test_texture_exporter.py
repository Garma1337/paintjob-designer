# coding: utf-8

import pytest
from PIL import Image

from paintjob_designer.color.converter import ColorConverter
from paintjob_designer.models import PsxColor
from paintjob_designer.texture.four_bpp_codec import FourBppCodec
from paintjob_designer.texture.texture_exporter import TextureExporter


@pytest.fixture
def texture_exporter():
    return TextureExporter(ColorConverter(), FourBppCodec())


def _psx(r5: int, g5: int, b5: int) -> PsxColor:
    """Build a PsxColor from 5-bit components (BGR15 packing)."""
    return PsxColor(value=(b5 << 10) | (g5 << 5) | r5)


def _opaque_clut() -> list[PsxColor]:
    # 16 distinct opaque colors: index i → (i, i, i) in 5-bit. Index 0 has
    # the stencil bit set so it's not treated as transparent.
    clut: list[PsxColor] = [PsxColor(value=0x8000)]
    for i in range(1, 16):
        clut.append(_psx(i, i, i))
    return clut


class TestRoundTrip:

    def test_decodes_packed_indices_to_rgba(self, texture_exporter):
        # 4×1 image: indices [1, 2, 3, 4] packed as bytes [0x21, 0x43].
        pixels = bytes([0x21, 0x43])
        clut = _opaque_clut()

        image = texture_exporter.to_image(pixels, 4, 1, clut)

        assert image.size == (4, 1)
        assert image.mode == "RGBA"
        # Each PSX 5-bit component expands to 8 bits via x*8 + x//4 (or close).
        # We assert the channels are non-zero / monotonic — actual conversion
        # belongs to ColorConverter's own tests.
        raw = image.tobytes()
        rgba = [tuple(raw[i:i + 4]) for i in range(0, len(raw), 4)]
        rs = [px[0] for px in rgba]
        assert rs == sorted(rs)  # indices increase, so red component increases
        assert all(px[3] == 0xFF for px in rgba)

    def test_index_zero_is_transparent_when_clut_entry_is(self, texture_exporter):
        # Index 0 with value 0 (stp=0, rgb=0) → fully transparent.
        pixels = bytes([0x00])  # two zero indices
        clut = [PsxColor(value=0)] + [_psx(31, 0, 0)] * 15

        image = texture_exporter.to_image(pixels, 2, 1, clut)

        raw = image.tobytes()
        rgba = [tuple(raw[i:i + 4]) for i in range(0, len(raw), 4)]
        assert rgba[0][3] == 0
        assert rgba[1][3] == 0

    def test_non_zero_index_pointing_at_transparent_slot_stays_transparent(
        self, texture_exporter,
    ):
        # Even index 5 is transparent if clut[5] is the transparent sentinel.
        pixels = bytes([0x55])  # two index-5s
        clut = [_psx(31, 0, 0)] * 16
        clut[5] = PsxColor(value=0)

        image = texture_exporter.to_image(pixels, 2, 1, clut)

        raw = image.tobytes()
        rgba = [tuple(raw[i:i + 4]) for i in range(0, len(raw), 4)]
        assert rgba[0][3] == 0
        assert rgba[1][3] == 0


class TestRowOrdering:

    def test_pixels_lay_out_row_major(self, texture_exporter):
        # 2×2: row 0 = [1, 2], row 1 = [3, 4]. Packed: row0=0x21, row1=0x43.
        pixels = bytes([0x21, 0x43])
        clut = _opaque_clut()

        image = texture_exporter.to_image(pixels, 2, 2, clut)

        raw = image.tobytes()
        rgba = [tuple(raw[i:i + 4]) for i in range(0, len(raw), 4)]
        # Row-major: [(0,0), (1,0), (0,1), (1,1)] correspond to indices [1,2,3,4]
        assert rgba[0][0] < rgba[1][0] < rgba[2][0] < rgba[3][0]


class TestValidation:

    def test_zero_dims_rejected(self, texture_exporter):
        with pytest.raises(ValueError, match="positive"):
            texture_exporter.to_image(b"", 0, 0, _opaque_clut())

    def test_too_few_pixel_bytes_rejected(self, texture_exporter):
        # 4×1 needs 2 bytes; pass 1.
        with pytest.raises(ValueError):
            texture_exporter.to_image(bytes([0x12]), 4, 1, _opaque_clut())
