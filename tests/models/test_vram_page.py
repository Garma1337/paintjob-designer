# coding: utf-8

from paintjob_designer.models import VramPage


class TestDefaults:

    def test_default_buffer_size_is_one_megabyte(self):
        # 1024 × 512 × 2 bytes = 1 048 576. Core PSX VRAM invariant.
        page = VramPage()

        assert page.byte_size == VramPage.WIDTH * VramPage.HEIGHT * VramPage.BYTES_PER_PIXEL
        assert page.byte_size == 1024 * 512 * 2

    def test_default_buffer_is_all_zero(self):
        page = VramPage()

        assert all(b == 0 for b in page.data)

    def test_each_instance_gets_its_own_buffer(self):
        # The `field(default_factory=...)` lambda must allocate per-instance;
        # accidentally sharing a class-level default would silently leak
        # edits across pages.
        page_a = VramPage()
        page_b = VramPage()

        page_a.data[0] = 0x42

        assert page_b.data[0] == 0


class TestU16Read:

    def test_reads_little_endian_u16(self):
        page = VramPage()
        page.data[0] = 0x34
        page.data[1] = 0x12

        assert page.u16_at(0, 0) == 0x1234

    def test_addresses_row_major(self):
        # Row y=1 starts at offset `WIDTH * BYTES_PER_PIXEL`.
        page = VramPage()
        row_start = VramPage.WIDTH * VramPage.BYTES_PER_PIXEL
        page.data[row_start] = 0xFF
        page.data[row_start + 1] = 0x7F

        assert page.u16_at(0, 1) == 0x7FFF

    def test_reads_correct_column(self):
        # Column x=5 is 10 bytes into the row (2 bytes per pixel).
        page = VramPage()
        page.data[10] = 0xEF
        page.data[11] = 0xBE

        assert page.u16_at(5, 0) == 0xBEEF

    def test_transparent_sentinel(self):
        # All-zero u16 is the PSX transparency marker; confirm it reads as 0.
        page = VramPage()

        assert page.u16_at(100, 50) == 0
