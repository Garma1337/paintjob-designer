# coding: utf-8


class FourBppCodec:
    """Packs / unpacks PSX 4bpp pixel buffers (two indices per byte, low nibble first)."""

    _MASK = 0x0F
    _PIXELS_PER_BYTE = 2

    def unpack(self, packed: bytes, count: int) -> list[int]:
        if count < 0:
            raise ValueError(f"Pixel count must be non-negative, got {count}")

        capacity = len(packed) * self._PIXELS_PER_BYTE
        if count > capacity:
            raise ValueError(
                f"Asked for {count} pixels but buffer only holds {capacity}",
            )

        out: list[int] = []
        for byte in packed:
            out.append(byte & self._MASK)
            out.append((byte >> 4) & self._MASK)

        return out[:count]

    def pack(self, indices: list[int]) -> bytes:
        if len(indices) % self._PIXELS_PER_BYTE != 0:
            raise ValueError(
                f"4bpp pack needs an even pixel count, got {len(indices)}",
            )

        out = bytearray(len(indices) // self._PIXELS_PER_BYTE)
        for i in range(0, len(indices), self._PIXELS_PER_BYTE):
            out[i // self._PIXELS_PER_BYTE] = (
                (indices[i] & self._MASK)
                | ((indices[i + 1] & self._MASK) << 4)
            )

        return bytes(out)
