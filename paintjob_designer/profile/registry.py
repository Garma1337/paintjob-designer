# coding: utf-8

import sys
from pathlib import Path

from paintjob_designer.models import Profile
from paintjob_designer.profile.reader import ProfileReader


class ProfileRegistry:
    """Enumerates and loads the built-in profiles shipped under
    `config/profiles/`. Third-party profiles can be loaded directly via
    `ProfileReader` without going through the registry."""

    def __init__(self, profile_reader: ProfileReader) -> None:
        self._reader = profile_reader
        self._bundled_dir = self._resolve_bundled_dir()

    def available(self) -> list[str]:
        """Return sorted list of profile IDs that ship with the tool."""
        return sorted(p.stem for p in self._bundled_dir.glob("*.json"))

    def load(self, profile_id: str) -> Profile:
        path = self._bundled_dir / f"{profile_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"Bundled profile not found: {profile_id!r}")

        return self._reader.read(path.read_bytes())

    @staticmethod
    def _resolve_bundled_dir() -> Path:
        """Resolve `config/profiles/` whether we're running from source or a PyInstaller one-file bundle."""
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass) / "config" / "profiles"

        return Path(__file__).parent.parent.parent / "config" / "profiles"
