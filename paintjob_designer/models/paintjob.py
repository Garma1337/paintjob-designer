# coding: utf-8

from dataclasses import dataclass, field

from paintjob_designer.models.color import PsxColor


@dataclass
class SlotColors:
    """The 16 colors of one CLUT slot."""
    SIZE = 16

    colors: list[PsxColor] = field(default_factory=list)


@dataclass
class CharacterPaintjob:
    # Keyed by slot name. Omitted slots inherit the game's original CLUT.
    slots: dict[str, SlotColors] = field(default_factory=dict)


@dataclass
class Paintjob:
    """In-memory session edits, keyed by character id.

    Not serialized — the editor's on-disk format is `SinglePaintjob`
    (one character's slots at a time). This is just the runtime container
    that keeps per-character edits alive while the user switches between
    characters in the sidebar.
    """
    # Omitted characters use all-default colors.
    characters: dict[str, CharacterPaintjob] = field(default_factory=dict)


@dataclass
class SinglePaintjob:
    """A single, character-agnostic paintjob: just 8 slots × 16 colors.

    This is the unit the user exports when they want to share "a paintjob" that
    can be applied to any character — Saphi's cyclable-paintjob scheme being
    the canonical example. Structurally it's the same as one entry of
    `Paintjob.characters`, with its own metadata and without a profile/character
    binding.
    """
    SCHEMA_VERSION = 1

    schema_version: int = SCHEMA_VERSION
    name: str = ""
    author: str = ""
    slots: dict[str, SlotColors] = field(default_factory=dict)
