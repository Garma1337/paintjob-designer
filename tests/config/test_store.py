# coding: utf-8

import json
from pathlib import Path

import pytest

from paintjob_designer.config.store import AppConfig, ConfigStore


@pytest.fixture
def config_path(tmp_path: Path) -> Path:
    return tmp_path / "config.json"


@pytest.fixture
def config_store(config_path: Path) -> ConfigStore:
    return ConfigStore(config_path)


class TestAppConfig:

    def test_defaults(self):
        cfg = AppConfig()

        assert cfg.iso_root == ""
        assert cfg.last_profile_id == "vanilla-ntsc-u"
        assert cfg.library is None
        assert cfg.palettes == []


class TestLoad:

    def test_missing_file_returns_default_config(self, config_store):
        cfg = config_store.load()

        assert cfg == AppConfig()

    def test_loads_previously_saved_values(self, config_store, config_path):
        config_path.write_text(json.dumps({
            "iso_root": "/iso/root",
            "last_profile_id": "saphi",
        }))

        cfg = config_store.load()

        assert cfg.iso_root == "/iso/root"
        assert cfg.last_profile_id == "saphi"

    def test_non_object_json_falls_back_to_default(self, config_store, config_path):
        config_path.write_text(json.dumps([1, 2, 3]))

        cfg = config_store.load()

        assert cfg == AppConfig()

    def test_missing_fields_fall_back_to_defaults(self, config_store, config_path):
        config_path.write_text(json.dumps({"iso_root": "/iso"}))

        cfg = config_store.load()

        assert cfg.iso_root == "/iso"
        assert cfg.last_profile_id == "vanilla-ntsc-u"
        assert cfg.library is None
        assert cfg.palettes == []

    def test_loads_library_blob(self, config_store, config_path):
        library_blob = {"paintjobs": []}
        config_path.write_text(json.dumps({
            "iso_root": "/iso",
            "last_profile_id": "saphi",
            "library": library_blob,
        }))

        cfg = config_store.load()

        assert cfg.library == library_blob

    def test_non_dict_library_is_coerced_to_none(self, config_store, config_path):
        # A corrupt or unexpected shape (e.g. someone wrote a list) must
        # not crash the load — fall back to "no library yet" so the app
        # still opens.
        config_path.write_text(json.dumps({
            "iso_root": "/iso",
            "library": ["not", "a", "dict"],
        }))

        cfg = config_store.load()

        assert cfg.library is None

    def test_loads_palettes(self, config_store, config_path):
        palettes = [
            {"name": "Warm", "colors": ["#001f"]},
            {"name": "Cool", "colors": ["#7c00"]},
        ]
        config_path.write_text(json.dumps({
            "iso_root": "/iso",
            "palettes": palettes,
        }))

        cfg = config_store.load()

        assert cfg.palettes == palettes

    def test_non_list_palettes_falls_back_to_empty(self, config_store, config_path):
        config_path.write_text(json.dumps({
            "iso_root": "/iso",
            "palettes": "not a list",
        }))

        cfg = config_store.load()

        assert cfg.palettes == []

    def test_non_dict_palette_entries_are_dropped(self, config_store, config_path):
        # Legit `{name, colors}` dicts pass through; anything else (string,
        # null, stray number) is silently filtered so one corrupt entry can't
        # poison the whole palette list.
        config_path.write_text(json.dumps({
            "palettes": [
                {"name": "ok", "colors": []},
                "garbage",
                None,
                42,
                {"name": "also ok", "colors": []},
            ],
        }))

        cfg = config_store.load()

        assert [p["name"] for p in cfg.palettes] == ["ok", "also ok"]


class TestSave:

    def test_creates_parent_directory(self, tmp_path):
        nested = tmp_path / "a" / "b" / "config.json"
        store = ConfigStore(nested)

        store.save(AppConfig(iso_root="/iso"))

        assert nested.exists()

    def test_round_trip_through_save_and_load(self, config_store):
        original = AppConfig(
            iso_root="/iso/root",
            last_profile_id="saphi",
        )

        config_store.save(original)
        loaded = config_store.load()

        assert loaded == original

    def test_save_is_human_readable_json(self, config_store, config_path):
        config_store.save(AppConfig(iso_root="/iso"))

        text = config_path.read_text(encoding="utf-8")
        # Pretty-printed with indentation so users can eyeball/edit it.
        assert "\n" in text
        assert "\"iso_root\": \"/iso\"" in text

    def test_round_trip_with_library_and_palettes(self, config_store):
        # Whole-library autosave round-trips the nested structure exactly,
        # not just the top-level fields — anything less would silently drop
        # paintjob data on restart.
        original = AppConfig(
            iso_root="/iso",
            library={
                "paintjobs": [
                    {
                        "schema_version": 1,
                        "name": "Crash",
                        "author": "",
                        "base_character_id": "crash",
                        "slots": {},
                    },
                ],
            },
            palettes=[{"name": "Warm", "colors": ["#001f"]}],
        )

        config_store.save(original)
        loaded = config_store.load()

        assert loaded == original

    def test_save_omits_library_when_none(self, config_store, config_path):
        # Default `library=None` means "no autosave yet" — don't write a
        # null into the config file; just leave the key out so the JSON
        # stays clean and the semantics stay distinct from an empty
        # library (which would serialize to `{"paintjobs": []}`).
        config_store.save(AppConfig())

        raw = json.loads(config_path.read_text(encoding="utf-8"))
        assert "library" not in raw
