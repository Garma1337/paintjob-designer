# coding: utf-8

"""Dump per-CLUT palette strips and decoded sample regions for a racer .ctr.

Use this when authoring a new `CharacterProfile` for a racer that doesn't
yet have one. For each unique CLUT used by the mesh, the script writes:

    out/clut_<palette_x>_<palette_y>_palette.png  16-swatch palette strip
    out/clut_<palette_x>_<palette_y>_regions.png  every textured region
                                                  that samples this CLUT,
                                                  4bpp-decoded and tiled

Plus `out/manifest.json` listing each CLUT's coordinates, the number of
regions that use it, and an empty `name` field — fill it in as you identify
which palette colors which body part, then transcribe into a profile.

Usage (from repo root, with the venv active):

    python tools/inspect_clut_palette.py \\
        --ctr  /path/to/Saphi-Dev/build/ctr-u/bigfile/models/racers/hi/oxide.ctr \\
        --vram /path/to/Saphi-Dev/build/ctr-u/bigfile/packs/shared.vrm \\
        --out  ./oxide_clut_dump
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

# Make `paintjob_designer` importable when running this file directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from paintjob_designer.ctr.animation import AnimationDecoder
from paintjob_designer.ctr.reader import CtrModelReader
from paintjob_designer.models import (
    BitDepth,
    CharacterProfile,
    SlotRegion,
    VramPage,
)
from paintjob_designer.render.psx_rgba_lut import PsxRgbaLut
from paintjob_designer.render.slot_region_deriver import SlotRegionDeriver
from paintjob_designer.vram.reader import VramReader


_SWATCH_SIZE = 32  # px per palette swatch in the strip
_REGION_UPSCALE = 2  # nearest-neighbor upscale for region thumbnails
_TILE_GAP = 4
_TILE_BG = (50, 50, 50, 255)


def main() -> int:
    args = _parse_args()

    ctr_bytes = Path(args.ctr).read_bytes()
    vram_bytes = Path(args.vram).read_bytes()

    model = CtrModelReader(AnimationDecoder()).read(ctr_bytes)
    vram = VramReader().read(vram_bytes)

    if len(model.meshes) != 1:
        print(
            f"warning: expected a single-mesh racer, got {len(model.meshes)} "
            f"meshes; using meshes[0]"
        )

    mesh = model.meshes[0]

    # An empty CharacterProfile has no slots, so every grouped CLUT ends up
    # in `unmatched_regions` — exactly what we want when there is no profile
    # yet for this racer.
    derived = SlotRegionDeriver().derive(
        mesh,
        CharacterProfile(
            id="dump", display_name="dump", mesh_source="",
            kart_slots=[], skin_slots=[],
        ),
    )

    lut = PsxRgbaLut().as_array()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    manifest: list[dict] = []
    for slot_regions in derived.unmatched_regions:
        clut_x = slot_regions.clut.x
        clut_y = slot_regions.clut.y
        palette_x = clut_x // 16
        palette_y = clut_y
        prefix = f"clut_{palette_x:02d}_{palette_y:03d}"

        clut_values = _read_clut(vram, clut_x, clut_y)
        _render_palette_strip(clut_values, lut).save(
            out / f"{prefix}_palette.png",
        )

        regions_img = _render_regions_strip(
            vram, slot_regions.regions, clut_values, lut,
        )
        if regions_img is not None:
            regions_img.save(out / f"{prefix}_regions.png")

        manifest.append({
            "palette_x": palette_x,
            "palette_y": palette_y,
            "vram_pixel_x": clut_x,
            "vram_pixel_y": clut_y,
            "region_count": len(slot_regions.regions),
            "name": "",
            "profile_entry": {
                "name": "",
                "clut": {"x": clut_x, "y": clut_y},
            },
        })

    (out / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8",
    )
    print(f"Wrote {len(manifest)} CLUT dumps to {out}")
    return 0


def _read_clut(vram: VramPage, clut_x: int, clut_y: int) -> list[int]:
    values: list[int] = []
    base = (clut_y * VramPage.WIDTH + clut_x) * VramPage.BYTES_PER_PIXEL
    for i in range(16):
        off = base + i * 2
        values.append(vram.data[off] | (vram.data[off + 1] << 8))
    return values


def _render_palette_strip(clut_values: list[int], lut: np.ndarray) -> Image.Image:
    """16 swatches arranged left-to-right; transparent entries show as a
    checker so they're visibly distinct from opaque black."""
    swatch = _SWATCH_SIZE
    strip = np.zeros((swatch, swatch * 16, 4), dtype=np.uint8)
    checker = _checker_tile(swatch)

    for i, value in enumerate(clut_values):
        packed = int(lut[value])
        rgba = (
            packed & 0xFF,
            (packed >> 8) & 0xFF,
            (packed >> 16) & 0xFF,
            (packed >> 24) & 0xFF,
        )
        cell = strip[:, i * swatch:(i + 1) * swatch]
        if rgba[3] == 0:
            cell[:] = checker
        else:
            cell[:] = rgba

    return Image.fromarray(strip, "RGBA")


