# coding: utf-8

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class IsoRootValidation:
    """Result of probing a candidate directory for a usable CTR ISO extract."""
    ok: bool = False
    missing: list[str] = field(default_factory=list)


class IsoRootValidator:
    """Determines whether a directory looks like an extracted CTR (NTSC-U) ISO.

    Probes for a small set of files the designer needs — at least one character
    `.ctr` plus `shared.vrm` (source of kart texture pixels). Keeping it headless
    lets the first-run dialog run the same check as any scripted bring-up.
    """

    _REQUIRED_FILES = (
        "bigfile/models/racers/hi/crash.ctr",
        "bigfile/packs/shared.vrm",
    )

    def validate(self, iso_root: str | Path) -> IsoRootValidation:
        root = Path(iso_root) if iso_root else None
        if root is None or not root.is_dir():
            return IsoRootValidation(ok=False, missing=list(self._REQUIRED_FILES))

        missing = [p for p in self._REQUIRED_FILES if not (root / p).exists()]
        return IsoRootValidation(ok=not missing, missing=missing)
