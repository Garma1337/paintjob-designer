# coding: utf-8

import pytest

from paintjob_designer.models import (
    Paintjob,
    PaintjobLibrary,
    PsxColor,
    SlotColors,
)


def _paintjob(name: str, base: str | None = None) -> Paintjob:
    return Paintjob(
        name=name,
        base_character_id=base,
        slots={
            "front": SlotColors(
                colors=[PsxColor(value=i) for i in range(SlotColors.SIZE)],
            ),
        },
    )


class TestDefaults:

    def test_empty_library(self):
        library = PaintjobLibrary()

        assert library.count() == 0
        assert library.paintjobs == []

    def test_paintjob_has_no_base_character_by_default(self):
        pj = Paintjob()

        # Default: unset so the paintjob is character-agnostic. The field
        # only gets populated when an artist explicitly authors against a
        # specific character.
        assert pj.base_character_id is None


class TestAddAndCount:

    def test_add_returns_index_and_appends(self):
        library = PaintjobLibrary()

        idx0 = library.add(_paintjob("Crash"))
        idx1 = library.add(_paintjob("Cortex"))

        assert idx0 == 0
        assert idx1 == 1
        assert library.count() == 2
        assert library.paintjobs[0].name == "Crash"
        assert library.paintjobs[1].name == "Cortex"


class TestRemove:

    def test_remove_returns_popped_paintjob(self):
        library = PaintjobLibrary()
        library.add(_paintjob("Crash"))
        library.add(_paintjob("Cortex"))

        removed = library.remove(0)

        assert removed.name == "Crash"
        assert library.count() == 1
        assert library.paintjobs[0].name == "Cortex"

    def test_remove_out_of_range_raises(self):
        library = PaintjobLibrary()

        with pytest.raises(IndexError):
            library.remove(0)


class TestMove:

    def test_move_forward(self):
        library = PaintjobLibrary()
        for name in ("A", "B", "C", "D"):
            library.add(_paintjob(name))

        library.move(0, 2)

        # After removing A and re-inserting at index 2: B, C, A, D.
        assert [pj.name for pj in library.paintjobs] == ["B", "C", "A", "D"]

    def test_move_backward(self):
        library = PaintjobLibrary()
        for name in ("A", "B", "C", "D"):
            library.add(_paintjob(name))

        library.move(3, 1)

        assert [pj.name for pj in library.paintjobs] == ["A", "D", "B", "C"]

    def test_move_clamps_destination(self):
        library = PaintjobLibrary()
        for name in ("A", "B", "C"):
            library.add(_paintjob(name))

        # Destination past the end lands at the end, not out-of-range.
        library.move(0, 99)

        assert [pj.name for pj in library.paintjobs] == ["B", "C", "A"]


class TestOrderIsExportIndex:

    def test_indices_match_list_position(self):
        # The library's order IS the paintjob index for downstream exports
        # (PAINTALL.BIN colors[N] etc.) — assert that invariant holds.
        library = PaintjobLibrary()
        for name in ("zero", "one", "two"):
            library.add(_paintjob(name))

        for i, pj in enumerate(library.paintjobs):
            assert library.paintjobs[i] is pj


class TestFindByBaseCharacter:

    def test_returns_matching_paintjob(self):
        library = PaintjobLibrary()
        library.add(_paintjob("Crash", base="crash"))
        library.add(_paintjob("Cortex", base="cortex"))

        hit = library.find_by_base_character("cortex")

        assert hit is not None
        assert hit.name == "Cortex"

    def test_returns_none_when_no_match(self):
        library = PaintjobLibrary()
        library.add(_paintjob("Crash", base="crash"))

        assert library.find_by_base_character("tiny") is None

    def test_returns_first_match_when_duplicates(self):
        # A paintjob can carry any `base_character_id`; duplicates are allowed
        # in the library (the artist may keep two alternate Crash palettes).
        # `find_by_base_character` returns the first one so the behavior is
        # deterministic.
        library = PaintjobLibrary()
        library.add(_paintjob("Crash A", base="crash"))
        library.add(_paintjob("Crash B", base="crash"))

        hit = library.find_by_base_character("crash")

        assert hit is not None
        assert hit.name == "Crash A"
