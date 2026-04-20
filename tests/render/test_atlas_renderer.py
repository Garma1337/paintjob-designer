# coding: utf-8

from paintjob_designer.models import (
    BitDepth,
    CharacterSlotRegions,
    ClutCoord,
    Paintjob,
    PsxColor,
    SlotColors,
    SlotRegion,
    SlotRegionPixels,
    SlotRegions,
    VramPage,
)
from paintjob_designer.render.atlas_renderer import AtlasRenderer
from tests.conftest import atlas_pixel as _shared_atlas_pixel


def _write_u16(page: VramPage, x: int, y: int, value: int) -> None:
    offset = (y * VramPage.WIDTH + x) * VramPage.BYTES_PER_PIXEL
    page.data[offset] = value & 0xFF
    page.data[offset + 1] = (value >> 8) & 0xFF


def _atlas_pixel(rgba: bytearray, x: int, y: int) -> tuple[int, int, int, int]:
    # Thin wrapper that pins the atlas width to AtlasRenderer's constant so
    # callers don't have to repeat it. The shared helper does the offset math.
    return _shared_atlas_pixel(rgba, x, y, AtlasRenderer.ATLAS_WIDTH)


class TestOutputShape:

    def test_render_returns_stretched_rgba_buffer(self, atlas_renderer):
        rgba = atlas_renderer.render_atlas(
            VramPage(), Paintjob(), CharacterSlotRegions(),
        )

        assert len(rgba) == 4096 * 512 * 4
        assert AtlasRenderer.ATLAS_WIDTH == 4096
        assert AtlasRenderer.ATLAS_HEIGHT == 512


class TestBaseline16bpp:

    def test_zero_vram_produces_transparent_atlas(self, atlas_renderer):
        rgba = atlas_renderer.render_atlas(
            VramPage(), Paintjob(), CharacterSlotRegions(),
        )

        # Every pixel should be (0, 0, 0, 0) — PSX value 0 is transparent.
        assert _atlas_pixel(rgba, 0, 0) == (0, 0, 0, 0)
        assert _atlas_pixel(rgba, 2000, 250) == (0, 0, 0, 0)

    def test_non_zero_vram_decodes_as_16bpp_color_stretched_4x(self, atlas_renderer):
        # PSX value 0x7FFF = (r=31, g=31, b=31) = white.
        vram = VramPage()
        _write_u16(vram, 10, 20, 0x7FFF)

        rgba = atlas_renderer.render_atlas(
            vram, Paintjob(), CharacterSlotRegions(),
        )

        # VRAM pixel (10, 20) -> atlas pixels (40..43, 20), all white.
        for atlas_x in range(40, 44):
            assert _atlas_pixel(rgba, atlas_x, 20) == (255, 255, 255, 255)
        # Adjacent VRAM pixel (11, 20) is zero -> atlas (44..47, 20) transparent.
        assert _atlas_pixel(rgba, 44, 20) == (0, 0, 0, 0)


