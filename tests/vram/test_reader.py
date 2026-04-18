# coding: utf-8

import struct

import pytest

from paintjob_designer.models import VramPage
from tests.conftest import build_tim, build_vrm_bytes


def _solid_u16_block(value: int, width: int, height: int) -> bytes:
    return struct.pack("<H", value) * (width * height)


class TestEmptyInputs:

    def test_empty_stream_yields_blank_vram(self, vram_reader):
        page = vram_reader.read(build_vrm_bytes([]))

        assert page.byte_size == VramPage.WIDTH * VramPage.HEIGHT * 2
        # First pixel untouched.
        assert page.u16_at(0, 0) == 0

    def test_missing_tim_magic_raises(self, vram_reader):
        # Stream with one "TIM" whose magic is wrong.
        bad_tim = struct.pack("<II", 0xDEADBEEF, 0)
        with pytest.raises(ValueError, match="TIM magic"):
            vram_reader.read(build_vrm_bytes([bad_tim]))


class TestSingleBlock:

    def test_image_block_lands_at_origin(self, vram_reader):
        # 4x2 block of 0xBEEF at (100, 50).
        image = {
            "origin_x": 100, "origin_y": 50,
            "width": 4, "height": 2,
            "pixels": _solid_u16_block(0xBEEF, 4, 2),
        }
        data = build_vrm_bytes([build_tim(bpp=2, image=image)])

        page = vram_reader.read(data)

        assert page.u16_at(100, 50) == 0xBEEF
        assert page.u16_at(103, 51) == 0xBEEF
        # Adjacent pixels untouched.
        assert page.u16_at(99, 50) == 0
        assert page.u16_at(104, 50) == 0

    def test_clut_block_precedes_image_block(self, vram_reader):
        # CLUT at (0, 0), image at (256, 128). Confirm both are blitted.
        clut = {
            "origin_x": 0, "origin_y": 0, "width": 16, "height": 1,
            "pixels": struct.pack("<H", 0x1234) * 16,
        }
        image = {
            "origin_x": 256, "origin_y": 128, "width": 8, "height": 4,
            "pixels": _solid_u16_block(0x5678, 8, 4),
        }
        data = build_vrm_bytes([build_tim(bpp=0, image=image, clut=clut)])

        page = vram_reader.read(data)

        assert page.u16_at(0, 0) == 0x1234
        assert page.u16_at(15, 0) == 0x1234
        assert page.u16_at(256, 128) == 0x5678
        assert page.u16_at(263, 131) == 0x5678


class TestMultipleTims:

    def test_stream_of_multiple_tims_are_all_blitted(self, vram_reader):
        tim_a = build_tim(bpp=2, image={
            "origin_x": 0, "origin_y": 0, "width": 2, "height": 1,
            "pixels": _solid_u16_block(0x1111, 2, 1),
        })
        tim_b = build_tim(bpp=2, image={
            "origin_x": 512, "origin_y": 256, "width": 2, "height": 1,
            "pixels": _solid_u16_block(0x2222, 2, 1),
        })
        data = build_vrm_bytes([tim_a, tim_b])

        page = vram_reader.read(data)

        assert page.u16_at(0, 0) == 0x1111
        assert page.u16_at(512, 256) == 0x2222


class TestBlitInto:

    def test_blit_into_merges_into_existing_page(self, vram_reader):
        page = VramPage()
        tim_a = build_tim(bpp=2, image={
            "origin_x": 0, "origin_y": 0, "width": 1, "height": 1,
            "pixels": struct.pack("<H", 0xAAAA),
        })
        vram_reader.blit_into(build_vrm_bytes([tim_a]), page)

        tim_b = build_tim(bpp=2, image={
            "origin_x": 10, "origin_y": 10, "width": 1, "height": 1,
            "pixels": struct.pack("<H", 0xBBBB),
        })
        vram_reader.blit_into(build_vrm_bytes([tim_b]), page)

        assert page.u16_at(0, 0) == 0xAAAA
        assert page.u16_at(10, 10) == 0xBBBB

    def test_overlapping_writes_overwrite(self, vram_reader):
        page = VramPage()
        first = build_tim(bpp=2, image={
            "origin_x": 0, "origin_y": 0, "width": 1, "height": 1,
            "pixels": struct.pack("<H", 0x1111),
        })
        second = build_tim(bpp=2, image={
            "origin_x": 0, "origin_y": 0, "width": 1, "height": 1,
            "pixels": struct.pack("<H", 0x2222),
        })
        vram_reader.blit_into(build_vrm_bytes([first]), page)
        vram_reader.blit_into(build_vrm_bytes([second]), page)

        assert page.u16_at(0, 0) == 0x2222


class TestClipping:

    def test_block_past_vram_bounds_is_clipped_not_crashed(self, vram_reader):
        # Height pushes us past row 512; those rows should be silently dropped.
        image = {
            "origin_x": 0, "origin_y": 510,
            "width": 4, "height": 10,
            "pixels": _solid_u16_block(0xCAFE, 4, 10),
        }
        data = build_vrm_bytes([build_tim(bpp=2, image=image)])

        page = vram_reader.read(data)

        # Rows 510 and 511 are inside VRAM and should be populated.
        assert page.u16_at(0, 510) == 0xCAFE
        assert page.u16_at(0, 511) == 0xCAFE
