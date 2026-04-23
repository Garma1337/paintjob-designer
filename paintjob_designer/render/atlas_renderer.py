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
    """Decodes a `VramPage` + `Paintjob` into an RGBA atlas ready for display."""

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
            pixels_by_pos = self._paintjob_pixels_by_pos(paintjob, slot_name)
            for region in slot.regions:
                self._decode_region(vram, region, clut, pixels_by_pos, rgba)

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
        """Re-decode just this slot's regions into an already-rendered atlas."""
        clut = self._resolve_clut(vram, slot.clut, paintjob, slot.slot_name)
        pixels_by_pos = self._paintjob_pixels_by_pos(paintjob, slot.slot_name)
        
        for region in slot.regions:
            self._decode_region(vram, region, clut, pixels_by_pos, rgba)

        return rgba

    def _decode_region(
        self,
        vram: VramPage,
        region,
        clut: list[int],
        pixels_by_pos: dict,
        rgba: bytearray,
    ) -> None:
        """Route a single region through the pixel payload or the VRAM fallback."""
        override = pixels_by_pos.get((region.vram_x, region.vram_y))
        if override is not None:
            ok = self._decoder.decode_pixels_into(
                region, override.pixels, clut, rgba,
            )

            if ok:
                return

        self._decoder.decode_into(vram, region, clut, rgba)

    def _paintjob_pixels_by_pos(self, paintjob: Paintjob, slot_name: str) -> dict:
        """Index a slot's imported pixel payloads by their VRAM anchor."""
        slot = paintjob.slots.get(slot_name)
        if slot is None or not slot.pixels:
            return {}

        return {(p.vram_x, p.vram_y): p for p in slot.pixels}

    def _decode_16bpp_baseline(self, vram: VramPage, rgba: bytearray) -> None:
        """Vectorized 16bpp decode: every VRAM u16 -> 4 adjacent atlas pixels."""
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
        """Return 16 PSX color u16s for a slot's CLUT."""
        if slot_name in paintjob.slots:
            return [c.value for c in paintjob.slots[slot_name].colors]

        return [vram.u16_at(clut_coord.x + i, clut_coord.y) for i in range(16)]
