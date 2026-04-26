# coding: utf-8

from pathlib import Path

from paintjob_designer.models import (
    Paintjob,
    PsxColor,
    SlotColors,
    SlotRegion,
    SlotRegions,
    VramPage,
)
from paintjob_designer.render.atlas_renderer import AtlasRenderer
from paintjob_designer.vram.cache import VramCache


class ColorHandler:
    """Applies color edits to a single `Paintjob` + re-renders the slot."""

    def __init__(
        self,
        vram_cache: VramCache,
        atlas_renderer: AtlasRenderer,
    ) -> None:
        self._vram_cache = vram_cache
        self._atlas = atlas_renderer

    def apply_edit(
        self,
        iso_root: str | Path,
        rgba_buffer: bytearray,
        paintjob: Paintjob,
        slot: SlotRegions,
        color_index: int,
        new_color: PsxColor,
    ) -> None:
        """Mutate `paintjob` and re-render only this slot into `rgba_buffer`."""
        if color_index < 0 or color_index >= SlotColors.SIZE:
            raise IndexError(
                f"color_index {color_index} out of range (0..{SlotColors.SIZE - 1})"
            )

        vram = self._vram_cache.get(iso_root)
        self._ensure_slot_populated(paintjob, slot, vram)
        paintjob.slots[slot.slot_name].colors[color_index] = new_color
        self._atlas.render_slot(rgba_buffer, vram, paintjob, slot)

    def apply_edits(
        self,
        iso_root: str | Path,
        rgba_buffer: bytearray,
        paintjob: Paintjob,
        slot: SlotRegions,
        edits: list[tuple[int, PsxColor]],
    ) -> None:
        """Apply multiple color changes to one slot in a single pass."""
        if not edits:
            return

        vram = self._vram_cache.get(iso_root)
        self._ensure_slot_populated(paintjob, slot, vram)

        slot_colors = paintjob.slots[slot.slot_name].colors
        for color_index, new_color in edits:
            if color_index < 0 or color_index >= SlotColors.SIZE:
                raise IndexError(
                    f"color_index {color_index} out of range (0..{SlotColors.SIZE - 1})"
                )

            slot_colors[color_index] = new_color

        self._atlas.render_slot(rgba_buffer, vram, paintjob, slot)

    def default_slot_colors(
        self,
        iso_root: str | Path,
        slot: SlotRegions,
    ) -> list[PsxColor]:
        """Return the 16-entry CLUT currently in VRAM for `slot`."""
        return self.default_slot_colors_at(iso_root, slot.clut.x, slot.clut.y)

    def default_slot_colors_at(
        self,
        iso_root: str | Path,
        clut_x: int,
        clut_y: int,
    ) -> list[PsxColor]:
        """Raw-coord variant used when we only have a `ClutCoord`, not a
        `SlotRegions`. The binary exporter's "backfill un-edited characters
        with VRAM defaults" path hits this because it reads straight from
        the profile's `SlotProfile.clut_race` without going through region
        derivation.
        """
        vram = self._vram_cache.get(iso_root)

        return [
            PsxColor(value=vram.u16_at(clut_x + i, clut_y))
            for i in range(SlotColors.SIZE)
        ]

    def default_region_pixels(
        self,
        iso_root: str | Path,
        region: SlotRegion,
    ) -> bytes:
        """Read packed 4bpp pixel bytes from VRAM at `region`'s coords.

        Used by the texture exporter when a slot has no imported pixel
        override — we dump whatever the ISO ships with.
        """
        vram = self._vram_cache.get(iso_root)
        bytes_per_column = VramPage.BYTES_PER_PIXEL
        out = bytearray()

        for row in range(region.vram_height):
            start = (
                (region.vram_y + row) * VramPage.WIDTH + region.vram_x
            ) * bytes_per_column
            out.extend(vram.data[start:start + region.vram_width * bytes_per_column])

        return bytes(out)

    def reset_slot(
        self,
        iso_root: str | Path,
        rgba_buffer: bytearray,
        paintjob: Paintjob,
        slot: SlotRegions,
        base_clut_x: int,
        base_clut_y: int,
    ) -> list[PsxColor]:
        """Revert a slot to the paintjob's base-character VRAM CLUT."""
        vram = self._vram_cache.get(iso_root)
        defaults = [
            PsxColor(value=vram.u16_at(base_clut_x + i, base_clut_y))
            for i in range(SlotColors.SIZE)
        ]

        paintjob.slots[slot.slot_name] = SlotColors(colors=list(defaults))
        self._atlas.render_slot(rgba_buffer, vram, paintjob, slot)
        return defaults

    def restore_slot(
        self,
        iso_root: str | Path,
        rgba_buffer: bytearray,
        paintjob: Paintjob,
        slot: SlotRegions,
        colors: SlotColors | None,
    ) -> list[PsxColor]:
        """Undo-style inverse of `apply_edit` / `reset_slot`."""
        vram = self._vram_cache.get(iso_root)

        if colors is None:
            paintjob.slots.pop(slot.slot_name, None)
        else:
            paintjob.slots[slot.slot_name] = SlotColors(
                colors=list(colors.colors),
                pixels=list(colors.pixels),
            )

        self._atlas.render_slot(rgba_buffer, vram, paintjob, slot)

        if colors is not None:
            return list(colors.colors)

        return [
            PsxColor(value=vram.u16_at(slot.clut.x + i, slot.clut.y))
            for i in range(SlotColors.SIZE)
        ]

    def _ensure_slot_populated(
        self,
        paintjob: Paintjob,
        slot: SlotRegions,
        vram: VramPage,
    ) -> None:
        if slot.slot_name in paintjob.slots:
            return

        paintjob.slots[slot.slot_name] = SlotColors(colors=[
            PsxColor(value=vram.u16_at(slot.clut.x + i, slot.clut.y))
            for i in range(SlotColors.SIZE)
        ])
