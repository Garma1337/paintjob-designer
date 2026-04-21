# coding: utf-8

from pydantic import BaseModel, ConfigDict, Field

from paintjob_designer.models.color import PsxColor


class Palette(BaseModel):
    """A named list of PSX colors the artist has saved for reuse.

    Short (1–16 entries). When applied to a slot, each palette entry maps
    to the corresponding slot color index by list position; artists can
    reorder the entries before apply to change that mapping. Shorter
    palettes leave the trailing slot colors untouched.
    """

    model_config = ConfigDict(frozen=False)

    name: str = ""
    colors: list[PsxColor] = Field(default_factory=list)


class PaletteLibrary(BaseModel):
    """Ordered collection of palettes persisted in the user's config."""

    model_config = ConfigDict(frozen=False)

    palettes: list[Palette] = Field(default_factory=list)
