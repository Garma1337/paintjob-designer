# coding: utf-8

import pytest

from paintjob_designer.models import Skin, SkinLibrary


def _skin(name: str, character_id: str = "crash") -> Skin:
    return Skin(name=name, character_id=character_id)


class TestSkinLibrary:

    def test_count_starts_at_zero(self):
        assert SkinLibrary().count() == 0

    def test_add_returns_index_and_appends(self):
        lib = SkinLibrary()

        assert lib.add(_skin("a")) == 0
        assert lib.add(_skin("b")) == 1
        assert [s.name for s in lib.skins] == ["a", "b"]

    def test_remove_pops_and_returns(self):
        lib = SkinLibrary()
        a, b = _skin("a"), _skin("b")
        lib.add(a)
        lib.add(b)

        removed = lib.remove(0)

        assert removed is a
        assert [s.name for s in lib.skins] == ["b"]

    def test_remove_out_of_range_raises(self):
        with pytest.raises(IndexError):
            SkinLibrary().remove(0)

    def test_move_reorders(self):
        lib = SkinLibrary()
        for n in ("a", "b", "c", "d"):
            lib.add(_skin(n))

        lib.move(0, 2)

        assert [s.name for s in lib.skins] == ["b", "c", "a", "d"]

    def test_for_character_filters(self):
        lib = SkinLibrary()
        lib.add(_skin("crash variant 1", "crash"))
        lib.add(_skin("cortex variant 1", "cortex"))
        lib.add(_skin("crash variant 2", "crash"))

        crash_skins = lib.for_character("crash")

        assert [s.name for s in crash_skins] == ["crash variant 1", "crash variant 2"]

    def test_for_character_returns_empty_when_no_match(self):
        lib = SkinLibrary()
        lib.add(_skin("crash skin", "crash"))

        assert lib.for_character("oxide") == []
