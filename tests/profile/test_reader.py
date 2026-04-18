# coding: utf-8

import json

import pytest


def _profile_json(**overrides) -> str:
    doc = {
        "schema_version": 1,
        "id": "saphi",
        "display_name": "Saphi TrackROM",
        "vram_page": {"width": 1024, "height": 512},
        "characters": [
            {
                "id": "crash",
                "display_name": "Crash Bandicoot",
                "mesh_source": "bigfile/models/racers/hi/crash.ctr",
                "slots": [
                    {"name": "front", "clut": {"x": 112, "y": 255}},
                    {"name": "back", "clut": {"x": 112, "y": 250}},
                ],
            }
        ],
    }
    doc.update(overrides)
    return json.dumps(doc)


class TestProfileReader:

    def test_reads_full_profile(self, profile_reader):
        profile = profile_reader.read(_profile_json())

        assert profile.schema_version == 1
        assert profile.id == "saphi"
        assert profile.display_name == "Saphi TrackROM"
        assert profile.vram_page.width == 1024
        assert profile.vram_page.height == 512
        assert len(profile.characters) == 1

    def test_parses_character(self, profile_reader):
        profile = profile_reader.read(_profile_json())

        character = profile.characters[0]
        assert character.id == "crash"
        assert character.display_name == "Crash Bandicoot"
        assert character.mesh_source == "bigfile/models/racers/hi/crash.ctr"
        assert len(character.slots) == 2

    def test_parses_slots_with_clut_coords(self, profile_reader):
        profile = profile_reader.read(_profile_json())

        front = profile.characters[0].slots[0]
        assert front.name == "front"
        assert front.clut.x == 112
        assert front.clut.y == 255

    def test_accepts_bytes_input(self, profile_reader):
        profile = profile_reader.read(_profile_json().encode("utf-8"))

        assert profile.id == "saphi"

    def test_rejects_non_object_root(self, profile_reader):
        with pytest.raises(ValueError, match="root must be a JSON object"):
            profile_reader.read("[]")

    def test_rejects_future_schema(self, profile_reader):
        with pytest.raises(ValueError, match="schema_version"):
            profile_reader.read(_profile_json(schema_version=999))

    def test_defaults_vram_page_when_missing(self, profile_reader):
        doc = json.dumps({"schema_version": 1, "id": "minimal"})

        profile = profile_reader.read(doc)

        assert profile.vram_page.width == 1024
        assert profile.vram_page.height == 512

    def test_empty_character_list_when_missing(self, profile_reader):
        doc = json.dumps({"schema_version": 1, "id": "minimal"})

        profile = profile_reader.read(doc)

        assert profile.characters == []
