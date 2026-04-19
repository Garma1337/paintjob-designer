# coding: utf-8

from dataclasses import dataclass, field


@dataclass
class ClutCoord:
    x: int = 0
    y: int = 0


@dataclass
class SlotProfile:
    """One paintjob slot on one character.

    `clut` is the in-race VRAM position the slot's 16-entry CLUT lands at —
    the one the editor reads when the user picks a character, and the one
    the game uses during actual racing.

    `clut_menu` is the separate VRAM position the same 16 entries occupy
    during the character-select menu (which lays all characters out at
    once, so each needs its own VRAM slot). Optional; only the PAINTALL.bin
    binary export consumes it. Leave `None` on profiles that don't target
    that export format.
    """

    name: str = ""
    clut: ClutCoord = field(default_factory=ClutCoord)
    clut_menu: ClutCoord | None = None


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
class PaintjobSlotProfile:
    """One entry in the profile's `paintjob_slots` table.

    Declares where a library paintjob sits in the in-game `colors[N]`
    array that PAINTALL.BIN materializes:

      - `name`: display label for the paintjob in menus / API.
      - `default_character_id`: the character whose `paintJobIndex`
        starts on this entry at runtime, and the home character whose
        VRAM backfills this paintjob's unedited slots at export time.
        `None` means "no home character" — a shared paintjob with no
        default owner.

    Order in `Profile.paintjob_slots` is authoritative: position `i` in
    this list maps to `colors[i]` in the binary. The editor's
    `PaintjobLibrary` mirrors that ordering — paintjob index in the
    sidebar = paintjob index in the binary.
    """
    name: str = ""
    default_character_id: str | None = None


@dataclass
class Profile:
    SCHEMA_VERSION = 1

    schema_version: int = SCHEMA_VERSION
    id: str = ""
    display_name: str = ""
    vram_page: VramPageDimensions = field(default_factory=VramPageDimensions)
    characters: list[CharacterProfile] = field(default_factory=list)
    paintjob_slots: list[PaintjobSlotProfile] = field(default_factory=list)
