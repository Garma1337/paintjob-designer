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
