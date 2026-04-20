# coding: utf-8

import pytest

from paintjob_designer.models import Paintjob, PaintjobLibrary
from tests.conftest import slot_of


class TestLoadSaveRoundTrip:

    def test_save_then_load_preserves_fields(self, project_handler, tmp_path):
        original = Paintjob(
            name="Lime",
            author="Garma",
            base_character_id="crash",
            slots={"front": slot_of(value=0x03EB)},
        )
        path = tmp_path / "lime.json"

        project_handler.save(path, original)
        loaded = project_handler.load(path)

        assert loaded.name == "Lime"
        assert loaded.author == "Garma"
        assert loaded.base_character_id == "crash"
        assert loaded.slots["front"].colors[0].value == 0x03EB

    def test_save_creates_parent_directory(self, project_handler, tmp_path):
        deep = tmp_path / "a" / "b" / "c" / "mine.json"

        project_handler.save(deep, Paintjob())

        assert deep.exists()


class TestLibraryRoundTrip:

    def _filename(self, paintjob: Paintjob, index: int) -> str:
        base = paintjob.base_character_id or "paintjob"
        return f"{index:02d}_{base}.json"

    def test_save_library_writes_one_file_per_paintjob(
        self, project_handler, tmp_path,
    ):
        library = PaintjobLibrary()
        library.add(Paintjob(name="a", base_character_id="crash"))
        library.add(Paintjob(name="b", base_character_id="cortex"))

        written = project_handler.save_library(
            tmp_path, library, self._filename,
        )

        assert len(written) == 2
        assert (tmp_path / "00_crash.json").exists()
        assert (tmp_path / "01_cortex.json").exists()

    def test_save_library_creates_missing_directory(
        self, project_handler, tmp_path,
    ):
        library = PaintjobLibrary()
        library.add(Paintjob(name="x", base_character_id="crash"))
        target = tmp_path / "a" / "b" / "lib"

        project_handler.save_library(target, library, self._filename)

        assert (target / "00_crash.json").exists()

    def test_load_library_preserves_sorted_filename_order(
        self, project_handler, tmp_path,
    ):
        library = PaintjobLibrary()
        library.add(Paintjob(name="first", base_character_id="crash"))
        library.add(Paintjob(name="second", base_character_id="cortex"))
        library.add(Paintjob(name="third", base_character_id="tiny"))
        project_handler.save_library(tmp_path, library, self._filename)

        loaded = project_handler.load_library(tmp_path)

        assert [pj.name for pj in loaded.paintjobs] == ["first", "second", "third"]

    def test_load_library_ignores_non_json_files(
        self, project_handler, tmp_path,
    ):
        (tmp_path / "00_crash.json").write_text('{"schema_version":1,"slots":{}}')
        (tmp_path / "notes.txt").write_text("this isn't a paintjob")
        (tmp_path / "stray.bin").write_bytes(b"\x00\x01\x02")

        loaded = project_handler.load_library(tmp_path)

        assert loaded.count() == 1

    def test_load_library_raises_with_filename_on_parse_error(
        self, project_handler, tmp_path,
    ):
        (tmp_path / "00_good.json").write_text('{"schema_version":1,"slots":{}}')
        (tmp_path / "01_broken.json").write_text('{"not_json')

        with pytest.raises(ValueError, match="01_broken.json"):
            project_handler.load_library(tmp_path)

    def test_empty_directory_returns_empty_library(
        self, project_handler, tmp_path,
    ):
        loaded = project_handler.load_library(tmp_path)

        assert loaded.count() == 0

    def test_round_trip_preserves_metadata(
        self, project_handler, tmp_path,
    ):
        library = PaintjobLibrary()
        library.add(Paintjob(
            name="Crash Classic",
            author="Garma",
            base_character_id="crash",
            slots={"front": slot_of(value=0x03EB)},
        ))

        project_handler.save_library(tmp_path, library, self._filename)
        loaded = project_handler.load_library(tmp_path)

        assert loaded.count() == 1
        pj = loaded.paintjobs[0]
        assert pj.name == "Crash Classic"
        assert pj.author == "Garma"
        assert pj.base_character_id == "crash"
        assert pj.slots["front"].colors[0].value == 0x03EB
