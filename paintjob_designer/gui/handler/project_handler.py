# coding: utf-8

from pathlib import Path

from paintjob_designer.models import (
    Paintjob,
    PaintjobLibrary,
    PsxColor,
    SlotColors,
)
from paintjob_designer.paintjob.reader import PaintjobReader
from paintjob_designer.paintjob.writer import PaintjobWriter


class ProjectHandler:
    """Paintjob file I/O.

    Reads/writes paintjob JSON — one file = one `Paintjob` — plus
    directory-level "library" operations that treat a folder of JSONs
    as a whole `PaintjobLibrary`. Stateless; the caller owns any path /
    dirty tracking.
    """

    _LIBRARY_GLOB = "*.json"

    def __init__(
        self,
        paintjob_reader: PaintjobReader,
        paintjob_writer: PaintjobWriter,
    ) -> None:
        self._reader = paintjob_reader
        self._writer = paintjob_writer

    def load(self, path: Path) -> Paintjob:
        return self._reader.read(path.read_bytes())

    def save(self, path: Path, paintjob: Paintjob) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self._writer.serialize(paintjob), encoding="utf-8")

    def load_library(self, directory: Path) -> PaintjobLibrary:
        """Load every `*.json` under `directory` as a `PaintjobLibrary`.

        Files are loaded in sorted-filename order so a `NN_name.json`
        convention preserves the library index → in-game paintjob index
        mapping. Non-JSON files are ignored; a JSON file that fails to
        parse stops the load and propagates the `ValueError` with its
        path attached so the user can fix the offending file without
        guessing which one.
        """
        library = PaintjobLibrary()
        for path in sorted(directory.glob(self._LIBRARY_GLOB)):
            try:
                library.add(self.load(path))
            except ValueError as exc:
                raise ValueError(f"{path.name}: {exc}") from exc

        return library

    def save_library(
        self,
        directory: Path,
        library: PaintjobLibrary,
        filename_for: "callable",
    ) -> list[Path]:
        """Write each paintjob in `library` as a JSON file in `directory`.

        `filename_for(paintjob, index) -> str` picks each file's basename
        so callers can enforce whatever convention they want (the main
        window prefixes `NN_` for sortability). Returns the list of
        written paths in library order.
        """
        directory.mkdir(parents=True, exist_ok=True)

        written: list[Path] = []
        for i, paintjob in enumerate(library.paintjobs):
            path = directory / filename_for(paintjob, i)
            self.save(path, paintjob)
            written.append(path)

        return written

    def with_backfilled_defaults(
        self,
        paintjob: Paintjob,
        defaults_by_slot: dict[str, list[PsxColor]],
    ) -> Paintjob:
        """Return a copy of `paintjob` with every slot in `defaults_by_slot`
        populated — edited slots win, the rest fall back to VRAM defaults.

        Used at export time so a saved file carries every slot the profile
        knows about, not just the ones the user touched. Slots already in
        the paintjob but missing from the defaults set (e.g. if the profile
        drifted) are preserved rather than silently dropped.
        """
        slots: dict[str, SlotColors] = {
            name: SlotColors(colors=list(colors))
            for name, colors in defaults_by_slot.items()
        }

        for name, slot in paintjob.slots.items():
            slots[name] = slot

        return Paintjob(
            schema_version=paintjob.schema_version,
            name=paintjob.name,
            author=paintjob.author,
            base_character_id=paintjob.base_character_id,
            slots=slots,
        )
