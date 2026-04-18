# coding: utf-8

from dataclasses import dataclass, field

from paintjob_designer.models.ctr_mesh import BitDepth, BlendingMode
from paintjob_designer.models.profile import ClutCoord


@dataclass
class SlotRegion:
    """One rectangular texture region that samples through a paintjob slot's CLUT.

    Coordinates are in the 1024x512 16bpp VRAM pixel grid. For a 4bpp texture, each
    VRAM u16 holds four CLUT indices (low nibble first); `vram_width` is therefore
    smaller than the underlying pixel count — the 4bpp pixel count is
    `vram_width * stretch`, where `stretch = 4` for Bit4, 2 for Bit8, 1 otherwise.
    """
    vram_x: int = 0
    vram_y: int = 0
    vram_width: int = 0
    vram_height: int = 0
    bpp: BitDepth = BitDepth.Bit4
    blending: BlendingMode = BlendingMode.Standard
    texture_layout_indices: list[int] = field(default_factory=list)


@dataclass
class SlotRegions:
    """All VRAM regions on one character's mesh that share a single paintjob slot."""
    slot_name: str = ""
    clut: ClutCoord = field(default_factory=ClutCoord)
    regions: list[SlotRegion] = field(default_factory=list)


@dataclass
class CharacterSlotRegions:
    """Slot regions for one character.

    `slots` holds regions whose CLUT matches a paintjob slot — those are the
    only ones the user can recolor. `unmatched_regions` holds everything else
    the mesh actually samples (driver figures, wheels, tires, shared assets);
    they still need to be decoded for a correct 3D render but always use the
    default VRAM CLUT, never a paintjob override.
    """
    character_id: str = ""
    slots: dict[str, SlotRegions] = field(default_factory=dict)
    unmatched_regions: list[SlotRegions] = field(default_factory=list)

    @property
    def unmatched_palettes(self) -> list[ClutCoord]:
        """Convenience view: just the CLUT coords of unmatched regions."""
        return [sr.clut for sr in self.unmatched_regions]