class TestSlotDecodeWith4bpp:

    def test_4bpp_region_decodes_nibbles_through_vram_clut(self, atlas_renderer):
        vram = VramPage()

        # CLUT at (0, 0): 16 distinct 15-bit colors. index 0 is transparent.
        # We'll use index 5 with a recognisable value (0x7C00 = pure blue).
        _write_u16(vram, 0, 0, 0)          # index 0: transparent
        _write_u16(vram, 5, 0, 0x7C00)     # index 5: blue

        # One VRAM u16 of 4bpp texture pixels at (100, 50).
        # Nibbles (low to high): 5, 5, 5, 5 -> u16 = 0x5555.
        _write_u16(vram, 100, 50, 0x5555)

        region = SlotRegion(
            vram_x=100, vram_y=50, vram_width=1, vram_height=1,
            bpp=BitDepth.Bit4,
        )
        regions = CharacterSlotRegions(
            character_id="crash",
            slots={"front": SlotRegions(
                slot_name="front",
                clut=ClutCoord(x=0, y=0),
                regions=[region],
            )},
        )

        rgba = atlas_renderer.render_atlas(vram, Paintjob(), regions)

        # VRAM (100, 50) spans atlas (400..403, 50). All four nibbles are index 5
        # -> all blue.
        for atlas_x in range(400, 404):
            assert _atlas_pixel(rgba, atlas_x, 50) == (0, 0, 255, 255)

    def test_paintjob_overrides_default_clut(self, atlas_renderer):
        vram = VramPage()
        # Default CLUT index 0 = transparent, index 3 = blue (0x7C00 in VRAM).
        _write_u16(vram, 3, 0, 0x7C00)
        # 4bpp texture: 1 u16, all nibbles = 3.
        _write_u16(vram, 50, 10, 0x3333)

        # Paintjob replaces CLUT index 3 with red (PSX 0x001F).
        red_colors = [PsxColor(value=0) for _ in range(16)]
        red_colors[3] = PsxColor(value=0x001F)
        paintjob = Paintjob(slots={"front": SlotColors(colors=red_colors)})

        region = SlotRegion(
            vram_x=50, vram_y=10, vram_width=1, vram_height=1,
            bpp=BitDepth.Bit4,
        )
        regions = CharacterSlotRegions(
            character_id="crash",
            slots={"front": SlotRegions(
                slot_name="front", clut=ClutCoord(x=0, y=0), regions=[region],
            )},
        )

        rgba = atlas_renderer.render_atlas(vram, paintjob, regions)

        # Atlas pixels at the region now show the paintjob's red, not the default blue.
        for atlas_x in range(200, 204):
            assert _atlas_pixel(rgba, atlas_x, 10) == (255, 0, 0, 255)

    def test_missing_paintjob_falls_back_to_vram_default(self, atlas_renderer):
        vram = VramPage()
        _write_u16(vram, 3, 0, 0x7C00)  # default CLUT index 3 = blue
        _write_u16(vram, 50, 10, 0x3333)

        region = SlotRegion(
            vram_x=50, vram_y=10, vram_width=1, vram_height=1,
            bpp=BitDepth.Bit4,
        )
        regions = CharacterSlotRegions(
            character_id="crash",
            slots={"front": SlotRegions(
                slot_name="front", clut=ClutCoord(x=0, y=0), regions=[region],
            )},
        )

        # Paintjob has NO entry for this slot -> default VRAM CLUT is used.
        rgba = atlas_renderer.render_atlas(vram, Paintjob(), regions)

        assert _atlas_pixel(rgba, 200, 10) == (0, 0, 255, 255)


class TestUnmatchedRegions:

    def test_unmatched_region_decoded_through_default_vram_clut(self, atlas_renderer):
        vram = VramPage()
        _write_u16(vram, 5, 0, 0x03E0)  # CLUT index 5 = pure green
        _write_u16(vram, 200, 100, 0x5555)  # 4bpp nibbles all = 5

        unmatched_region = SlotRegion(
            vram_x=200, vram_y=100, vram_width=1, vram_height=1,
            bpp=BitDepth.Bit4,
        )
        regions = CharacterSlotRegions(
            character_id="crash",
            slots={},
            unmatched_regions=[SlotRegions(
                slot_name="unmatched@0,0",
                clut=ClutCoord(x=0, y=0),
                regions=[unmatched_region],
            )],
        )

        rgba = atlas_renderer.render_atlas(vram, Paintjob(), regions)

        # Atlas x=800..803 stretched from VRAM x=200 should all be green.
        for atlas_x in range(800, 804):
            assert _atlas_pixel(rgba, atlas_x, 100) == (0, 255, 0, 255)

    def test_paintjob_slots_dont_leak_into_unmatched(self, atlas_renderer):
        vram = VramPage()
        _write_u16(vram, 5, 0, 0x03E0)  # VRAM default index 5 = green
        _write_u16(vram, 50, 10, 0x5555)

        unmatched_region = SlotRegion(
            vram_x=50, vram_y=10, vram_width=1, vram_height=1,
            bpp=BitDepth.Bit4,
        )
        regions = CharacterSlotRegions(
            character_id="crash",
            unmatched_regions=[SlotRegions(
                slot_name="unmatched@0,0",
                clut=ClutCoord(x=0, y=0),
                regions=[unmatched_region],
            )],
        )

        # Paintjob puts red at index 5 under a matched slot — shouldn't affect
        # the unmatched region, which reads its CLUT straight from VRAM.
        red_colors = [PsxColor(value=0) for _ in range(16)]
        red_colors[5] = PsxColor(value=0x001F)
        paintjob = Paintjob(slots={"some_slot": SlotColors(colors=red_colors)})

        rgba = atlas_renderer.render_atlas(vram, paintjob, regions)

        assert _atlas_pixel(rgba, 200, 10) == (0, 255, 0, 255)


