# coding: utf-8

from paintjob_designer.models import (
    BitDepth,
    BlendingMode,
    CharacterProfile,
    ClutCoord,
    CtrMesh,
    SlotProfile,
    TextureLayout,
)


def _tl(
    palette_x: int = 0,
    palette_y: int = 0,
    page_x: int = 0,
    page_y: int = 0,
    bpp: BitDepth = BitDepth.Bit4,
    blending: BlendingMode = BlendingMode.Standard,
    uvs: tuple[tuple[int, int], tuple[int, int], tuple[int, int], tuple[int, int]] = (
        (0, 0), (0, 0), (0, 0), (0, 0),
    ),
) -> TextureLayout:
    (u0, v0), (u1, v1), (u2, v2), (u3, v3) = uvs
    return TextureLayout(
        uv0_u=u0, uv0_v=v0, uv1_u=u1, uv1_v=v1,
        uv2_u=u2, uv2_v=v2, uv3_u=u3, uv3_v=v3,
        palette_x=palette_x, palette_y=palette_y,
        page_x=page_x, page_y=page_y,
        blending=blending, bpp=bpp,
    )


def _character(slots: list[tuple[str, int, int]]) -> CharacterProfile:
    return CharacterProfile(
        id="test",
        display_name="Test",
        slots=[
            SlotProfile(name=name, clut=ClutCoord(x=x, y=y))
            for name, x, y in slots
        ],
    )


class TestEmptyInputs:

    def test_empty_mesh_yields_empty_result(self, slot_region_deriver):
        result = slot_region_deriver.derive(CtrMesh(), _character([]))

        assert result.slots == {}
        assert result.unmatched_regions == []

    def test_mesh_with_no_matching_slot_goes_to_unmatched(self, slot_region_deriver):
        # TL has palette at (3, 10) -> VRAM CLUT at (48, 10); character has no slot there.
        mesh = CtrMesh(texture_layouts=[_tl(palette_x=3, palette_y=10)])

        result = slot_region_deriver.derive(mesh, _character([]))

        assert result.slots == {}
        assert len(result.unmatched_regions) == 1
        assert result.unmatched_regions[0].clut == ClutCoord(x=48, y=10)
        assert len(result.unmatched_regions[0].regions) == 1


class TestSingleSlot:

    def test_single_tl_matches_slot_and_produces_one_region(self, slot_region_deriver):
        # palette (7, 255) -> CLUT (112, 255) matches Saphi's crash "front" slot.
        mesh = CtrMesh(texture_layouts=[_tl(
            palette_x=7, palette_y=255,
            page_x=2, page_y=1,
            bpp=BitDepth.Bit4,
            uvs=((0, 0), (64, 0), (0, 32), (64, 32)),
        )])
        character = _character([("front", 112, 255)])

        result = slot_region_deriver.derive(mesh, character)

        assert "front" in result.slots
        front = result.slots["front"]
        assert front.clut == ClutCoord(x=112, y=255)
        assert len(front.regions) == 1
        region = front.regions[0]
        # vram_x = page_x * 64 + min_u / 4 = 128 + 0 = 128
        # vram_y = page_y * 256 + min_v = 256 + 0 = 256
        # width = (64 - 0) / 4 + 1 = 17
        # height = 32 - 0 + 1 = 33
        assert region.vram_x == 128
        assert region.vram_y == 256
        assert region.vram_width == 17
        assert region.vram_height == 33
        assert region.bpp == BitDepth.Bit4
        assert region.texture_layout_indices == [0]

    def test_multiple_tls_same_palette_merge_into_one_bounding_region(self, slot_region_deriver):
        # Two triangles sharing a palette → single region with combined bbox.
        mesh = CtrMesh(texture_layouts=[
            _tl(palette_x=7, palette_y=255, uvs=((0, 0), (32, 0), (0, 16), (32, 16))),
            _tl(palette_x=7, palette_y=255, uvs=((32, 16), (64, 16), (32, 32), (64, 32))),
        ])
        character = _character([("front", 112, 255)])

        result = slot_region_deriver.derive(mesh, character)

        front = result.slots["front"]
        assert len(front.regions) == 1
        region = front.regions[0]
        # Combined u range 0..64, v range 0..32 (uv[3] is ignored).
        # In 4bpp: width = 64/4 + 1 = 17, height = 32 + 1 = 33.
        assert region.vram_x == 0
        assert region.vram_y == 0
        assert region.vram_width == 17
        assert region.vram_height == 33
        assert region.texture_layout_indices == [0, 1]


