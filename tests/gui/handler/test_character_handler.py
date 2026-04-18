# coding: utf-8

import struct
from pathlib import Path

from paintjob_designer.models import (
    BitDepth,
    CharacterProfile,
    ClutCoord,
    Paintjob,
    SlotProfile,
)
from paintjob_designer.render.atlas_renderer import AtlasRenderer
from tests.conftest import build_ctr_bytes, build_tim, build_vrm_bytes


def _triangle_commands() -> list[int]:
    # Minimal 3-command tristrip, textured (tex_index=1).
    base = 1  # tex_index=1
    return [
        (1 << 31) | (0 << 16) | base,
        (1 << 16) | base,
        (2 << 16) | base,
    ]


def _write_iso(
    root: Path,
    mesh_bytes: bytes,
    vrm_bytes: bytes,
    mesh_relative: str = "bigfile/models/racers/hi/crash.ctr",
) -> None:
    mesh_path = root / mesh_relative
    mesh_path.parent.mkdir(parents=True, exist_ok=True)
    mesh_path.write_bytes(mesh_bytes)

    vrm_path = root / "bigfile/packs/shared.vrm"
    vrm_path.parent.mkdir(parents=True, exist_ok=True)
    vrm_path.write_bytes(vrm_bytes)


def _minimal_character_profile() -> CharacterProfile:
    return CharacterProfile(
        id="crash",
        display_name="Crash",
        mesh_source="bigfile/models/racers/hi/crash.ctr",
        slots=[
            SlotProfile(name="front", clut=ClutCoord(x=0, y=0)),
        ],
    )


def _mesh_bytes_with_slot_region() -> bytes:
    """Synthetic .ctr where one TL's palette matches the 'front' slot at (0, 0)."""
    # palette_x=0, palette_y=0 -> CLUT coord (0, 0) matches SlotProfile.clut.
    # Keep UVs small so the slot region fits in our synthetic VRAM.
    return build_ctr_bytes(meshes=[{
        "commands": _triangle_commands(),
        "vertices": [(0, 0, 0)] * 3,
        "texture_layouts": [{
            "uv0_u": 0, "uv0_v": 0,
            "uv1_u": 3, "uv1_v": 0,
            "uv2_u": 0, "uv2_v": 0,
            "uv3_u": 3, "uv3_v": 0,
            "palette_x": 0, "palette_y": 0,
            "page_x": 4, "page_y": 0,  # page offset pushes texture to VRAM x=256
            "bpp": BitDepth.Bit4,
        }],
    }])


def _vrm_bytes_with_clut_at_origin() -> bytes:
    """VRM that paints CLUT index 3 = pure red at VRAM (0, 0)..(15, 0)."""
    clut_pixels = bytearray(32)  # 16 u16s
    clut_pixels[6:8] = struct.pack("<H", 0x001F)  # index 3 = red
    return build_vrm_bytes([build_tim(
        bpp=0,
        image={"origin_x": 0, "origin_y": 0, "width": 16, "height": 1,
               "pixels": bytes(clut_pixels)},
    )])


class TestLoadCharacter:

    def test_loads_ctr_and_builds_atlas(self, character_handler, tmp_path):
        _write_iso(tmp_path, _mesh_bytes_with_slot_region(), _vrm_bytes_with_clut_at_origin())

        result = character_handler.load_character(
            tmp_path, _minimal_character_profile(), Paintjob(),
        )

        assert result.character_id == "crash"
        assert "front" in result.slot_regions.slots
        assert len(result.atlas_rgba) == AtlasRenderer.ATLAS_WIDTH * AtlasRenderer.ATLAS_HEIGHT * 4

    def test_slot_regions_are_derived_from_mesh_texture_layouts(
        self, character_handler, tmp_path,
    ):
        _write_iso(tmp_path, _mesh_bytes_with_slot_region(), _vrm_bytes_with_clut_at_origin())

        result = character_handler.load_character(
            tmp_path, _minimal_character_profile(), Paintjob(),
        )

        front_regions = result.slot_regions.slots["front"].regions
        assert len(front_regions) == 1
        assert front_regions[0].bpp == BitDepth.Bit4

    def test_missing_mesh_file_raises(self, character_handler, tmp_path):
        # Write VRAM but no .ctr so the mesh_source path doesn't exist.
        vrm_path = tmp_path / "bigfile/packs/shared.vrm"
        vrm_path.parent.mkdir(parents=True, exist_ok=True)
        vrm_path.write_bytes(_vrm_bytes_with_clut_at_origin())

        try:
            character_handler.load_character(
                tmp_path, _minimal_character_profile(), Paintjob(),
            )
        except FileNotFoundError:
            return
        raise AssertionError("Expected FileNotFoundError for missing .ctr")


class TestVramCacheInvalidation:

    def test_invalidate_vram_cache_forces_reload(
        self, character_handler, tmp_path, monkeypatch,
    ):
        _write_iso(tmp_path, _mesh_bytes_with_slot_region(), _vrm_bytes_with_clut_at_origin())
        profile = _minimal_character_profile()

        read_calls = 0
        reader = character_handler._vram_cache._reader
        original = reader.read

        def counting_read(data):
            nonlocal read_calls
            read_calls += 1
            return original(data)

        monkeypatch.setattr(reader, "read", counting_read)

        character_handler.load_character(tmp_path, profile, Paintjob())
        character_handler.invalidate_vram_cache()
        character_handler.load_character(tmp_path, profile, Paintjob())

        assert read_calls == 2
