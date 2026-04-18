# coding: utf-8

from pathlib import Path

from paintjob_designer.models import VramPage
from paintjob_designer.vram.reader import VramReader

# Relative to the extracted-ISO root. `shared.vrm` carries the kart texture
# pixels + default CLUTs; it's the same blob across every character, so we load
# it once per iso_root and keep it in memory for the session.
_SHARED_VRM_RELATIVE = "bigfile/packs/shared.vrm"


class VramCache:
    """Keeps a single decoded `VramPage` in memory, keyed by iso_root.

    Shared by every handler that needs VRAM (character bring-up, color edits,
    future 3D viewer) so the 1 MB `shared.vrm` decode happens exactly once per
    iso_root change.
    """

    def __init__(self, vram_reader: VramReader) -> None:
        self._reader = vram_reader
        self._cache: VramPage | None = None
        self._cache_root: str = ""

    def get(self, iso_root: str | Path) -> VramPage:
        key = str(Path(iso_root))

        if self._cache is None or self._cache_root != key:
            vrm_bytes = (Path(iso_root) / _SHARED_VRM_RELATIVE).read_bytes()
            self._cache = self._reader.read(vrm_bytes)
            self._cache_root = key

        return self._cache

    def invalidate(self) -> None:
        self._cache = None
        self._cache_root = ""
