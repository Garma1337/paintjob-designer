# coding: utf-8

import pytest

from paintjob_designer.models import Profile

EXPECTED_SLOTS = {"front", "back", "floor", "brown", "motorside", "motortop", "bridge", "exhaust"}


class TestAvailableProfiles:

    def test_vanilla_ntsc_u_is_bundled(self, profile_registry):
        assert "vanilla-ntsc-u" in profile_registry.available()

    def test_unknown_profile_raises(self, profile_registry):
        with pytest.raises(FileNotFoundError):
            profile_registry.load("does-not-exist")


class TestVanillaNtscUProfile:

    @pytest.fixture
    def profile(self, profile_registry) -> Profile:
        return profile_registry.load("vanilla-ntsc-u")

    def test_profile_metadata(self, profile):
        assert profile.schema_version == 1
        assert profile.id == "vanilla-ntsc-u"
        assert profile.vram_page.width == 1024
        assert profile.vram_page.height == 512

    def test_has_fifteen_characters(self, profile):
        assert len(profile.characters) == 15

    def test_every_character_has_mesh_source(self, profile):
        for c in profile.characters:
            assert c.mesh_source.startswith("bigfile/models/racers/hi/"), c.id
            assert c.mesh_source.endswith(".ctr"), c.id

    def test_every_character_has_all_standard_slots(self, profile):
        for c in profile.characters:
            slot_names = {s.name for s in c.slots}
            assert slot_names == EXPECTED_SLOTS, f"{c.id}: {slot_names}"

    def test_crash_front_slot_matches_saphi_coord(self, profile):
        crash = next(c for c in profile.characters if c.id == "crash")
        front = next(s for s in crash.slots if s.name == "front")

        assert (front.clut.x, front.clut.y) == (112, 255)

    def test_papu_floor_resolves_to_shared_crash_coord(self, profile):
        # Saphi's PAINTP_R has `papu.floor = &floor_crash_pos`, meaning papu reuses
        # crash's floor CLUT in VRAM. The profile should reflect that aliasing.
        papu = next(c for c in profile.characters if c.id == "papu")
        floor = next(s for s in papu.slots if s.name == "floor")

        assert (floor.clut.x, floor.clut.y) == (304, 252)

    def test_tropy_uses_ntropy_mesh(self, profile):
        # `tropy` (N. Tropy) is the tool's id; on disk the model is `ntropy.ctr`.
        tropy = next(c for c in profile.characters if c.id == "tropy")

        assert tropy.mesh_source == "bigfile/models/racers/hi/ntropy.ctr"

    def test_all_clut_coords_are_within_vram(self, profile):
        for c in profile.characters:
            for slot in c.slots:
                assert 0 <= slot.clut.x < profile.vram_page.width, (c.id, slot.name)
                assert 0 <= slot.clut.y < profile.vram_page.height, (c.id, slot.name)
