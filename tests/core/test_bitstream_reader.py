# coding: utf-8

from paintjob_designer.core.bitstream_reader import BitStreamReader
from tests.conftest import encode_bitstream as _encode


class TestTakeBit:

    def test_emits_bits_in_encoding_order(self):
        bits = [1, 0, 1, 1, 0, 0, 1, 0]
        r = BitStreamReader(_encode(bits))

        assert [r.take_bit() for _ in bits] == bits

    def test_crosses_u32_boundary(self):
        # 36 bits -> spans two u32 blocks.
        bits = [1, 0, 1, 0] * 9
        r = BitStreamReader(_encode(bits))

        assert [r.take_bit() for _ in bits] == bits

    def test_read_past_end_returns_zeros(self):
        # Only 32 bits of data. Reading further should yield 0s, not crash.
        r = BitStreamReader(_encode([1] * 32))
        for _ in range(32):
            r.take_bit()

        assert [r.take_bit() for _ in range(16)] == [0] * 16

    def test_empty_buffer_yields_zeros(self):
        r = BitStreamReader(b"")

        assert [r.take_bit() for _ in range(8)] == [0] * 8
