# coding: utf-8

import numpy as np

from paintjob_designer.color.converter import ColorConverter
from paintjob_designer.models import (
    CharacterSlotRegions,
    ClutCoord,
    Paintjob,
    SlotRegions,
    VramPage,
)
from paintjob_designer.render.psx_rgba_lut import PsxRgbaLut
from paintjob_designer.render.vram_region_decoder import VramRegionDecoder

# The atlas stretches horizontally by 4x relative to VRAM so 4bpp texture pixels
# appear at natural 1:1 resolution. 16bpp regions (palette strips, 16bpp textures)
# are stretched 4x as a side effect, which is acceptable — they're context/filler.
_STRETCH_4BPP = 4
_ATLAS_WIDTH = VramPage.WIDTH * _STRETCH_4BPP
_ATLAS_HEIGHT = VramPage.HEIGHT
_BYTES_PER_PIXEL = 4  # RGBA


class AtlasRenderer:
    """Decodes a `VramPage` + `Paintjob` into an RGBA atlas ready for display.

    Orchestrates three helpers:
      - `PsxRgbaLut` for the 16bpp baseline scan (one gather over VRAM)
      - `VramRegionDecoder` for per-slot 4bpp rewrites
      - local CLUT resolution (paintjob vs. VRAM default)

    Output is a 4096x512 RGBA buffer (row-major, `r, g, b, a` per pixel).
    Every VRAM u16 occupies 4 horizontal atlas pixels so 4bpp texture
    regions decode to their natural texel size. 16bpp-decoded regions
    (the baseline pass) end up stretched 4x horizontally, which is fine
    for the CLUT strips and context they typically occupy.

    Two entry points:
        - `render_atlas`: full decode. Call once per character load.
        - `render_slot`: incremental decode of one slot's regions, for
          fast update when the user edits a single CLUT color.

    Both return RGBA `bytes`. The incremental path applies its writes
    in-place on the caller-owned buffer, returning it for chaining.
    """

    ATLAS_WIDTH = _ATLAS_WIDTH
    ATLAS_HEIGHT = _ATLAS_HEIGHT
    BYTES_PER_PIXEL = _BYTES_PER_PIXEL

    def __init__(self, color_converter: ColorConverter) -> None:
        self._lut = PsxRgbaLut()
        self._decoder = VramRegionDecoder(
            color_converter, self.ATLAS_WIDTH, self.ATLAS_HEIGHT, _STRETCH_4BPP,
        )

    def render_atlas(
        self,
        vram: VramPage,
        paintjob: Paintjob,
        regions: CharacterSlotRegions,
    ) -> bytearray:
        rgba = bytearray(self.ATLAS_WIDTH * self.ATLAS_HEIGHT * self.BYTES_PER_PIXEL)
        self._decode_16bpp_baseline(vram, rgba)

        for slot_name, slot in regions.slots.items():
            clut = self._resolve_clut(vram, slot.clut, paintjob, slot_name)
            for region in slot.regions:
                self._decoder.decode_into(vram, region, clut, rgba)

        # Unmatched regions always use the default VRAM CLUT — they're the
        # wheels, driver figures, and shared textures that aren't paintjob-
        # editable but still need 4bpp decoding so the 3D preview doesn't
        # fall back to baseline garbage in their place.
        for unmatched in regions.unmatched_regions:
            clut = [
                vram.u16_at(unmatched.clut.x + i, unmatched.clut.y)
                for i in range(16)
            ]
            for region in unmatched.regions:
                self._decoder.decode_into(vram, region, clut, rgba)

        return rgba

    def render_slot(
        self,
        rgba: bytearray,
        vram: VramPage,
        paintjob: Paintjob,
        slot: SlotRegions,
    ) -> bytearray:
        """Re-decode just this slot's regions into an already-rendered atlas.

        The caller keeps the baseline 16bpp decode and only pays for the
        16-to-few-hundred pixels the edited slot actually covers. Used on
        every color-picker change.
        """
        clut = self._resolve_clut(vram, slot.clut, paintjob, slot.slot_name)
        for region in slot.regions:
            self._decoder.decode_into(vram, region, clut, rgba)
        return rgba

    def _decode_16bpp_baseline(self, vram: VramPage, rgba: bytearray) -> None:
        """Vectorized 16bpp decode: every VRAM u16 -> 4 adjacent atlas pixels.

        Gathers packed RGBA values from the precomputed 65536-entry LUT,
        reshapes to 2D, repeats 4x horizontally for the 4bpp atlas stretch,
        and copies the bytes into the caller-owned buffer. ~50x faster
        than a per-pixel loop.
        """
        vram_u16 = np.frombuffer(vram.data, dtype=np.uint16)
        packed = self._lut.as_array()[vram_u16]                            # (524288,)
        packed_2d = packed.reshape(VramPage.HEIGHT, VramPage.WIDTH)        # (512, 1024)
        stretched = np.repeat(packed_2d, _STRETCH_4BPP, axis=1)            # (512, 4096)
        rgba[:] = stretched.tobytes()

    def _resolve_clut(
        self,
        vram: VramPage,
        clut_coord: ClutCoord,
        paintjob: Paintjob,
        slot_name: str,
    ) -> list[int]:
        """Return 16 PSX color u16s for a slot's CLUT.

        If the paintjob has this slot populated, its colors win; otherwise
        the default CLUT is read straight from the VRAM page at the given
        `clut_coord`.
        """
        if slot_name in paintjob.slots:
            return [c.value for c in paintjob.slots[slot_name].colors]

        return [vram.u16_at(clut_coord.x + i, clut_coord.y) for i in range(16)]
