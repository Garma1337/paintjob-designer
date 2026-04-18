# coding: utf-8


class BitStreamReader:
    """LSB-first bit reader over a byte buffer, with a quirky per-u32 bit-reversal.

    Port of `BitStreamReader.cs` in ctr-tools. The CTR
    compressed-animation bitstream is encoded in 4-byte blocks where each block is
    read little-endian, then bit-reversed before bits are pulled LSB-first. Net
    effect is that the *last* byte of each block is consumed first, MSB to LSB,
    then the third byte, and so on.

    Reads past the end return 0 rather than raising — the decompressor over-reads
    intentionally (it consumes up to `num_verts × max_bits` bits, which can exceed
    the real payload for the last frame).
    """

    def __init__(self, data: bytes) -> None:
        self._data = data
        self._byte_pos = 0
        self._bits_taken = 0
        self._cache = self._next_u32()

    def take_bit(self) -> int:
        bit = self._cache & 1
        self._cache >>= 1
        self._bits_taken += 1

        if self._bits_taken >= 32:
            self._bits_taken = 0
            self._cache |= self._next_u32()

        return bit

    def _next_u32(self) -> int:
        if self._byte_pos + 4 > len(self._data):
            self._byte_pos = len(self._data)
            return 0

        raw = int.from_bytes(
            self._data[self._byte_pos:self._byte_pos + 4], "little",
        )

        self._byte_pos += 4
        return self._bit_reverse_32(raw)

    def _bit_reverse_32(self, value: int) -> int:
        value = ((value & 0xFFFF0000) >> 16) | ((value & 0x0000FFFF) << 16)
        value = ((value & 0xFF00FF00) >> 8)  | ((value & 0x00FF00FF) << 8)
        value = ((value & 0xF0F0F0F0) >> 4)  | ((value & 0x0F0F0F0F) << 4)
        value = ((value & 0xCCCCCCCC) >> 2)  | ((value & 0x33333333) << 2)
        value = ((value & 0xAAAAAAAA) >> 1)  | ((value & 0x55555555) << 1)
        return value & 0xFFFFFFFF
