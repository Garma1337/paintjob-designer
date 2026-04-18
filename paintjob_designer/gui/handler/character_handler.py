# coding: utf-8

from dataclasses import dataclass
from pathlib import Path

from paintjob_designer.ctr.reader import CtrModelReader
from paintjob_designer.models import (
    CharacterProfile,
    CharacterSlotRegions,
    CtrMesh,
    Paintjob,
)
from paintjob_designer.render.atlas_renderer import AtlasRenderer
from paintjob_designer.render.slot_region_deriver import SlotRegionDeriver
from paintjob_designer.vram.cache import VramCache


@dataclass
class BroughtUpCharacter:
    """Everything the UI needs to display one character at a given paintjob state.

    `mesh` is kept on the bundle so the 3D viewer can run the vertex assembler
    itself; the 2D preview only uses `atlas_rgba` + `slot_regions`.
    """
    character_id: str
    mesh: CtrMesh
    slot_regions: CharacterSlotRegions
    atlas_rgba: bytearray  # 4096x512 RGBA (AtlasRenderer output)


class CharacterHandler:
    """Orchestrates character bring-up: `.ctr` parse + VRAM load + slot derivation + atlas render.

    Headless — returns a `BroughtUpCharacter` bundle that the widget layer can
    consume. No Qt imports here. VRAM caching lives in the shared `VramCache`
    so color-edit re-renders hit the same decoded 1 MB blob instead of re-reading
    `shared.vrm` each stroke.
    """

    def __init__(
        self,
        ctr_model_reader: CtrModelReader,
        vram_cache: VramCache,
        slot_region_deriver: SlotRegionDeriver,
        atlas_renderer: AtlasRenderer,
    ) -> None:
        self._ctr_reader = ctr_model_reader
        self._vram_cache = vram_cache
        self._deriver = slot_region_deriver
        self._atlas = atlas_renderer

    def load_character(
        self,
        iso_root: str | Path,
        character: CharacterProfile,
        paintjob: Paintjob,
    ) -> BroughtUpCharacter:
        vram = self._vram_cache.get(iso_root)

        ctr_path = Path(iso_root) / character.mesh_source
        model = self._ctr_reader.read(ctr_path.read_bytes())
        mesh = model.meshes[0]

        regions = self._deriver.derive(mesh, character)
        atlas = self._atlas.render_atlas(vram, paintjob, character.id, regions)

        return BroughtUpCharacter(
            character_id=character.id,
            mesh=mesh,
            slot_regions=regions,
            atlas_rgba=atlas,
        )

    def invalidate_vram_cache(self) -> None:
        """Drop the cached VRAM page so the next load re-reads `shared.vrm`.

        Call when the user points at a different ISO root.
        """
        self._vram_cache.invalidate()
