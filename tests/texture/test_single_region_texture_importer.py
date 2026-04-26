# coding: utf-8

import pytest

pytest.importorskip("PIL", exc_type=ImportError)

from PIL import Image

from paintjob_designer.color.converter import ColorConverter
from paintjob_designer.texture.single_region_texture_importer import (
    SingleRegionTextureImporter,
    SizeMismatchMode,
)
from paintjob_designer.texture.texture_quantizer import TextureQuantizer


def _write_png(tmp_path, filename: str, size: tuple[int, int], color=(255, 0, 0, 255)):
    path = tmp_path / filename
    img = Image.new("RGBA", size, color)
    img.save(path)
    return path


class TestSingleRegionTextureImporter:

    def setup_method(self) -> None:
        self._importer = SingleRegionTextureImporter(TextureQuantizer(ColorConverter()))

    def test_imports_matching_size_without_resize(self, tmp_path) -> None:
        path = _write_png(tmp_path, "exact.png", (4, 2))

        result = self._importer.import_from_path(path, 4, 2)

        assert result.width == 4
        assert result.height == 2

    def test_rejects_size_mismatch_by_default(self, tmp_path) -> None:
        path = _write_png(tmp_path, "big.png", (8, 4))

        with pytest.raises(ValueError, match="target is 4x2"):
            self._importer.import_from_path(path, 4, 2)

    def test_scale_mode_resizes_to_target(self, tmp_path) -> None:
        path = _write_png(tmp_path, "big.png", (8, 4))

        result = self._importer.import_from_path(
            path, 4, 2, mode=SizeMismatchMode.SCALE,
        )

        assert result.width == 4
        assert result.height == 2
        # 4x2 = 8 pixels = 4 bytes at 4bpp.
        assert len(result.pixels) == 4

    def test_crop_mode_center_crops(self, tmp_path) -> None:
        # Solid blue border with a red 2x1 center patch → center-cropping to
        # 2x1 should leave only the red pixels (every byte has non-zero nibbles).
        img = Image.new("RGBA", (4, 3), (0, 0, 255, 255))
        for x in range(1, 3):
            img.putpixel((x, 1), (255, 0, 0, 255))
        path = tmp_path / "border.png"
        img.save(path)

        result = self._importer.import_from_path(
            path, 2, 1, mode=SizeMismatchMode.CENTER_CROP,
        )

        # Only the red pixels should survive the crop → both nibbles map to
        # the same non-zero palette index (solid red after quantize).
        assert result.width == 2
        assert result.height == 1
        byte = result.pixels[0]
        assert (byte & 0x0F) != 0
        assert ((byte >> 4) & 0x0F) != 0
        assert (byte & 0x0F) == ((byte >> 4) & 0x0F)

    def test_crop_mode_rejects_too_small_source(self, tmp_path) -> None:
        path = _write_png(tmp_path, "small.png", (2, 1))

        with pytest.raises(ValueError, match="source must be"):
            self._importer.import_from_path(
                path, 4, 2, mode=SizeMismatchMode.CENTER_CROP,
            )

    def test_accepts_non_rgba_png(self, tmp_path) -> None:
        # Plain RGB (no alpha) should still import fine — the quantizer
        # treats missing alpha as fully opaque.
        img = Image.new("RGB", (4, 2), (0, 200, 0))
        path = tmp_path / "rgb.png"
        img.save(path)

        result = self._importer.import_from_path(path, 4, 2)

        assert result.width == 4
        assert result.height == 2
