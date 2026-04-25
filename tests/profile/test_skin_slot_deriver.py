# coding: utf-8

from paintjob_designer.models import (
    BlendingMode,
    BitDepth,
    ClutCoord,
    CtrMesh,
    SlotProfile,
    TextureLayout,
)
from paintjob_designer.profile.skin_slot_deriver import SkinSlotDeriver


def _layout(palette_x: int, palette_y: int) -> TextureLayout:
    return TextureLayout(
        uv0_u=0, uv0_v=0,
        uv1_u=0, uv1_v=0,
        uv2_u=0, uv2_v=0,
        uv3_u=0, uv3_v=0,
        palette_x=palette_x,
        palette_y=palette_y,
        page_x=0,
        page_y=0,
        blending=BlendingMode.Standard,
        bpp=BitDepth.Bit4,
    )


def _mesh(palette_coords: list[tuple[int, int]]) -> CtrMesh:
    return CtrMesh(texture_layouts=[_layout(x, y) for x, y in palette_coords])


def _kart_slot(name: str, vram_x: int, vram_y: int) -> SlotProfile:
    return SlotProfile(name=name, clut_race=ClutCoord(x=vram_x, y=vram_y))


class TestSkinSlotDeriver:

    def setup_method(self) -> None:
        self._deriver = SkinSlotDeriver()

    def test_palette_grid_coords_are_multiplied_by_16_to_get_vram_x(self) -> None:
        # palette_x=7 → vram_x=112; palette_x=19 → vram_x=304.
        mesh = _mesh([(7, 255), (19, 252)])

        slots = self._deriver.derive(mesh, kart_slots=[])

        assert {(s.clut_race.x, s.clut_race.y) for s in slots} == {(112, 255), (304, 252)}

    def test_kart_slots_are_excluded(self) -> None:
        mesh = _mesh([(7, 255), (7, 250), (7, 253)])
        kart = [_kart_slot("front", 112, 255), _kart_slot("back", 112, 250)]

        slots = self._deriver.derive(mesh, kart_slots=kart)

        assert [(s.clut_race.x, s.clut_race.y) for s in slots] == [(112, 253)]

    def test_distinct_clut_coords_are_deduplicated(self) -> None:
        # 5 layouts but only 2 distinct CLUTs.
        mesh = _mesh([(7, 255), (7, 255), (7, 250), (7, 250), (7, 250)])

        slots = self._deriver.derive(mesh, kart_slots=[])

        assert len(slots) == 2

    def test_skin_slots_are_named_extra_x_y(self) -> None:
        mesh = _mesh([(7, 253)])

        slots = self._deriver.derive(mesh, kart_slots=[])

        assert slots[0].name == "extra_112_253"

    def test_clut_menu_is_none_for_derived_slots(self) -> None:
        mesh = _mesh([(7, 253)])

        slots = self._deriver.derive(mesh, kart_slots=[])

        assert slots[0].clut_menu is None

    def test_results_are_sorted_by_y_then_x(self) -> None:
        mesh = _mesh([(19, 253), (7, 255), (7, 250), (19, 250)])

        slots = self._deriver.derive(mesh, kart_slots=[])

        assert [(s.clut_race.x, s.clut_race.y) for s in slots] == [
            (112, 250),
            (304, 250),
            (304, 253),
            (112, 255),
        ]

    def test_returns_empty_when_every_clut_is_a_kart_slot(self) -> None:
        mesh = _mesh([(7, 255), (7, 250)])
        kart = [_kart_slot("front", 112, 255), _kart_slot("back", 112, 250)]

        assert self._deriver.derive(mesh, kart_slots=kart) == []

    def test_returns_empty_for_mesh_without_layouts(self) -> None:
        assert self._deriver.derive(CtrMesh(), kart_slots=[]) == []
