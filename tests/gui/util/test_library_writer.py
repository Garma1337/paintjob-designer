# coding: utf-8

from dataclasses import dataclass
from pathlib import Path

import pytest

from paintjob_designer.gui.util.library_writer import LibraryWriter


@dataclass
class _Item:
    name: str


@pytest.fixture
def writer() -> LibraryWriter:
    return LibraryWriter()


def test_writes_one_file_per_item(writer: LibraryWriter, tmp_path: Path) -> None:
    items = [_Item("a"), _Item("b")]
    written = writer.write(
        tmp_path, items,
        filename_for=lambda i, idx: f"{idx:02d}_{i.name}.json",
        serialize=lambda i: f'{{"name":"{i.name}"}}',
    )

    assert [p.name for p in written] == ["00_a.json", "01_b.json"]
    assert (tmp_path / "00_a.json").read_text(encoding="utf-8") == '{"name":"a"}'
    assert (tmp_path / "01_b.json").read_text(encoding="utf-8") == '{"name":"b"}'


def test_creates_missing_directory(writer: LibraryWriter, tmp_path: Path) -> None:
    target = tmp_path / "fresh" / "dir"
    writer.write(
        target, [_Item("x")],
        filename_for=lambda i, idx: f"{i.name}.json",
        serialize=lambda i: "{}",
    )

    assert target.is_dir()


def test_empty_list_writes_nothing(writer: LibraryWriter, tmp_path: Path) -> None:
    written = writer.write(
        tmp_path, [],
        filename_for=lambda i, idx: "x.json",
        serialize=lambda i: "{}",
    )

    assert written == []
    assert list(tmp_path.iterdir()) == []
