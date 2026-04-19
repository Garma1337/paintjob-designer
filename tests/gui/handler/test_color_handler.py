# coding: utf-8

import struct
from pathlib import Path

import pytest

from paintjob_designer.models import (
    BitDepth,
    ClutCoord,
    Paintjob,
    PsxColor,
    SlotColors,
    SlotRegion,
    SlotRegions,
)
from paintjob_designer.render.atlas_renderer import AtlasRenderer
from tests.conftest import atlas_pixel as _shared_atlas_pixel, build_tim, build_vrm_bytes


def _front_slot() -> SlotRegions:
    return SlotRegions(
        slot_name="front",
        clut=ClutCoord(x=0, y=0),
        regions=[SlotRegion(
            vram_x=50, vram_y=10, vram_width=1, vram_height=1,
            bpp=BitDepth.Bit4,
        )],
    )


def _vrm_bytes_with_defaults() -> bytes:
    """Build a .vrm whose CLUT at (0,0) and a texture nibble at (50,10) are known."""
    # CLUT index 3 = default blue (PSX 0x7C00). Other indices zero.
    clut_pixels = bytearray(32)
    clut_pixels[6:8] = struct.pack("<H", 0x7C00)
    clut_block = build_tim(bpp=0, image={
        "origin_x": 0, "origin_y": 0, "width": 16, "height": 1,
        "pixels": bytes(clut_pixels),
    })
    # Texture: 1 u16 of nibbles all = 3.
    texture_block = build_tim(bpp=2, image={
        "origin_x": 50, "origin_y": 10, "width": 1, "height": 1,
        "pixels": struct.pack("<H", 0x3333),
    })
    return build_vrm_bytes([clut_block, texture_block])


def _write_shared_vrm(root: Path) -> None:
    vrm = root / "bigfile/packs/shared.vrm"
    vrm.parent.mkdir(parents=True, exist_ok=True)
    vrm.write_bytes(_vrm_bytes_with_defaults())


def _atlas_pixel(rgba: bytearray, x: int, y: int) -> tuple[int, int, int, int]:
    return _shared_atlas_pixel(rgba, x, y, AtlasRenderer.ATLAS_WIDTH)


class TestApplyEdit:

    def test_first_edit_initializes_slot_from_vram_defaults(
        self, color_handler, tmp_path,
    ):
        _write_shared_vrm(tmp_path)
        paintjob = Paintjob()
        rgba = bytearray(AtlasRenderer.ATLAS_WIDTH * AtlasRenderer.ATLAS_HEIGHT * 4)
        slot = _front_slot()

        # Edit index 5. The handler should populate all 16 colors from VRAM first,
        # so everything except index 5 keeps the default CLUT values.
        color_handler.apply_edit(
            tmp_path, rgba, paintjob, slot,
            color_index=5, new_color=PsxColor(value=0x001F),
        )

        slot_colors = paintjob.slots["front"].colors
        assert len(slot_colors) == SlotColors.SIZE
        assert slot_colors[5].value == 0x001F
        # Index 3 retained its default blue from VRAM (0x7C00).
        assert slot_colors[3].value == 0x7C00

    def test_subsequent_edit_only_changes_the_one_color(
        self, color_handler, tmp_path,
    ):
        _write_shared_vrm(tmp_path)
        existing = SlotColors(colors=[PsxColor(value=0x1234) for _ in range(16)])
        paintjob = Paintjob(slots={"front": existing})
        rgba = bytearray(AtlasRenderer.ATLAS_WIDTH * AtlasRenderer.ATLAS_HEIGHT * 4)

        color_handler.apply_edit(
            tmp_path, rgba, paintjob, _front_slot(),
            color_index=7, new_color=PsxColor(value=0x7FFF),
        )

        result = paintjob.slots["front"].colors
        assert result[7].value == 0x7FFF
        # Other indices untouched.
        for i in range(16):
            if i == 7:
                continue

            assert result[i].value == 0x1234

    def test_rerenders_slot_in_place_with_new_color(
        self, color_handler, tmp_path,
    ):
        _write_shared_vrm(tmp_path)
        paintjob = Paintjob()
        rgba = bytearray(AtlasRenderer.ATLAS_WIDTH * AtlasRenderer.ATLAS_HEIGHT * 4)

        # Set CLUT index 3 to red. The texture nibbles at VRAM (50, 10) are all 3,
        # so atlas pixels at (200..203, 10) should become red.
        color_handler.apply_edit(
            tmp_path, rgba, paintjob, _front_slot(),
            color_index=3, new_color=PsxColor(value=0x001F),
        )

        for atlas_x in range(200, 204):
            assert _atlas_pixel(rgba, atlas_x, 10) == (255, 0, 0, 255)

    def test_out_of_range_index_raises(self, color_handler, tmp_path):
        _write_shared_vrm(tmp_path)
        paintjob = Paintjob()
        rgba = bytearray(AtlasRenderer.ATLAS_WIDTH * AtlasRenderer.ATLAS_HEIGHT * 4)

        with pytest.raises(IndexError):
            color_handler.apply_edit(
                tmp_path, rgba, paintjob, _front_slot(),
                color_index=16, new_color=PsxColor(),
            )


class TestDefaultSlotColors:

    def test_returns_vram_clut_values(self, color_handler, tmp_path):
        _write_shared_vrm(tmp_path)

        defaults = color_handler.default_slot_colors(tmp_path, _front_slot())

        assert len(defaults) == 16
        # CLUT at (0,0): only index 3 was set to 0x7C00.
        assert defaults[3].value == 0x7C00
        assert defaults[0].value == 0


class TestResetSlot:

    def test_reset_wipes_existing_edits_and_restores_defaults(
        self, color_handler, tmp_path,
    ):
        _write_shared_vrm(tmp_path)
        edited = SlotColors(colors=[PsxColor(value=0xAAAA) for _ in range(16)])
        paintjob = Paintjob(slots={"front": edited})
        rgba = bytearray(AtlasRenderer.ATLAS_WIDTH * AtlasRenderer.ATLAS_HEIGHT * 4)

        defaults = color_handler.reset_slot(
            tmp_path, rgba, paintjob, _front_slot(),
        )

        assert defaults[3].value == 0x7C00
        assert paintjob.slots["front"].colors[3].value == 0x7C00
        assert paintjob.slots["front"] is not edited

    def test_reset_creates_missing_slot(self, color_handler, tmp_path):
        _write_shared_vrm(tmp_path)
        paintjob = Paintjob()
        rgba = bytearray(AtlasRenderer.ATLAS_WIDTH * AtlasRenderer.ATLAS_HEIGHT * 4)

        color_handler.reset_slot(tmp_path, rgba, paintjob, _front_slot())

        assert "front" in paintjob.slots
        assert len(paintjob.slots["front"].colors) == 16

    def test_reset_rerenders_atlas_with_default_colors(self, color_handler, tmp_path):
        _write_shared_vrm(tmp_path)
        paintjob = Paintjob()
        rgba = bytearray(AtlasRenderer.ATLAS_WIDTH * AtlasRenderer.ATLAS_HEIGHT * 4)
        slot = _front_slot()

        # Apply a red edit first.
        color_handler.apply_edit(
            tmp_path, rgba, paintjob, slot,
            color_index=3, new_color=PsxColor(value=0x001F),
        )
        assert _atlas_pixel(rgba, 200, 10) == (255, 0, 0, 255)

        # Reset should return the atlas to the VRAM-default decode (index 3 = blue).
        color_handler.reset_slot(tmp_path, rgba, paintjob, slot)
        assert _atlas_pixel(rgba, 200, 10) == (0, 0, 255, 255)
