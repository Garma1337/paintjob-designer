# coding: utf-8

from paintjob_designer.models import PsxColor
from paintjob_designer.palette.palette_from_colors_creator import PaletteFromColorsCreator


class TestPaletteFromColorsCreator:

    def setup_method(self) -> None:
        self._creator = PaletteFromColorsCreator()

    def test_create_copies_the_input_color_list(self) -> None:
        colors = [PsxColor(value=i) for i in range(16)]

        palette = self._creator.create(colors, "x")

        assert palette.colors == colors
        # Mutating the source mustn't leak into the saved palette.
        colors.append(PsxColor(value=999))
        assert len(palette.colors) == 16

    def test_create_trims_whitespace_in_name(self) -> None:
        palette = self._creator.create([], "  Trimmed  ")

        assert palette.name == "Trimmed"

    def test_create_accepts_empty_color_list(self) -> None:
        # The dialog seed will fill in defaults; the creator just defers.
        palette = self._creator.create([], "Empty")

        assert palette.colors == []
        assert palette.name == "Empty"
