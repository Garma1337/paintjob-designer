# coding: utf-8

import pytest

from paintjob_designer.texture.four_bpp_codec import FourBppCodec


class TestFourBppCodec:

    def setup_method(self) -> None:
        self._codec = FourBppCodec()

    def test_pack_two_indices_into_one_byte_low_nibble_first(self) -> None:
        # Index 0 → low nibble, index 1 → high nibble.
        packed = self._codec.pack([0x3, 0xA])

        assert packed == bytes([0xA3])

    def test_pack_round_trips_through_unpack(self) -> None:
        indices = [1, 2, 3, 4, 5, 6, 7, 8]

        packed = self._codec.pack(indices)
        recovered = self._codec.unpack(packed, len(indices))

        assert recovered == indices

    def test_pack_masks_indices_above_15(self) -> None:
        # Higher bits silently dropped — 4bpp only stores the low nibble.
        packed = self._codec.pack([0xFF, 0xF0])

        assert packed == bytes([0x0F])

    def test_pack_rejects_odd_length(self) -> None:
        with pytest.raises(ValueError, match="even pixel count"):
            self._codec.pack([1, 2, 3])

    def test_unpack_returns_exactly_count_indices(self) -> None:
        packed = bytes([0x21, 0x43])

        unpacked = self._codec.unpack(packed, 3)

        assert unpacked == [0x1, 0x2, 0x3]

    def test_unpack_zero_count_returns_empty_list(self) -> None:
        assert self._codec.unpack(bytes([0xAB]), 0) == []

    def test_unpack_negative_count_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            self._codec.unpack(bytes([0x00]), -1)

    def test_unpack_count_larger_than_buffer_raises(self) -> None:
        with pytest.raises(ValueError, match="only holds"):
            self._codec.unpack(bytes([0x00]), 3)