class TestBppFilter:

    def test_non_4bpp_regions_are_skipped(self, atlas_renderer):
        # A Bit16 region shouldn't be re-decoded; baseline 16bpp pass already
        # covered it.
        vram = VramPage()
        _write_u16(vram, 100, 50, 0x7FFF)  # white

        region = SlotRegion(
            vram_x=100, vram_y=50, vram_width=1, vram_height=1,
            bpp=BitDepth.Bit16,
        )
        regions = CharacterSlotRegions(
            character_id="crash",
            slots={"front": SlotRegions(
                slot_name="front", clut=ClutCoord(x=0, y=0), regions=[region],
            )},
        )

        rgba = atlas_renderer.render_atlas(vram, Paintjob(), regions)

        # Unchanged from baseline 16bpp decode: white stretched 4x.
        for atlas_x in range(400, 404):
            assert _atlas_pixel(rgba, atlas_x, 50) == (255, 255, 255, 255)


class TestIncrementalRender:

    def test_render_slot_updates_only_given_regions(self, atlas_renderer):
        vram = VramPage()
        # Seed CLUT + texture bytes.
        _write_u16(vram, 3, 0, 0x7C00)  # default index 3 = blue
        _write_u16(vram, 50, 10, 0x3333)
        # Unrelated baseline pixel we shouldn't clobber.
        _write_u16(vram, 900, 400, 0x7FFF)

        region = SlotRegion(
            vram_x=50, vram_y=10, vram_width=1, vram_height=1,
            bpp=BitDepth.Bit4,
        )
        slot = SlotRegions(
            slot_name="front", clut=ClutCoord(x=0, y=0), regions=[region],
        )

        # First render with an empty paintjob -> region is blue, (900,400) is white.
        regions = CharacterSlotRegions(character_id="crash", slots={"front": slot})
        rgba = atlas_renderer.render_atlas(vram, Paintjob(), regions)
        assert _atlas_pixel(rgba, 200, 10) == (0, 0, 255, 255)
        assert _atlas_pixel(rgba, 3600, 400) == (255, 255, 255, 255)

        # Now apply a paintjob that makes index 3 green, and re-render only the slot.
        green_colors = [PsxColor(value=0) for _ in range(16)]
        green_colors[3] = PsxColor(value=0x03E0)  # pure green
        paintjob = Paintjob(slots={"front": SlotColors(colors=green_colors)})
        atlas_renderer.render_slot(rgba, vram, paintjob, slot)

        # Slot region updated to green.
        assert _atlas_pixel(rgba, 200, 10) == (0, 255, 0, 255)
        # Unrelated baseline pixel untouched.
        assert _atlas_pixel(rgba, 3600, 400) == (255, 255, 255, 255)


