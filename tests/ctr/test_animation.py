# coding: utf-8

from paintjob_designer.core.bitstream_reader import BitStreamReader
from paintjob_designer.models import CtrDelta
from tests.conftest import encode_bitstream as _encode_bits, pack_delta as _pack_delta


class TestUnpackDelta:

    def test_roundtrip_from_packed_u32(self, animation_decoder):
        packed = _pack_delta(
            bits_x=5, bits_y=3, bits_z=7,
            pos_x=100, pos_y=200, pos_z=50,
        )

        delta = animation_decoder.unpack_delta(packed)

        assert delta.bits_x == 5
        assert delta.bits_y == 3
        assert delta.bits_z == 7
        assert delta.pos_x == 100
        assert delta.pos_y == 200
        assert delta.pos_z == 50

    def test_zero_packed_is_zero_delta(self, animation_decoder):
        delta = animation_decoder.unpack_delta(0)

        assert delta == CtrDelta()

    def test_pos_x_is_seven_bits(self, animation_decoder):
        # 0x7F is the max 7-bit pos_x. Packing 0xFF masks to 0x7F.
        delta = animation_decoder.unpack_delta(_pack_delta(0, 0, 0, 0xFF, 0, 0))

        assert delta.pos_x == 0x7F


class TestDecompressSingleDelta:

    def test_zero_bits_zero_sign_applies_only_base_pos(self, animation_decoder):
        # bits_*=0 -> 1 bit per axis (just the sign). All sign bits 0 -> temporal 0.
        delta = CtrDelta(bits_x=0, bits_y=0, bits_z=0, pos_x=5, pos_y=10, pos_z=15)
        bs = BitStreamReader(_encode_bits([0, 0, 0]))

        verts = animation_decoder.decompress_vertices(bs, [delta])

        assert len(verts) == 1
        # base_x = (5 << 1) + 0 = 10
        # base_y = 10 + 0 = 10
        # base_z = 15 + 0 = 15
        # Vector3b stores (x, z, y) after Y/Z swap -> (10, 15, 10).
        assert (verts[0].x, verts[0].y, verts[0].z) == (10, 15, 10)

    def test_sign_bit_on_zero_width_subtracts_one(self, animation_decoder):
        # bits_*=0, all sign bits = 1 -> tx=ty=tz = -(1 << 0) = -1.
        delta = CtrDelta(bits_x=0, bits_y=0, bits_z=0, pos_x=0, pos_y=10, pos_z=20)
        bs = BitStreamReader(_encode_bits([1, 1, 1]))

        verts = animation_decoder.decompress_vertices(bs, [delta])

        # base_x = (0 << 1) + (-1) = -1 mod 256 = 255
        # base_y = 10 + (-1) = 9
        # base_z = 20 + (-1) = 19
        assert (verts[0].x, verts[0].y, verts[0].z) == (255, 19, 9)

    def test_bits_equal_seven_resets_base(self, animation_decoder):
        # Two deltas; first sets base non-zero, second resets it via bits==7.
        bs = BitStreamReader(_encode_bits([
            0, 0, 0,   # first delta: tx=ty=tz=0
            0, 0, 0,   # second delta: tx=ty=tz=0 (still 1 sign bit each since bits=7 takes 1+7=8)
            0, 0, 0, 0, 0, 0, 0,  # value bits for x (7 bits)
            0, 0, 0, 0, 0, 0, 0,  # value bits for y (7 bits)
            0, 0, 0, 0, 0, 0, 0,  # value bits for z (7 bits)
        ]))

        deltas = [
            CtrDelta(bits_x=0, bits_y=0, bits_z=0, pos_x=50, pos_y=60, pos_z=70),
            CtrDelta(bits_x=7, bits_y=7, bits_z=7, pos_x=1, pos_y=2, pos_z=3),
        ]

        verts = animation_decoder.decompress_vertices(bs, deltas)

        # Second vertex: base reset to 0 on each axis before adding.
        # base_x = 0 + (1 << 1) + 0 = 2
        # base_y = 0 + 2 + 0 = 2
        # base_z = 0 + 3 + 0 = 3
        # Vector3b swaps y/z -> (2, 3, 2).
        assert (verts[1].x, verts[1].y, verts[1].z) == (2, 3, 2)


class TestDecompressMultipleDeltas:

    def test_base_accumulates_across_vertices(self, animation_decoder):
        delta = CtrDelta(bits_x=0, bits_y=0, bits_z=0, pos_x=5, pos_y=10, pos_z=15)
        bs = BitStreamReader(_encode_bits([0] * 6))  # 2 deltas * 3 sign bits each

        verts = animation_decoder.decompress_vertices(bs, [delta, delta])

        assert len(verts) == 2
        # Vertex 0: (10, 10, 15) byte-space; swapped -> (10, 15, 10)
        assert (verts[0].x, verts[0].y, verts[0].z) == (10, 15, 10)
        # Vertex 1: base accumulates -> (20, 20, 30); swapped -> (20, 30, 20)
        assert (verts[1].x, verts[1].y, verts[1].z) == (20, 30, 20)


class TestTemporalBitsWidth:

    def test_bits_width_one_adds_value_bit(self, animation_decoder):
        # bits_x=1: read 1 sign bit + 1 value bit. Sign=0, value=1 -> tx = 1.
        # bits_y=0, bits_z=0 -> 1 sign bit each.
        delta = CtrDelta(bits_x=1, bits_y=0, bits_z=0, pos_x=0, pos_y=0, pos_z=0)
        bs = BitStreamReader(_encode_bits([
            0, 1,    # X: sign=0, bit0=1 -> tx = 1
            0,       # Y: sign=0 -> ty = 0
            0,       # Z: sign=0 -> tz = 0
        ]))

        verts = animation_decoder.decompress_vertices(bs, [delta])

        # base_x = 0 + (0<<1) + 1 = 1
        assert verts[0].x == 1
