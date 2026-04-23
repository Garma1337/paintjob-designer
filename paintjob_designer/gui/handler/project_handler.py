# coding: utf-8

from pathlib import Path

from paintjob_designer.models import (
    Paintjob,
    PaintjobLibrary,
)
from paintjob_designer.paintjob.reader import PaintjobReader
from paintjob_designer.paintjob.writer import PaintjobWriter


class ProjectHandler:
    """Paintjob file I/O."""

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
        """Load every `*.json` under `directory` as a `PaintjobLibrary`."""
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
        """Write each paintjob in `library` as a JSON file in `directory`."""
        directory.mkdir(parents=True, exist_ok=True)

        written: list[Path] = []
        for i, paintjob in enumerate(library.paintjobs):
            path = directory / filename_for(paintjob, i)
            self.save(path, paintjob)
            written.append(path)

        return written

