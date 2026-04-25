# coding: utf-8

import pytest

from paintjob_designer.models import VramPage
from paintjob_designer.profile.menu_clut_locator import MenuClutLocator


def _empty_vram() -> VramPage:
    return VramPage()


def _write_clut(vram: VramPage, x: int, y: int, values: list[int]) -> None:
    """Write a list of u16 PSX values starting at (x, y)."""
    for i, v in enumerate(values):
        offset = (y * vram.WIDTH + (x + i)) * vram.BYTES_PER_PIXEL
        vram.data[offset] = v & 0xFF
        vram.data[offset + 1] = (v >> 8) & 0xFF


def _signature_a() -> list[int]:
    # 16 distinct PSX u16 values — high entropy, unique signature.
    return [0x7C00 | (i << 5) for i in range(16)]


class TestReadSignature:

    def setup_method(self) -> None:
        self._locator = MenuClutLocator()

    def test_reads_16_consecutive_u16s(self) -> None:
        vram = _empty_vram()
        _write_clut(vram, 100, 200, _signature_a())

        sig = self._locator.read_signature(vram, 100, 200)

        assert sig == _signature_a()


class TestFindDuplicates:

    def setup_method(self) -> None:
        self._locator = MenuClutLocator()

    def test_finds_a_single_duplicate_at_a_different_coord(self) -> None:
        vram = _empty_vram()
        _write_clut(vram, 100, 200, _signature_a())
        _write_clut(vram, 50, 400, _signature_a())  # the duplicate

        matches = self._locator.find_duplicates(vram, 100, 200)

        assert matches == [(50, 400)]

    def test_excludes_the_source_position(self) -> None:
        vram = _empty_vram()
        _write_clut(vram, 100, 200, _signature_a())

        matches = self._locator.find_duplicates(vram, 100, 200)

        # Source matches itself but is filtered out → no other matches in empty VRAM.
        assert matches == []

    def test_returns_multiple_when_multiple_duplicates_exist(self) -> None:
        vram = _empty_vram()
        _write_clut(vram, 100, 200, _signature_a())
        _write_clut(vram, 50, 400, _signature_a())
        _write_clut(vram, 200, 100, _signature_a())

        matches = self._locator.find_duplicates(vram, 100, 200)

        assert set(matches) == {(50, 400), (200, 100)}

    def test_excluded_positions_are_filtered(self) -> None:
        vram = _empty_vram()
        _write_clut(vram, 100, 200, _signature_a())
        _write_clut(vram, 50, 400, _signature_a())

        matches = self._locator.find_duplicates(
            vram, 100, 200, excluded={(50, 400)},
        )

        assert matches == []

    def test_skips_matches_that_would_overrun_the_row_edge(self) -> None:
        vram = _empty_vram()
        sig = _signature_a()
        _write_clut(vram, 100, 200, sig)

        # Plant the first u16 of the signature near the row edge — a match
        # would need columns 1010..1025, which doesn't fit in 1024 columns.
        offset = (300 * vram.WIDTH + 1010) * vram.BYTES_PER_PIXEL
        vram.data[offset] = sig[0] & 0xFF
        vram.data[offset + 1] = (sig[0] >> 8) & 0xFF

        matches = self._locator.find_duplicates(vram, 100, 200)

        # The dangling first u16 alone shouldn't count as a match.
        assert matches == []

    def test_returns_empty_when_no_duplicates_exist(self) -> None:
        vram = _empty_vram()
        _write_clut(vram, 100, 200, _signature_a())

        matches = self._locator.find_duplicates(vram, 100, 200)

        assert matches == []


class TestFindMatches:

    def setup_method(self) -> None:
        self._locator = MenuClutLocator()

    def test_rejects_signature_of_wrong_length(self) -> None:
        vram = _empty_vram()

        with pytest.raises(ValueError, match="must be 16"):
            self._locator.find_matches(vram, [0xFFFF] * 15, excluded=set())


class TestSignatureEntropy:

    def setup_method(self) -> None:
        self._locator = MenuClutLocator()

    def test_returns_count_of_distinct_values(self) -> None:
        assert self._locator.signature_entropy([0xAAAA] * 16) == 1
        assert self._locator.signature_entropy(_signature_a()) == 16
        assert self._locator.signature_entropy([1, 1, 2, 2, 3, 3] + [0] * 10) == 4
