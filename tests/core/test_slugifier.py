# coding: utf-8

import pytest

from paintjob_designer.core import Slugifier


@pytest.fixture
def slugifier():
    return Slugifier()


class TestSlugify:

    def test_plain_ascii_is_lowercased(self, slugifier):
        assert slugifier.slugify("Crash") == "crash"

    def test_spaces_become_underscores(self, slugifier):
        assert slugifier.slugify("Crash Classic") == "crash_classic"

    def test_mixed_case_with_spaces(self, slugifier):
        assert slugifier.slugify("Saphi TrackROM") == "saphi_trackrom"

    def test_keeps_hyphens_and_underscores(self, slugifier):
        assert slugifier.slugify("foo-bar_baz") == "foo-bar_baz"

    def test_strips_unsupported_punctuation(self, slugifier):
        # Parentheses, exclamation, question marks, slashes — all dropped
        # (not replaced with underscore). Only spaces become underscores.
        assert slugifier.slugify("Crash! (best)") == "crash_best"
        assert slugifier.slugify("a/b?c") == "abc"

    def test_keeps_digits(self, slugifier):
        assert slugifier.slugify("Paint Job 42") == "paint_job_42"

    def test_trims_surrounding_whitespace(self, slugifier):
        assert slugifier.slugify("   padded   ") == "padded"

    def test_empty_input_returns_empty(self, slugifier):
        # Callers rely on this so `slug or fallback` works.
        assert slugifier.slugify("") == ""

    def test_whitespace_only_returns_empty(self, slugifier):
        assert slugifier.slugify("   ") == ""

    def test_all_unsupported_returns_empty(self, slugifier):
        # Nothing survives the filter — empty, not the original string.
        assert slugifier.slugify("!@#$%^&*()") == ""
