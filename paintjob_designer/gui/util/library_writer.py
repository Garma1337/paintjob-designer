# coding: utf-8

from pathlib import Path
from typing import Callable, TypeVar

T = TypeVar("T")


class LibraryWriter:
    """Writes a list of items as a directory of JSON files."""

    def write(
        self,
        directory: Path,
        items: list[T],
        *,
        filename_for: Callable[[T, int], str],
        serialize: Callable[[T], str],
    ) -> list[Path]:
        directory.mkdir(parents=True, exist_ok=True)

        written: list[Path] = []
        for i, item in enumerate(items):
            path = directory / filename_for(item, i)
            path.write_text(serialize(item), encoding="utf-8")
            written.append(path)

        return written
