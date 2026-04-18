# coding: utf-8

from dataclasses import dataclass, field


@dataclass
class ClutCoord:
    x: int = 0
    y: int = 0


@dataclass
class SlotProfile:
    name: str = ""
    clut: ClutCoord = field(default_factory=ClutCoord)


@dataclass
class CharacterProfile:
    id: str = ""
    display_name: str = ""
    mesh_source: str = ""
    slots: list[SlotProfile] = field(default_factory=list)


@dataclass
class VramPageDimensions:
    width: int = 1024
    height: int = 512


@dataclass
class Profile:
    SCHEMA_VERSION = 1

    schema_version: int = SCHEMA_VERSION
    id: str = ""
    display_name: str = ""
    vram_page: VramPageDimensions = field(default_factory=VramPageDimensions)
    characters: list[CharacterProfile] = field(default_factory=list)
