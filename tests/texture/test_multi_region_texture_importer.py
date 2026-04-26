# coding: utf-8

import pytest

pytest.importorskip("PIL", exc_type=ImportError)

from PIL import Image

from paintjob_designer.color.converter import ColorConverter
from paintjob_designer.texture.four_bpp_codec import FourBppCodec
from paintjob_designer.texture.multi_region_texture_importer import (
    MultiRegionTextureImporter,
)
from paintjob_designer.texture.texture_quantizer import TextureQuantizer


def _importer() -> MultiRegionTextureImporter:
    return MultiRegionTextureImporter(
        TextureQuantizer(ColorConverter()), FourBppCodec(),
    )


def _solid(width: int, height: int, rgba: tuple[int, int, int, int]) -> Image.Image:
    return Image.new("RGBA", (width, height), rgba)


class TestMultiRegionTextureImporter:

    def test_two_regions_share_one_palette(self) -> None:
        red = _solid(8, 4, (255, 0, 0, 255))
        green = _solid(8, 4, (0, 255, 0, 255))

        result = _importer().import_for_regions(
            [red, green], [(8, 4), (8, 4)],
        )

        assert len(result.palette) == 16
        assert len(result.regions) == 2

    def test_per_region_pixel_count_matches_dimensions(self) -> None:
        red = _solid(8, 4, (255, 0, 0, 255))
        green = _solid(8, 2, (0, 255, 0, 255))

        result = _importer().import_for_regions(
            [red, green], [(8, 4), (8, 2)],
        )

        assert result.regions[0].width == 8 and result.regions[0].height == 4
        assert result.regions[1].width == 8 and result.regions[1].height == 2
        # 4bpp: width × height / 2 bytes per region.
        assert len(result.regions[0].pixels) == 8 * 4 // 2
        assert len(result.regions[1].pixels) == 8 * 2 // 2

    def test_different_widths_get_padded_during_stitch(self) -> None:
        # Wider region drives stitched width; narrower one is right-padded.
        red = _solid(8, 4, (255, 0, 0, 255))
        green = _solid(4, 4, (0, 255, 0, 255))

        result = _importer().import_for_regions(
            [red, green], [(8, 4), (4, 4)],
        )

        # Output respects each region's own dimensions, not the stitched width.
        assert result.regions[0].width == 8
        assert result.regions[1].width == 4
        assert len(result.regions[1].pixels) == 4 * 4 // 2

    def test_rejects_image_count_mismatch(self) -> None:
        red = _solid(4, 4, (255, 0, 0, 255))

        with pytest.raises(ValueError, match="length mismatch"):
            _importer().import_for_regions([red], [(4, 4), (4, 4)])

    def test_rejects_empty_input(self) -> None:
        with pytest.raises(ValueError, match="at least one"):
            _importer().import_for_regions([], [])

    def test_rejects_non_positive_dimensions(self) -> None:
        red = _solid(4, 4, (255, 0, 0, 255))

        with pytest.raises(ValueError, match="positive"):
            _importer().import_for_regions([red], [(0, 4)])

    def test_resizes_image_to_match_region_spec(self) -> None:
        # Source 16×8, region wants 8×4 → resize-on-import via Lanczos.
        red = _solid(16, 8, (255, 0, 0, 255))

        result = _importer().import_for_regions([red], [(8, 4)])

        assert result.regions[0].width == 8
        assert len(result.regions[0].pixels) == 8 * 4 // 2


class TestSliceRegion:

    def test_extracts_a_left_aligned_block(self) -> None:
        # 4×3 stitched buffer (12 indices), pull a 2×2 starting at row 1.
        all_indices = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]

        sliced = MultiRegionTextureImporter.slice_region(
            all_indices, stitched_width=4, y_offset=1,
            region_width=2, region_height=2,
        )

        # Row 1 starts at index 4 → slice [4,5] then row 2 at [8,9].
        assert sliced == [5, 6, 9, 10]

    def test_rejects_odd_region_width(self) -> None:
        with pytest.raises(ValueError, match="even"):
            MultiRegionTextureImporter.slice_region(
                [0] * 12, stitched_width=4, y_offset=0,
                region_width=3, region_height=1,
            )
