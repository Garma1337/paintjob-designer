# coding: utf-8

from dataclasses import dataclass, field
from enum import Enum


class KartType(str, Enum):
    """The kind of vehicle a character drives."""

    KART = "kart"
    HOVERCRAFT = "hovercraft"


@dataclass
class ClutCoord:
    x: int = 0
    y: int = 0


@dataclass
class SlotProfile:
    """One paintable CLUT on one character."""

    name: str = ""
    clut_race: ClutCoord = field(default_factory=ClutCoord)
    clut_menu: ClutCoord | None = None
    non_portable: bool = False


@dataclass
class CharacterProfile:
    """One character + the CLUTs that paintjobs and skins can edit."""

    id: str = ""
    display_name: str = ""
    mesh_source: str = ""
    kart_type: KartType = KartType.KART
    kart_slots: list[SlotProfile] = field(default_factory=list)
    skin_slots: list[SlotProfile] = field(default_factory=list)

    @property
    def slots(self) -> list[SlotProfile]:
        return self.kart_slots + self.skin_slots


@dataclass
class VramPageDimensions:
    width: int = 1024
    height: int = 512


@dataclass
class PaintjobSlotProfile:
    """One entry in the profile's `paintjob_slots` table."""
    name: str = ""
    default_character_id: str | None = None


@dataclass
class Profile:
    SCHEMA_VERSION = 3

    schema_version: int = SCHEMA_VERSION
    id: str = ""
    display_name: str = ""
    vram_page: VramPageDimensions = field(default_factory=VramPageDimensions)
    characters: list[CharacterProfile] = field(default_factory=list)
    paintjob_slots: list[PaintjobSlotProfile] = field(default_factory=list)