def _checker_tile(size: int) -> np.ndarray:
    tile = np.zeros((size, size, 4), dtype=np.uint8)
    a = np.array((180, 180, 180, 255), dtype=np.uint8)
    b = np.array((90, 90, 90, 255), dtype=np.uint8)
    for y in range(size):
        for x in range(size):
            tile[y, x] = a if ((x // 4) + (y // 4)) % 2 == 0 else b
    return tile


def _render_regions_strip(
    vram: VramPage,
    regions: list[SlotRegion],
    clut_values: list[int],
    lut: np.ndarray,
) -> Image.Image | None:
    """Decode every 4bpp region using the supplied CLUT and tile them
    horizontally. 8/16/24bpp regions are skipped — the designer only paints
    4bpp anyway."""
    decoded: list[np.ndarray] = []
    for region in regions:
        img = _decode_region_4bpp(vram, region, clut_values, lut)
        if img is not None:
            decoded.append(img)

    if not decoded:
        return None

    height = max(img.shape[0] for img in decoded)
    total_w = sum(img.shape[1] for img in decoded) + _TILE_GAP * (len(decoded) - 1)
    grid = np.zeros((height, total_w, 4), dtype=np.uint8)
    grid[:] = _TILE_BG

    x = 0
    for img in decoded:
        h, w = img.shape[:2]
        grid[:h, x:x + w] = img
        x += w + _TILE_GAP

    upscaled = np.repeat(
        np.repeat(grid, _REGION_UPSCALE, axis=0), _REGION_UPSCALE, axis=1,
    )
    return Image.fromarray(upscaled, "RGBA")


def _decode_region_4bpp(
    vram: VramPage,
    region: SlotRegion,
    clut_values: list[int],
    lut: np.ndarray,
) -> np.ndarray | None:
    if region.bpp != BitDepth.Bit4:
        return None

    stretch = 4
    h = region.vram_height
    w = region.vram_width * stretch
    out = np.zeros((h, w, 4), dtype=np.uint8)

    for row in range(h):
        atlas_y = region.vram_y + row
        if atlas_y >= VramPage.HEIGHT:
            break
        row_base = atlas_y * VramPage.WIDTH * VramPage.BYTES_PER_PIXEL
        for col in range(region.vram_width):
            vram_x = region.vram_x + col
            if vram_x >= VramPage.WIDTH:
                break
            off = row_base + vram_x * VramPage.BYTES_PER_PIXEL
            u16 = vram.data[off] | (vram.data[off + 1] << 8)
            for nibble in range(stretch):
                idx = (u16 >> (nibble * 4)) & 0xF
                packed = int(lut[clut_values[idx]])
                out[row, col * stretch + nibble] = (
                    packed & 0xFF,
                    (packed >> 8) & 0xFF,
                    (packed >> 16) & 0xFF,
                    (packed >> 24) & 0xFF,
                )

    return out


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__.strip().splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--ctr", required=True, help="path to racer .ctr")
    p.add_argument("--vram", required=True, help="path to .vrm (typically shared.vrm)")
    p.add_argument("--out", required=True, help="output directory")
    return p.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
