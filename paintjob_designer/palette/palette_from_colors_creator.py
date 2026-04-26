# coding: utf-8

from paintjob_designer.models import Palette, PsxColor


class PaletteFromColorsCreator:
    """Builds a `Palette` from an explicit list of PSX colors plus a name.

    The "from colors" path mirrors `PaletteFromImageCreator` so both
    palette sources go through a small focused class with the same shape
    (`create(...)` → `Palette`). This keeps the controller free of inline
    palette assembly and makes both creation paths trivially testable.
    """

    def create(self, colors: list[PsxColor], name: str) -> Palette:
        return Palette(name=name.strip(), colors=list(colors))
