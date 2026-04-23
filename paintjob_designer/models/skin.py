# coding: utf-8

from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from paintjob_designer.models.color import Rgb888
from paintjob_designer.models.paintjob import SlotColors


class Skin(BaseModel):
    """A character-bound recolor: skin-slot CLUT overrides + gouraud
    vertex color overrides.
    """

    model_config = ConfigDict(frozen=False)

    SCHEMA_VERSION: ClassVar[int] = 1

    schema_version: int = SCHEMA_VERSION
    name: str = ""
    author: str = ""
    character_id: str = ""
    slots: dict[str, SlotColors] = Field(default_factory=dict)
    vertex_overrides: dict[int, Rgb888] = Field(default_factory=dict)


class SkinLibrary(BaseModel):
    """Ordered collection of skins the session is working on."""

    model_config = ConfigDict(frozen=False)

    skins: list[Skin] = Field(default_factory=list)

    def count(self) -> int:
        return len(self.skins)

    def add(self, skin: Skin) -> int:
        """Append `skin` to the library and return its new index."""
        self.skins.append(skin)
        return len(self.skins) - 1

    def remove(self, index: int) -> Skin:
        """Pop the skin at `index` and return it."""
        return self.skins.pop(index)

    def move(self, from_index: int, to_index: int) -> None:
        """Reorder: move a skin to a new position."""
        skin = self.skins.pop(from_index)
        to_index = max(0, min(to_index, len(self.skins)))
        self.skins.insert(to_index, skin)

    def for_character(self, character_id: str) -> list[Skin]:
        """Return every skin in the library bound to `character_id`."""
        return [s for s in self.skins if s.character_id == character_id]