class TestPaintjobPixelOverride:
    """Paintjobs with imported textures replace the vanilla VRAM pixels.

    The slot's CLUT already drives color choice; when `SlotColors.pixels`
    is populated, the atlas must also sample the imported indices instead
    of the VRAM-stored ones, so the artist sees their actual PNG (not
    vanilla geometry recolored with the new palette).
    """

    def test_paintjob_pixels_override_vram_at_matching_region(
        self, atlas_renderer,
    ):
        vram = VramPage()
        # VRAM texture at (50, 10): all nibbles = 5 (would decode to whatever
        # the CLUT puts at index 5).
        _write_u16(vram, 50, 10, 0x5555)

        # CLUT: red at index 3, something-else at 5. Paintjob keeps that CLUT.
        red = PsxColor(value=0x001F)
        clut = [PsxColor(value=0) for _ in range(16)]
        clut[3] = red
        clut[5] = PsxColor(value=0x7C00)  # blue — what vanilla would show

        # Imported pixels: all four nibbles = 3 (every byte = 0x33).
        # At vram_width=1, 4bpp → 4 pixels per row, 2 bytes per row.
        override = SlotRegionPixels(
            vram_x=50, vram_y=10, width=4, height=1,
            pixels=bytes([0x33, 0x33]),
        )

        paintjob = Paintjob(
            slots={"front": SlotColors(colors=clut, pixels=[override])},
        )

        region = SlotRegion(
            vram_x=50, vram_y=10, vram_width=1, vram_height=1,
            bpp=BitDepth.Bit4,
        )

        regions = CharacterSlotRegions(
            character_id="crash",
            slots={"front": SlotRegions(
                slot_name="front", clut=ClutCoord(x=0, y=0), regions=[region],
            )},
        )

        rgba = atlas_renderer.render_atlas(vram, paintjob, regions)

        # All four atlas pixels at this region should be red — NOT blue,
        # which is what the vanilla VRAM nibbles would have resolved to.
        for atlas_x in range(200, 204):
            assert _atlas_pixel(rgba, atlas_x, 10) == (255, 0, 0, 255)

    def test_missing_pixel_region_falls_back_to_vram(self, atlas_renderer):
        # Paintjob has pixels for ONE region at (50, 10); a separate region at
        # (80, 10) with the same slot should still decode from VRAM, not skip.
        vram = VramPage()
        _write_u16(vram, 3, 0, 0x03E0)   # VRAM CLUT index 3 = green
        _write_u16(vram, 80, 10, 0x3333)

        clut = [PsxColor(value=0) for _ in range(16)]
        clut[3] = PsxColor(value=0x03E0)  # green in the paintjob CLUT too

        override = SlotRegionPixels(
            vram_x=50, vram_y=10, width=4, height=1,
            pixels=bytes([0x33, 0x33]),
        )

        paintjob = Paintjob(
            slots={"front": SlotColors(colors=clut, pixels=[override])},
        )

        region_with_override = SlotRegion(
            vram_x=50, vram_y=10, vram_width=1, vram_height=1,
            bpp=BitDepth.Bit4,
        )

        region_without_override = SlotRegion(
            vram_x=80, vram_y=10, vram_width=1, vram_height=1,
            bpp=BitDepth.Bit4,
        )

        regions = CharacterSlotRegions(
            character_id="crash",
            slots={"front": SlotRegions(
                slot_name="front", clut=ClutCoord(x=0, y=0),
                regions=[region_with_override, region_without_override],
            )},
        )

        rgba = atlas_renderer.render_atlas(vram, paintjob, regions)

        # The non-override region must still be green (VRAM fallback).
        for atlas_x in range(320, 324):
            assert _atlas_pixel(rgba, atlas_x, 10) == (0, 255, 0, 255)

    def test_size_mismatched_pixel_buffer_is_ignored(self, atlas_renderer):
        # A corrupted pixel buffer (wrong length) should NOT punch a hole
        # in the atlas — the VRAM baseline stays so the preview remains
        # useful.
        vram = VramPage()
        _write_u16(vram, 3, 0, 0x03E0)
        _write_u16(vram, 50, 10, 0x3333)

        clut = [PsxColor(value=0) for _ in range(16)]
        clut[3] = PsxColor(value=0x03E0)

        bad = SlotRegionPixels(
            vram_x=50, vram_y=10, width=4, height=1,
            pixels=bytes([0x33]),  # 1 byte instead of 2
        )

        paintjob = Paintjob(
            slots={"front": SlotColors(colors=clut, pixels=[bad])},
        )

        region = SlotRegion(
            vram_x=50, vram_y=10, vram_width=1, vram_height=1,
            bpp=BitDepth.Bit4,
        )

        regions = CharacterSlotRegions(
            character_id="crash",
            slots={"front": SlotRegions(
                slot_name="front", clut=ClutCoord(x=0, y=0), regions=[region],
            )},
        )

        rgba = atlas_renderer.render_atlas(vram, paintjob, regions)

        # VRAM fallback: index 3 -> green.
        for atlas_x in range(200, 204):
            assert _atlas_pixel(rgba, atlas_x, 10) == (0, 255, 0, 255)
