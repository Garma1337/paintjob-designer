# coding: utf-8

from paintjob_designer.core.binary_reader import BinaryReader
from paintjob_designer.models import VramPage


# The stream-wrapper magic at the start of a CTR .vrm distinguishes a multi-TIM
# container from a single raw TIM.
_STREAM_MAGIC = 0x20

# Standard PSX TIM magic + flag bits (ctr_vrm.ksy `tim`).
_TIM_MAGIC = 0x10
_FLAG_HAS_CLUT = 1 << 3

# Bitmap block header: u4 len, u2 origin_x, u2 origin_y, u2 width, u2 height.
_BITMAP_HEADER_SIZE = 12


class VramReader:
    """Parses CTR `.vrm` TIM-stream files and blits each TIM block into a `VramPage`.

    A CTR .vrm is either a single raw TIM or a stream wrapper — first u4 is `0x20`
    for streams, then entries of `(u4 data_size, TIM)` until `data_size == 0`. Each
    TIM carries an optional CLUT block + an image block; both blocks encode their
    own VRAM destination rectangle and pixel payload.

    Port of `CTRFramework/Code/vrm/CtrVrm.cs` + `Tim.cs` in ctr-tools.
    """

    def read(self, data: bytes) -> VramPage:
        page = VramPage()
        self.blit_into(data, page)
        return page

    def blit_into(self, data: bytes, page: VramPage) -> None:
        """Draw every TIM block in `data` into `page` at its encoded coordinates.

        Existing pixels at overlapping coordinates are overwritten.
        """
        reader = BinaryReader(data)
        magic = reader.u4()

        if magic == _STREAM_MAGIC:
            self._read_stream(reader, page)
            return

        # Single-TIM file: rewind and parse one TIM.
        reader.seek(0)
        self._read_tim(reader, page)

    def _read_stream(self, reader: BinaryReader, page: VramPage) -> None:
        while True:
            data_size = reader.u4()
            if data_size == 0:
                return

            end = reader.position + data_size
            self._read_tim(reader, page)
            # Each entry's TIM must consume exactly `data_size` bytes; skip any
            # trailing padding/misalignment rather than trusting the inner reads.
            if reader.position < end:
                reader.seek(end)

    def _read_tim(self, reader: BinaryReader, page: VramPage) -> None:
        magic = reader.u4()
        if (magic & 0xFF) != _TIM_MAGIC:
            raise ValueError(
                f"Expected TIM magic 0x10 at {reader.position - 4}, got 0x{magic:08X}"
            )

        flags = reader.u4()
        has_clut = bool(flags & _FLAG_HAS_CLUT)

        if has_clut:
            self._blit_block(reader, page)

        self._blit_block(reader, page)

    def _blit_block(self, reader: BinaryReader, page: VramPage) -> None:
        """Copy one bitmap block's pixels into the VRAM page at `(origin_x, origin_y)`.

        `width` and `height` are in 16bpp pixels; the block payload is
        `width * height * 2` bytes immediately after the 12-byte header.
        """
        block_len = reader.u4()
        origin_x = reader.u2()
        origin_y = reader.u2()
        width = reader.u2()
        height = reader.u2()

        payload_size = block_len - _BITMAP_HEADER_SIZE
        if payload_size < 0:
            raise ValueError(f"TIM block shorter than header: len={block_len}")

        payload = reader.read(payload_size)

        expected = width * height * VramPage.BYTES_PER_PIXEL
        if len(payload) < expected:
            raise ValueError(
                f"TIM block payload truncated: expected {expected}, got {len(payload)}"
            )

        row_bytes = width * VramPage.BYTES_PER_PIXEL
        row_stride = VramPage.WIDTH * VramPage.BYTES_PER_PIXEL

        for row in range(height):
            dst = ((origin_y + row) * VramPage.WIDTH + origin_x) * VramPage.BYTES_PER_PIXEL
            src = row * row_bytes

            if dst < 0 or dst + row_bytes > len(page.data):
                # Block spills past VRAM bounds — silently clip (matches the
                # hardware behavior of wrapping/ignoring out-of-range draws).
                continue

            page.data[dst:dst + row_bytes] = payload[src:src + row_bytes]
