# coding: utf-8

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class AppConfig:
    """Per-user settings persisted between sessions.

    `iso_root` is the path the user chose on first launch, rooting all `.ctr`
    and `.vrm` lookups. Empty string means the first-run flow still needs to run.
    """
    iso_root: str = ""
    last_profile_id: str = "vanilla-ntsc-u"


class ConfigStore:
    """Loads and saves `AppConfig` as JSON at a caller-supplied path.

    Keeping the path injected (rather than computing it inside the class) means
    this stays Qt-free and headlessly testable. `main.py` / `services.py`
    resolves the platform location via `QStandardPaths` and passes it in.
    """

    def __init__(self, path: Path) -> None:
        self._path = path

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> AppConfig:
        """Return the stored config, or a default if nothing has been saved yet."""
        if not self._path.exists():
            return AppConfig()

        raw = json.loads(self._path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return AppConfig()

        return AppConfig(
            iso_root=str(raw.get("iso_root", "")),
            last_profile_id=str(raw.get("last_profile_id", "vanilla-ntsc-u")),
        )

    def save(self, config: AppConfig) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "iso_root": config.iso_root,
            "last_profile_id": config.last_profile_id,
        }

        self._path.write_text(json.dumps(data, indent=2), encoding="utf-8")
