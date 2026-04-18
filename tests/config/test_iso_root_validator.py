# coding: utf-8

from pathlib import Path


def _make_iso(root: Path, files: list[str]) -> Path:
    """Create the given files under `root` so the validator can probe them."""
    for rel in files:
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"")

    return root


class TestValidate:

    def test_empty_path_is_invalid(self, iso_root_validator):
        result = iso_root_validator.validate("")

        assert result.ok is False
        assert "bigfile/models/racers/hi/crash.ctr" in result.missing
        assert "bigfile/packs/shared.vrm" in result.missing

    def test_nonexistent_path_is_invalid(self, iso_root_validator, tmp_path):
        result = iso_root_validator.validate(tmp_path / "does-not-exist")

        assert result.ok is False
        assert len(result.missing) == 2

    def test_directory_with_all_required_files_is_valid(self, iso_root_validator, tmp_path):
        _make_iso(tmp_path, [
            "bigfile/models/racers/hi/crash.ctr",
            "bigfile/packs/shared.vrm",
        ])

        result = iso_root_validator.validate(tmp_path)

        assert result.ok is True
        assert result.missing == []

    def test_partially_populated_directory_lists_missing_files(
        self, iso_root_validator, tmp_path,
    ):
        _make_iso(tmp_path, ["bigfile/models/racers/hi/crash.ctr"])

        result = iso_root_validator.validate(tmp_path)

        assert result.ok is False
        assert result.missing == ["bigfile/packs/shared.vrm"]

    def test_accepts_string_path(self, iso_root_validator, tmp_path):
        _make_iso(tmp_path, [
            "bigfile/models/racers/hi/crash.ctr",
            "bigfile/packs/shared.vrm",
        ])

        result = iso_root_validator.validate(str(tmp_path))

        assert result.ok is True