class TestBppStretching:

    def test_bit4_width_is_quartered(self, slot_region_deriver):
        mesh = CtrMesh(texture_layouts=[_tl(
            palette_x=0, palette_y=0,
            bpp=BitDepth.Bit4,
            uvs=((0, 0), (32, 0), (0, 4), (32, 4)),
        )])
        character = _character([("front", 0, 0)])

        region = slot_region_deriver.derive(mesh, character).slots["front"].regions[0]

        assert region.vram_width == 32 // 4 + 1

    def test_bit8_width_is_halved(self, slot_region_deriver):
        mesh = CtrMesh(texture_layouts=[_tl(
            palette_x=0, palette_y=0,
            bpp=BitDepth.Bit8,
            uvs=((0, 0), (32, 0), (0, 4), (32, 4)),
        )])
        character = _character([("front", 0, 0)])

        region = slot_region_deriver.derive(mesh, character).slots["front"].regions[0]

        assert region.vram_width == 32 // 2 + 1

    def test_bit16_width_is_not_stretched(self, slot_region_deriver):
        mesh = CtrMesh(texture_layouts=[_tl(
            palette_x=0, palette_y=0,
            bpp=BitDepth.Bit16,
            uvs=((0, 0), (32, 0), (0, 4), (32, 4)),
        )])
        character = _character([("front", 0, 0)])

        region = slot_region_deriver.derive(mesh, character).slots["front"].regions[0]

        assert region.vram_width == 32 + 1


class TestPageGrouping:

    def test_same_palette_on_different_pages_produces_two_regions(self, slot_region_deriver):
        # A single slot whose CLUT is sampled from two pages -> two rectangles.
        mesh = CtrMesh(texture_layouts=[
            _tl(palette_x=7, palette_y=255, page_x=1, page_y=0,
                uvs=((0, 0), (32, 0), (0, 4), (32, 4))),
            _tl(palette_x=7, palette_y=255, page_x=2, page_y=1,
                uvs=((0, 0), (32, 0), (0, 4), (32, 4))),
        ])
        character = _character([("front", 112, 255)])

        result = slot_region_deriver.derive(mesh, character)

        front = result.slots["front"]
        assert len(front.regions) == 2

        starts = sorted((r.vram_x, r.vram_y) for r in front.regions)
        assert starts == [(64, 0), (128, 256)]


class TestUnmatched:

    def test_unmatched_regions_share_entry_across_pages(self, slot_region_deriver):
        # Two TLs with the same unmapped palette on different pages -> one
        # SlotRegions bucket containing both regions.
        mesh = CtrMesh(texture_layouts=[
            _tl(palette_x=30, palette_y=200),
            _tl(palette_x=30, palette_y=200, page_x=1),
        ])

        result = slot_region_deriver.derive(mesh, _character([]))

        assert len(result.unmatched_regions) == 1
        assert result.unmatched_regions[0].clut == ClutCoord(x=480, y=200)
        assert len(result.unmatched_regions[0].regions) == 2

    def test_mixed_matched_and_unmatched(self, slot_region_deriver):
        mesh = CtrMesh(texture_layouts=[
            _tl(palette_x=7, palette_y=255),   # -> CLUT (112, 255) matches 'front'
            _tl(palette_x=30, palette_y=200),  # -> CLUT (480, 200) unmatched
        ])
        character = _character([("front", 112, 255)])

        result = slot_region_deriver.derive(mesh, character)

        assert "front" in result.slots
        assert len(result.unmatched_regions) == 1
        assert result.unmatched_regions[0].clut == ClutCoord(x=480, y=200)


class TestMultipleSlots:

    def test_each_palette_routes_to_its_own_slot(self, slot_region_deriver):
        # Two distinct palettes, each matched to a different slot.
        mesh = CtrMesh(texture_layouts=[
            _tl(palette_x=7, palette_y=255),    # front
            _tl(palette_x=7, palette_y=250),    # back
        ])
        character = _character([
            ("front", 112, 255),
            ("back", 112, 250),
        ])

        result = slot_region_deriver.derive(mesh, character)

        assert set(result.slots.keys()) == {"front", "back"}
        assert len(result.slots["front"].regions) == 1
        assert len(result.slots["back"].regions) == 1
