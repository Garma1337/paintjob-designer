# coding: utf-8

import pytest

pytest.importorskip("PIL", exc_type=ImportError)

from PIL import Image

from paintjob_designer.color.converter import ColorConverter
from paintjob_designer.palette.palette_from_image_creator import PaletteFromImageCreator
from paintjob_designer.texture.texture_quantizer import TextureQuantizer


def _creator() -> PaletteFromImageCreator:
    return PaletteFromImageCreator(TextureQuantizer(ColorConverter()))


class TestPaletteFromImageCreator:

    def test_palette_has_exactly_16_entries(self) -> None:
        img = Image.new("RGBA", (8, 8), (255, 0, 0, 255))

        palette = _creator().create(img, "Reds")

        assert len(palette.colors) == 16

    def test_palette_name_is_trimmed(self) -> None:
        img = Image.new("RGBA", (4, 4), (0, 255, 0, 255))

        palette = _creator().create(img, "  Greens  ")

        assert palette.name == "Greens"

    def test_solid_image_palette_index_zero_stays_transparent_sentinel(self) -> None:
        img = Image.new("RGBA", (4, 4), (10, 20, 30, 255))

        palette = _creator().create(img, "x")

        # Quantizer reserves index 0 for the transparent sentinel.
        assert palette.colors[0].value == 0

    def test_odd_width_image_is_padded_to_even(self) -> None:
        # Quantizer rejects odd widths; the creator pads to the next even.
        img = Image.new("RGBA", (3, 4), (0, 0, 255, 255))

        palette = _creator().create(img, "Blues")

        assert len(palette.colors) == 16

    def test_minimum_width_one_image_does_not_crash(self) -> None:
        img = Image.new("RGBA", (1, 4), (255, 255, 255, 255))

        palette = _creator().create(img, "Tiny")

        assert len(palette.colors) == 16
