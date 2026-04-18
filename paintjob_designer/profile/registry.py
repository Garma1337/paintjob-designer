# coding: utf-8

import sys
from pathlib import Path

from paintjob_designer.models import Profile
from paintjob_designer.profile.reader import ProfileReader


def _bundled_profiles_dir() -> Path:
    """Resolve `config/profiles/` whether we're running from source or a
    PyInstaller one-file bundle.

    In a PyInstaller build the data files live under `sys._MEIPASS/config/profiles`
    (see `packaging/paintjob-designer.spec`). Outside the bundle we fall back to
    walking up from this file to the repo root — same layout the tests expect.
    """
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass) / "config" / "profiles"

    return Path(__file__).parent.parent.parent / "config" / "profiles"


_BUNDLED_PROFILES_DIR = _bundled_profiles_dir()


class ProfileRegistry:
    """Enumerates and loads the built-in profiles shipped under
    `paintjob_designer/profiles/`. Third-party profiles can be loaded directly
    via `ProfileReader` without going through the registry.
    """

    def __init__(self, profile_reader: ProfileReader) -> None:
        self._reader = profile_reader

    def available(self) -> list[str]:
        """Return sorted list of profile IDs that ship with the tool."""
        return sorted(p.stem for p in _BUNDLED_PROFILES_DIR.glob("*.json"))

    def load(self, profile_id: str) -> Profile:
        path = _BUNDLED_PROFILES_DIR / f"{profile_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"Bundled profile not found: {profile_id!r}")

        return self._reader.read(path.read_bytes())
