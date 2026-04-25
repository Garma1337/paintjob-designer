# coding: utf-8

from paintjob_designer.models import ClutCoord, CtrMesh, SlotProfile


class SkinSlotDeriver:
    """Computes a character's skin slots from its mesh + known kart slots.

    A "skin slot" is any distinct CLUT coord used by the character's
    `.ctr` that isn't already covered by a kart slot. Names follow the
    `extra_<vram_x>_<vram_y>` convention so they line up with how the
    deriver would emit them at runtime.
    """

    _PALETTES_PER_VRAM_ROW = 16

    def derive(
        self,
        mesh: CtrMesh,
        kart_slots: list[SlotProfile],
    ) -> list[SlotProfile]:
        """Return the skin-slot list for `mesh`, sorted by (y, x).

        VRAM coords are derived from the mesh's `palette_x`/`palette_y`
        (CLUT-grid coords) by `vram_x = palette_x * 16`. Kart-slot
        coords are subtracted by VRAM-coord identity.
        """
        used_vram = self._distinct_vram_clut_coords(mesh)
        kart_used = {(s.clut_race.x, s.clut_race.y) for s in kart_slots}
        extras = sorted(used_vram - kart_used, key=lambda c: (c[1], c[0]))

        return [
            SlotProfile(
                name=f"extra_{x}_{y}",
                clut_race=ClutCoord(x=x, y=y),
                clut_menu=None,
            )
            for x, y in extras
        ]

    def _distinct_vram_clut_coords(self, mesh: CtrMesh) -> set[tuple[int, int]]:
        return {
            (
                layout.palette_x * self._PALETTES_PER_VRAM_ROW,
                layout.palette_y,
            )
            for layout in mesh.texture_layouts
        }
