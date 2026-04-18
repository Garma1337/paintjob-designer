# coding: utf-8

import pytest

from paintjob_designer.core.binary_reader import BinaryReader


class TestPrimitiveReads:

    def test_reads_u1(self):
        r = BinaryReader(b"\x01\x02\xff")

        assert r.u1() == 1
        assert r.u1() == 2
        assert r.u1() == 0xFF

    def test_reads_u2_little_endian(self):
        r = BinaryReader(b"\x34\x12\xFF\x7F")

        assert r.u2() == 0x1234
        assert r.u2() == 0x7FFF

    def test_reads_u4_little_endian(self):
        r = BinaryReader(b"\x78\x56\x34\x12")

        assert r.u4() == 0x12345678

    def test_reads_u4_big_endian(self):
        r = BinaryReader(b"\x12\x34\x56\x78")

        assert r.u4_be() == 0x12345678

    def test_reads_signed_short(self):
        r = BinaryReader(b"\xFF\xFF\x01\x00")

        assert r.s2() == -1
        assert r.s2() == 1

    def test_reads_signed_int(self):
        r = BinaryReader(b"\xFF\xFF\xFF\xFF")

        assert r.s4() == -1


class TestCursor:

    def test_position_tracks_reads(self):
        r = BinaryReader(b"\x00\x00\x00\x00\x00\x00")

        assert r.position == 0
        r.u2()
        assert r.position == 2
        r.u4()
        assert r.position == 6

    def test_skip_advances_cursor(self):
        r = BinaryReader(b"\x00\x00\x05")

        r.skip(2)
        assert r.u1() == 5

    def test_seek_moves_cursor(self):
        r = BinaryReader(b"\x00\x00\x00\x05")

        r.seek(3)
        assert r.u1() == 5

    def test_seek_rejects_out_of_range(self):
        r = BinaryReader(b"\x00")

        with pytest.raises(ValueError, match="seek out of range"):
            r.seek(-1)

        with pytest.raises(ValueError, match="seek out of range"):
            r.seek(99)

    def test_remaining_reflects_cursor(self):
        r = BinaryReader(b"\x00\x00\x00\x00")

        assert r.remaining() == 4
        r.u2()
        assert r.remaining() == 2


class TestReadErrors:

    def test_read_past_end_raises(self):
        r = BinaryReader(b"\x01")

        with pytest.raises(EOFError, match="read past end"):
            r.u4()


class TestStrings:

    def test_reads_fixed_strz_stops_at_null(self):
        r = BinaryReader(b"crash\x00\x00\x00\x00\x00")

        assert r.read_strz(9) == "crash"
        assert r.position == 9

    def test_reads_fixed_strz_consumes_full_size_when_unterminated(self):
        r = BinaryReader(b"abcdef")

        assert r.read_strz(6) == "abcdef"
        assert r.position == 6
