# coding: utf-8

from paintjob_designer.gui.widget.filters.library_filter import LibraryFilter


class TestLibraryFilter:

    def setup_method(self) -> None:
        self._filter = LibraryFilter()

    def test_empty_query_matches_anything(self) -> None:
        assert self._filter.matches("", "Crash") is True
        assert self._filter.matches("   ", "anything") is True

    def test_substring_match_is_case_insensitive(self) -> None:
        assert self._filter.matches("crash", "Racing Crash") is True
        assert self._filter.matches("CRASH", "racing crash") is True

    def test_query_must_appear_in_at_least_one_field(self) -> None:
        assert self._filter.matches("garma", "Racing", "Garma") is True
        assert self._filter.matches("garma", "Racing", "Anonymous") is False

    def test_fields_are_joined_so_a_query_can_span_them(self) -> None:
        # Joining means "Red stripes" (primary) + " " + "Garma" (secondary)
        # gets searched as one string — so "stripes garma" matches.
        assert self._filter.matches("stripes garma", "Red stripes", "Garma") is True

    def test_none_fields_are_treated_as_empty(self) -> None:
        assert self._filter.matches("crash", None, "Crash Bandicoot") is True
        assert self._filter.matches("missing", None, None) is False
