# coding: utf-8

from paintjob_designer.core.bitstream_reader import BitStreamReader
from paintjob_designer.models import CtrDelta, Vector3b


class AnimationDecoder:
    """Decodes CTR compressed animation frames.

    Port of `CtrFrame.cs:DecompressVertices` /
    `DeltaToVertex` / `GetTemporalValue` plus `CtrDelta.cs:unpackValue`
    in ctr-tools.
    """

    def unpack_delta(self, value: int) -> CtrDelta:
        """Decode a 4-byte packed `CtrDelta` from its u32 representation."""
        return CtrDelta(
            bits_x=(value >> 6) & 0x7,
            bits_y=(value >> 3) & 0x7,
            bits_z=(value >> 0) & 0x7,
            pos_x=(value >> 25) & 0x7F,
            pos_y=(value >> 17) & 0xFF,
            pos_z=(value >> 9) & 0xFF,
        )

    def decompress_vertices(
        self, bitstream: BitStreamReader, deltas: list[CtrDelta],
    ) -> list[Vector3b]:
        """Reconstruct one frame's vertex bytes from the bitstream + per-vertex deltas.

        Keeps a running base (X, Y, Z) across vertices:
            - If the delta's bit-width for an axis is 7, reset that axis's base to 0.
            - Read a signed temporal value from the bitstream.
            - axis_byte = (base + base_delta + temporal) mod 256.
              (For X specifically, base_delta is left-shifted by 1.)
            - The resulting Vector3b swaps Y and Z when packed (matches ctr-tools).
        """
        result: list[Vector3b] = []
        base_x = 0
        base_y = 0
        base_z = 0

        for delta in deltas:
            if delta.bits_x == 7:
                base_x = 0

            if delta.bits_y == 7:
                base_y = 0

            if delta.bits_z == 7:
                base_z = 0

            tx = self._temporal_value(bitstream, delta.bits_x)
            ty = self._temporal_value(bitstream, delta.bits_y)
            tz = self._temporal_value(bitstream, delta.bits_z)

            base_x = (base_x + (delta.pos_x << 1) + tx) % 256
            base_y = (base_y + delta.pos_y + ty) % 256
            base_z = (base_z + delta.pos_z + tz) % 256

            # Y/Z swap when storing (ctr-tools: Vector3b((byte)X, (byte)Z, (byte)Y)).
            result.append(Vector3b(x=base_x, y=base_z, z=base_y))

        return result

    def _temporal_value(self, bitstream: BitStreamReader, delta_bits: int) -> int:
        """Read a signed temporal value from the bitstream using `delta_bits` width.

        First bit is the sign: 1 -> start at -(1 << delta_bits), 0 -> start at 0.
        Then `delta_bits` more bits are OR'd in MSB-first.
        """
        result = -(1 << delta_bits) if bitstream.take_bit() == 1 else 0
        for i in range(delta_bits):
            result |= bitstream.take_bit() << (delta_bits - 1 - i)

        return result
