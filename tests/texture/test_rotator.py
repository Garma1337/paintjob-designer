# coding: utf-8

import pytest

from paintjob_designer.texture.four_bpp_codec import FourBppCodec
from paintjob_designer.texture.rotator import TextureRotator


def _make_rotator() -> TextureRotator:
    return TextureRotator(FourBppCodec())


def _grid_pixels(grid: list[list[int]]) -> tuple[bytes, int, int]:
    """Pack a 2D grid of indices into (bytes, width, height)."""
    height = len(grid)
    width = len(grid[0])
    flat = [v for row in grid for v in row]
    return FourBppCodec().pack(flat), width, height


def _unpack_grid(pixels: bytes, width: int, height: int) -> list[list[int]]:
    indices = FourBppCodec().unpack(pixels, width * height)
    return [indices[r * width:(r + 1) * width] for r in range(height)]


class TestTextureRotator180:

    def test_180_preserves_dimensions(self) -> None:
        pixels, width, height = _grid_pixels([
            [1, 2, 3, 4],
            [5, 6, 7, 8],
        ])

        result = _make_rotator().rotate(pixels, width, height, 180)

        assert (result.width, result.height) == (4, 2)

    def test_180_reverses_pixel_order(self) -> None:
        pixels, width, height = _grid_pixels([
            [1, 2, 3, 4],
            [5, 6, 7, 8],
        ])

        result = _make_rotator().rotate(pixels, width, height, 180)

        assert _unpack_grid(result.pixels, result.width, result.height) == [
            [8, 7, 6, 5],
            [4, 3, 2, 1],
        ]

    def test_180_twice_returns_to_original(self) -> None:
        pixels, width, height = _grid_pixels([
            [1, 2, 3, 4],
            [5, 6, 7, 8],
        ])
        rotator = _make_rotator()

        once = rotator.rotate(pixels, width, height, 180)
        twice = rotator.rotate(once.pixels, once.width, once.height, 180)

        assert twice.pixels == pixels


class TestTextureRotator90:

    def test_90_swaps_dimensions(self) -> None:
        pixels, width, height = _grid_pixels([
            [1, 2, 3, 4],
            [5, 6, 7, 8],
        ])

        result = _make_rotator().rotate(pixels, width, height, 90)

        assert (result.width, result.height) == (2, 4)

    def test_90_rotates_clockwise(self) -> None:
        pixels, width, height = _grid_pixels([
            [1, 2, 3, 4],
            [5, 6, 7, 8],
        ])

        result = _make_rotator().rotate(pixels, width, height, 90)

        # Top-left of rotated image = bottom-left of source (Gimp behavior).
        assert _unpack_grid(result.pixels, result.width, result.height) == [
            [5, 1],
            [6, 2],
            [7, 3],
            [8, 4],
        ]

    def test_90_four_times_returns_to_original_when_square(self) -> None:
        pixels, width, height = _grid_pixels([
            [1, 2, 3, 4],
            [5, 6, 7, 8],
            [9, 10, 11, 12],
            [13, 14, 15, 0],
        ])
        rotator = _make_rotator()

        rotated = pixels
        w, h = width, height
        for _ in range(4):
            result = rotator.rotate(rotated, w, h, 90)
            rotated, w, h = result.pixels, result.width, result.height

        assert rotated == pixels

    def test_90_rejects_odd_height(self) -> None:
        # 4×3 source → rotated would be 3×4 (odd new width — illegal for 4bpp).
        pixels = bytes(6)

        with pytest.raises(ValueError, match="must be even"):
            _make_rotator().rotate(pixels, 4, 3, 90)


class TestTextureRotator270:

    def test_270_rotates_counter_clockwise(self) -> None:
        pixels, width, height = _grid_pixels([
            [1, 2, 3, 4],
            [5, 6, 7, 8],
        ])

        result = _make_rotator().rotate(pixels, width, height, 270)

        assert _unpack_grid(result.pixels, result.width, result.height) == [
            [4, 8],
            [3, 7],
            [2, 6],
            [1, 5],
        ]

    def test_90_then_270_returns_to_original(self) -> None:
        pixels, width, height = _grid_pixels([
            [1, 2, 3, 4],
            [5, 6, 7, 8],
        ])
        rotator = _make_rotator()

        ninety = rotator.rotate(pixels, width, height, 90)
        back = rotator.rotate(ninety.pixels, ninety.width, ninety.height, 270)

        assert back.pixels == pixels
        assert (back.width, back.height) == (width, height)


class TestTextureRotatorInputValidation:

    def test_rejects_unsupported_degree(self) -> None:
        with pytest.raises(ValueError, match="must be one of"):
            _make_rotator().rotate(bytes(2), 2, 2, 45)

    def test_rejects_zero_width(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            _make_rotator().rotate(b"", 0, 2, 180)

    def test_rejects_negative_height(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            _make_rotator().rotate(b"", 2, -1, 180)
