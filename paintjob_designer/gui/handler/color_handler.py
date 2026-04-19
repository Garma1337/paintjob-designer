# coding: utf-8

from pathlib import Path

from paintjob_designer.models import (
    CharacterPaintjob,
    Paintjob,
    PsxColor,
    SlotColors,
    SlotRegions,
    VramPage,
)
from paintjob_designer.render.atlas_renderer import AtlasRenderer
from paintjob_designer.vram.cache import VramCache


class ColorHandler:
    """Applies a single color edit: upsert into the paintjob + re-render the slot.

    First edit of a slot pulls the slot's 16 default colors from the current
    VRAM CLUT so only the user's one change differs from the in-game default.
    Subsequent edits just flip one of the already-stored colors.
    """

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
        character_id: str,
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
        self._ensure_slot_populated(paintjob, character_id, slot, vram)
        paintjob.characters[character_id].slots[slot.slot_name].colors[color_index] = new_color
        self._atlas.render_slot(rgba_buffer, vram, paintjob, character_id, slot)

    def apply_edits(
        self,
        iso_root: str | Path,
        rgba_buffer: bytearray,
        paintjob: Paintjob,
        character_id: str,
        slot: SlotRegions,
        edits: list[tuple[int, PsxColor]],
    ) -> None:
        """Apply multiple color changes to one slot in a single pass.

        `apply_edit` re-renders the slot's atlas region after every single
        color write, which is wasteful when a bulk transform touches 10+
        colors in the same slot. This collapses the same operation into one
        render by mutating the paintjob's 16-color CLUT entry in place and
        then calling `render_slot` exactly once.
        """
        if not edits:
            return

        vram = self._vram_cache.get(iso_root)
        self._ensure_slot_populated(paintjob, character_id, slot, vram)

        slot_colors = paintjob.characters[character_id].slots[slot.slot_name].colors
        for color_index, new_color in edits:
            if color_index < 0 or color_index >= SlotColors.SIZE:
                raise IndexError(
                    f"color_index {color_index} out of range (0..{SlotColors.SIZE - 1})"
                )

            slot_colors[color_index] = new_color

        self._atlas.render_slot(rgba_buffer, vram, paintjob, character_id, slot)

    def default_slot_colors(
        self,
        iso_root: str | Path,
        slot: SlotRegions,
    ) -> list[PsxColor]:
        """Return the 16-entry CLUT currently in VRAM for `slot`.

        Used by the slot editor to paint its initial swatches when the paintjob
        hasn't yet been touched for a given slot.
        """
        vram = self._vram_cache.get(iso_root)

        return [
            PsxColor(value=vram.u16_at(slot.clut.x + i, slot.clut.y))
            for i in range(SlotColors.SIZE)
        ]

    def reset_slot(
        self,
        iso_root: str | Path,
        rgba_buffer: bytearray,
        paintjob: Paintjob,
        character_id: str,
        slot: SlotRegions,
    ) -> list[PsxColor]:
        """Revert a slot to the VRAM default CLUT and re-render it in the atlas.

        Returns the 16 default colors so the caller can refresh its swatches.
        Safe even when the paintjob has no entry for the character or slot yet
        — it creates one populated with the defaults.
        """
        vram = self._vram_cache.get(iso_root)
        defaults = [
            PsxColor(value=vram.u16_at(slot.clut.x + i, slot.clut.y))
            for i in range(SlotColors.SIZE)
        ]

        character = paintjob.characters.get(character_id)
        if character is None:
            character = CharacterPaintjob()
            paintjob.characters[character_id] = character

        character.slots[slot.slot_name] = SlotColors(colors=list(defaults))
        self._atlas.render_slot(rgba_buffer, vram, paintjob, character_id, slot)
        return defaults

    def restore_slot(
        self,
        iso_root: str | Path,
        rgba_buffer: bytearray,
        paintjob: Paintjob,
        character_id: str,
        slot: SlotRegions,
        colors: SlotColors | None,
    ) -> list[PsxColor]:
        """Undo-style inverse of `apply_edit` / `reset_slot`.

        When `colors` is `None` the slot is removed from the character's
        paintjob entirely (restoring the "never been touched" state); otherwise
        its colors are overwritten with the provided snapshot. Either way the
        affected atlas region is re-decoded and the resolved colors (paintjob
        override if set, else VRAM defaults) are returned so the caller can
        refresh its swatches.
        """
        vram = self._vram_cache.get(iso_root)

        character = paintjob.characters.get(character_id)
        if colors is None:
            if character is not None:
                character.slots.pop(slot.slot_name, None)
        else:
            if character is None:
                character = CharacterPaintjob()
                paintjob.characters[character_id] = character

            character.slots[slot.slot_name] = SlotColors(colors=list(colors.colors))

        self._atlas.render_slot(rgba_buffer, vram, paintjob, character_id, slot)

        if colors is not None:
            return list(colors.colors)

        return [
            PsxColor(value=vram.u16_at(slot.clut.x + i, slot.clut.y))
            for i in range(SlotColors.SIZE)
        ]

    def _ensure_slot_populated(
        self,
        paintjob: Paintjob,
        character_id: str,
        slot: SlotRegions,
        vram: VramPage,
    ) -> None:
        character = paintjob.characters.get(character_id)
        if character is None:
            character = CharacterPaintjob()
            paintjob.characters[character_id] = character

        if slot.slot_name in character.slots:
            return

        character.slots[slot.slot_name] = SlotColors(colors=[
            PsxColor(value=vram.u16_at(slot.clut.x + i, slot.clut.y))
            for i in range(SlotColors.SIZE)
        ])
