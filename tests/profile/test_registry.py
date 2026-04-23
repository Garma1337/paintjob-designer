# coding: utf-8

import pytest

from paintjob_designer.models import KartType, Profile

KART_SLOT_NAMES = {"front", "back", "floor", "brown", "motorside", "motortop", "bridge", "exhaust"}
HOVERCRAFT_SLOT_NAMES = {"hoverkart"}


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
        assert profile.schema_version == 2
        assert profile.id == "vanilla-ntsc-u"
        assert profile.vram_page.width == 1024
        assert profile.vram_page.height == 512

    def test_has_sixteen_characters(self, profile):
        # 15 standard racers + Oxide (hoverkart).
        assert len(profile.characters) == 16

    def test_every_character_has_mesh_source(self, profile):
        for c in profile.characters:
            assert c.mesh_source.startswith("bigfile/models/racers/hi/"), c.id
            assert c.mesh_source.endswith(".ctr"), c.id

    def test_every_kart_character_has_all_standard_kart_slots(self, profile):
        # Kart-type characters must carry exactly the 8 canonical kart slots
        # in `kart_slots` — that's what makes a paintjob portable across
        # them. Skin-only extras live in `skin_slots` instead.
        for c in profile.characters:
            if c.kart_type != KartType.KART:
                continue

            slot_names = {s.name for s in c.kart_slots}
            assert slot_names == KART_SLOT_NAMES, f"{c.id}: kart_slots = {slot_names}"

    def test_floor_slot_is_marked_non_portable(self, profile):
        # `floor` shares VRAM texels with another character's CLUT, so the
        # editor must block texture import on it. The non-portable flag is
        # how that rule is signaled to the UI.
        for c in profile.characters:
            if c.kart_type != KartType.KART:
                continue

            floor = next(s for s in c.kart_slots if s.name == "floor")
            assert floor.non_portable, f"{c.id}: floor slot not marked non_portable"

    def test_oxide_is_hovercraft_with_single_kart_slot(self, profile):
        oxide = next(c for c in profile.characters if c.id == "oxide")

        assert oxide.kart_type == KartType.HOVERCRAFT
        assert {s.name for s in oxide.kart_slots} == HOVERCRAFT_SLOT_NAMES

        hoverkart = oxide.kart_slots[0]
        assert (hoverkart.clut.x, hoverkart.clut.y) == (288, 248)

    def test_oxide_skin_slots_cover_remaining_character_cluts(self, profile):
        # Oxide's whole character is texture-mapped (driver is not Gouraud-
        # colored like standard racers), so the 14 non-hoverkart CLUTs in
        # his mesh land in skin_slots and become skin-editable.
        oxide = next(c for c in profile.characters if c.id == "oxide")

        assert len(oxide.skin_slots) == 14

    def test_crash_front_slot_matches_saphi_coord(self, profile):
        crash = next(c for c in profile.characters if c.id == "crash")
        front = next(s for s in crash.kart_slots if s.name == "front")

        assert (front.clut.x, front.clut.y) == (112, 255)

    def test_papu_floor_resolves_to_shared_crash_coord(self, profile):
        # Saphi's PAINTP_R has `papu.floor = &floor_crash_pos`, meaning papu reuses
        # crash's floor CLUT in VRAM. The profile should reflect that aliasing.
        papu = next(c for c in profile.characters if c.id == "papu")
        floor = next(s for s in papu.kart_slots if s.name == "floor")

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

    def test_skin_slot_names_use_extra_prefix_on_kart_characters(self, profile):
        # On standard kart racers, skin slots are the per-character-unique
        # CLUTs we appended as `extra_<x>_<y>` placeholders. Pinning the
        # naming convention so a future migration that bypasses the prefix
        # gets caught.
        for c in profile.characters:
            if c.kart_type != KartType.KART:
                continue

            for slot in c.skin_slots:
                assert slot.name.startswith("extra_"), f"{c.id}: {slot.name!r}"
