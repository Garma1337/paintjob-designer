# coding: utf-8

from pathlib import Path

from paintjob_designer.models import (
    CharacterPaintjob,
    Paintjob,
    PsxColor,
    SinglePaintjob,
    SlotColors,
)
from paintjob_designer.paintjob.single_reader import SinglePaintjobReader
from paintjob_designer.paintjob.single_writer import SinglePaintjobWriter


class ProjectHandler:
    """Paintjob file I/O.

    Reads/writes paintjob JSON (character-agnostic slot dict) and converts
    between that on-disk form and the in-memory `Paintjob` session state the
    editor mutates. Stateless — the caller owns any path/dirty tracking.
    """

    def __init__(
        self,
        single_paintjob_reader: SinglePaintjobReader,
        single_paintjob_writer: SinglePaintjobWriter,
    ) -> None:
        self._single_reader = single_paintjob_reader
        self._single_writer = single_paintjob_writer

    def open_standalone(self, path: Path) -> SinglePaintjob:
        return self._single_reader.read(path.read_bytes())

    def save_standalone(self, path: Path, paintjob: SinglePaintjob) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            self._single_writer.serialize(paintjob),
            encoding="utf-8",
        )

    def extract_character_as_standalone(
        self,
        project: Paintjob,
        character_id: str,
        defaults_by_slot: dict[str, list[PsxColor]] | None = None,
    ) -> SinglePaintjob:
        """Snapshot one character's slots out of the session as a standalone paintjob.

        When `defaults_by_slot` is given, every slot in that dict is written
        to the output — edited slots win, unedited slots fall back to the
        supplied default CLUT. That's what callers want for "export a
        paintjob" — a self-contained document with every slot, not just the
        ones the user touched.
        """
        character = project.characters.get(character_id)
        edited = dict(character.slots) if character is not None else {}

        if defaults_by_slot is None:
            slots = edited
        else:
            slots = {
                name: edited.get(name, SlotColors(colors=list(colors)))
                for name, colors in defaults_by_slot.items()
            }

            # Preserve any edited slot that isn't in the defaults set (e.g. if
            # the profile's slot list drifted — safer to keep the user's data
            # than silently drop it).
            for name, slot in edited.items():
                slots.setdefault(name, slot)

        return SinglePaintjob(slots=slots)

    def apply_standalone_to_character(
        self,
        project: Paintjob,
        character_id: str,
        standalone: SinglePaintjob,
    ) -> None:
        """Overwrite one character's slots in the session with the standalone's."""
        project.characters[character_id] = CharacterPaintjob(
            slots=dict(standalone.slots),
        )
