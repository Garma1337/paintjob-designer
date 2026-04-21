# coding: utf-8

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class AppConfig:
    """Per-user settings persisted between sessions.

    `iso_root` is the path the user chose on first launch, rooting all `.ctr`
    and `.vrm` lookups. Empty string means the first-run flow still needs to run.

    `library` holds the serialized `PaintjobLibrary` (dict shape produced by
    `model_dump(by_alias=True)`) so the in-progress work survives a restart
    without the user having to export. `None` means "no autosaved library
    yet" — distinct from an explicitly-empty library (which serializes to
    a dict with an empty `paintjobs` list).

    `palettes` is the serialized palette library — a list of `{name, colors}`
    dicts (each color a PSX hex string). Saved palettes stay available across
    sessions the same way a desktop art tool's palette library would.
    """
    iso_root: str = ""
    last_profile_id: str = "vanilla-ntsc-u"
    library: dict | None = None
    palettes: list[dict] = field(default_factory=list)


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
            library=self._coerce_library(raw.get("library")),
            palettes=self._coerce_palettes(raw.get("palettes")),
        )

    def save(self, config: AppConfig) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)

        data: dict[str, Any] = {
            "iso_root": config.iso_root,
            "last_profile_id": config.last_profile_id,
            "palettes": list(config.palettes),
        }
        if config.library is not None:
            data["library"] = config.library

        self._path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    @staticmethod
    def _coerce_library(value: Any) -> dict | None:
        if isinstance(value, dict):
            return value
        return None

    @staticmethod
    def _coerce_palettes(value: Any) -> list[dict]:
        if not isinstance(value, list):
            return []
        return [entry for entry in value if isinstance(entry, dict)]
