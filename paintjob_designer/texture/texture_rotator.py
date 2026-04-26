# coding: utf-8

from paintjob_designer.models import RotatedTexture
from paintjob_designer.texture.four_bpp_codec import FourBppCodec


class TextureRotator:
    """Rotates a packed 4bpp pixel buffer clockwise by 90 / 180 / 270 degrees."""

    _SUPPORTED_DEGREES = (90, 180, 270)

    def __init__(self, codec: FourBppCodec) -> None:
        self._codec = codec

    def rotate(
        self, pixels: bytes, width: int, height: int, degrees: int,
    ) -> RotatedTexture:
        """Return the rotated pixel buffer and its new dimensions.

        180° preserves dimensions; 90 / 270 swap them. 4bpp packing requires
        the new width to be even — the rotation raises `ValueError` if it
        wouldn't be.
        """
        if degrees not in self._SUPPORTED_DEGREES:
            raise ValueError(
                f"Rotation must be one of {self._SUPPORTED_DEGREES}, got {degrees}",
            )

        if width <= 0 or height <= 0:
            raise ValueError(
                f"Width / height must be positive, got {width}x{height}",
            )

        indices = self._codec.unpack(pixels, width * height)

        if degrees == 180:
            return RotatedTexture(self._codec.pack(indices[::-1]), width, height)

        new_w, new_h = height, width
        if new_w % 2 != 0:
            raise ValueError(
                f"Cannot rotate {degrees}° — new width ({new_w}) must be even "
                f"for 4bpp packing",
            )

        rotated = [0] * (new_w * new_h)
        if degrees == 90:
            self.rotate_90_cw(indices, width, height, rotated, new_w)
        else:
            self.rotate_270_cw(indices, width, height, rotated, new_w)

        return RotatedTexture(self._codec.pack(rotated), new_w, new_h)

    @staticmethod
    def rotate_90_cw(
        src: list[int], width: int, height: int,
        dst: list[int], new_w: int,
    ) -> None:
        # CW: source (r, c) → dst (c, H - 1 - r).
        for r in range(height):
            row_offset = r * width
            for c in range(width):
                dst[c * new_w + (height - 1 - r)] = src[row_offset + c]

    @staticmethod
    def rotate_270_cw(
        src: list[int], width: int, height: int,
        dst: list[int], new_w: int,
    ) -> None:
        # 270° CW = 90° CCW: source (r, c) → dst (W - 1 - c, r).
        for r in range(height):
            row_offset = r * width
            for c in range(width):
                dst[(width - 1 - c) * new_w + r] = src[row_offset + c]
