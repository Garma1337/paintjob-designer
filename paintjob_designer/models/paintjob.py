# coding: utf-8

from dataclasses import dataclass, field

from paintjob_designer.models.color import PsxColor


@dataclass
class SlotColors:
    """The 16 colors of one CLUT slot."""
    SIZE = 16

    colors: list[PsxColor] = field(default_factory=list)


@dataclass
class Paintjob:
    """A single, character-agnostic paintjob: just 8 slots × 16 colors.

    Any character can wear any paintjob — the binding between paintjob and
    character lives in the profile (PAINTALL.BIN's `colors[]` index per
    character) rather than on the paintjob itself. That keeps the model
    honest about what a paintjob actually is: a palette, not a costume
    attached to a specific racer.

    `base_character_id` is a non-authoritative hint used in two places:
      - **Preview fallback** — slots the paintjob hasn't explicitly authored
        inherit colors from that character's VRAM so the 3D preview matches
        the character's unpainted look.
      - **Reopen context** — loading a saved paintjob restores the preview
        character the artist had active when they saved.

    Leave `None` for paintjobs that don't have a natural home character.
    """
    SCHEMA_VERSION = 1

    schema_version: int = SCHEMA_VERSION
    name: str = ""
    author: str = ""
    base_character_id: str | None = None
    slots: dict[str, SlotColors] = field(default_factory=dict)


@dataclass
class PaintjobLibrary:
    """Ordered collection of paintjobs the session is working on.

    Order matters: it drives PAINTALL.BIN's `colors[N]` indexing, so the
    position of a paintjob in the library is also its in-game paintjob ID.
    The library is the first-class editor entity — every save, load, and
    export works against it.
    """

    paintjobs: list[Paintjob] = field(default_factory=list)

    def count(self) -> int:
        return len(self.paintjobs)

    def add(self, paintjob: Paintjob) -> int:
        """Append `paintjob` to the library and return its new index."""
        self.paintjobs.append(paintjob)
        return len(self.paintjobs) - 1

    def remove(self, index: int) -> Paintjob:
        """Pop the paintjob at `index` and return it.

        Raises `IndexError` on an out-of-range index — callers should guard
        on `count()` first rather than rely on exception handling for
        normal UI flow.
        """
        return self.paintjobs.pop(index)

    def move(self, from_index: int, to_index: int) -> None:
        """Reorder: move a paintjob to a new position.

        `to_index` is interpreted on the list state AFTER the source has
        been removed — same semantics as drag-and-drop in Qt's list views,
        so the sidebar can forward its indices verbatim.
        """
        pj = self.paintjobs.pop(from_index)
        to_index = max(0, min(to_index, len(self.paintjobs)))
        self.paintjobs.insert(to_index, pj)

    def find_by_base_character(self, character_id: str) -> Paintjob | None:
        """Return the paintjob whose `base_character_id` matches, or None.

        Used while the editor still maps sidebar-selected characters to
        their "home" paintjob; later passes will replace that UX with
        library-centric selection.
        """
        for pj in self.paintjobs:
            if pj.base_character_id == character_id:
                return pj

        return None
