# coding: utf-8

from struct import unpack_from


class BinaryReader:
    """Cursor-based reader over a `bytes` object."""

    def __init__(self, data: bytes) -> None:
        self._data = data
        self._pos = 0

    @property
    def position(self) -> int:
        return self._pos

    @property
    def length(self) -> int:
        return len(self._data)

    def remaining(self) -> int:
        return len(self._data) - self._pos

    def seek(self, pos: int) -> None:
        if pos < 0 or pos > len(self._data):
            raise ValueError(f"seek out of range: {pos} (length={len(self._data)})")

        self._pos = pos

    def skip(self, n: int) -> None:
        self.seek(self._pos + n)

    def read(self, n: int) -> bytes:
        self._require(n)
        out = self._data[self._pos:self._pos + n]
        self._pos += n
        return out

    def u1(self) -> int:
        return self.read(1)[0]

    def u2(self) -> int:
        self._require(2)
        (v,) = unpack_from("<H", self._data, self._pos)
        self._pos += 2
        return v

    def u4(self) -> int:
        self._require(4)
        (v,) = unpack_from("<I", self._data, self._pos)
        self._pos += 4
        return v

    def u4_be(self) -> int:
        self._require(4)
        (v,) = unpack_from(">I", self._data, self._pos)
        self._pos += 4
        return v

    def s1(self) -> int:
        self._require(1)
        (v,) = unpack_from("<b", self._data, self._pos)
        self._pos += 1
        return v

    def s2(self) -> int:
        self._require(2)
        (v,) = unpack_from("<h", self._data, self._pos)
        self._pos += 2
        return v

    def s4(self) -> int:
        self._require(4)
        (v,) = unpack_from("<i", self._data, self._pos)
        self._pos += 4
        return v

    def _require(self, n: int) -> None:
        if self._pos + n > len(self._data):
            raise EOFError(
                f"read past end: want {n} bytes at {self._pos}, "
                f"have {len(self._data) - self._pos}"
            )

    def read_strz(self, size: int, encoding: str = "ascii") -> str:
        """Read `size` bytes as a null-terminated string."""
        raw = self.read(size)
        end = raw.find(b"\x00")

        if end >= 0:
            raw = raw[:end]

        return raw.decode(encoding)
