# coding: utf-8

from pathlib import Path

import pytest

from tests.conftest import build_tim, build_vrm_bytes


def _tiny_vrm_bytes() -> bytes:
    return build_vrm_bytes([build_tim(bpp=2, image={
        "origin_x": 0, "origin_y": 0, "width": 1, "height": 1,
        "pixels": b"\x00\x00",
    })])


def _write_shared_vrm(root: Path) -> Path:
    vrm = root / "bigfile/packs/shared.vrm"
    vrm.parent.mkdir(parents=True, exist_ok=True)
    vrm.write_bytes(_tiny_vrm_bytes())
    return vrm


class TestGet:

    def test_reads_shared_vrm_once_per_iso_root(self, vram_cache, tmp_path, monkeypatch):
        _write_shared_vrm(tmp_path)

        calls = 0
        original = vram_cache._reader.read

        def counting_read(data):
            nonlocal calls
            calls += 1
            return original(data)

        monkeypatch.setattr(vram_cache._reader, "read", counting_read)

        vram_cache.get(tmp_path)
        vram_cache.get(tmp_path)
        vram_cache.get(tmp_path)

        assert calls == 1

    def test_changing_iso_root_forces_reload(self, vram_cache, tmp_path, monkeypatch):
        a = tmp_path / "a"
        b = tmp_path / "b"
        _write_shared_vrm(a)
        _write_shared_vrm(b)

        calls = 0
        original = vram_cache._reader.read

        def counting_read(data):
            nonlocal calls
            calls += 1
            return original(data)

        monkeypatch.setattr(vram_cache._reader, "read", counting_read)

        vram_cache.get(a)
        vram_cache.get(b)

        assert calls == 2

    def test_accepts_string_path(self, vram_cache, tmp_path):
        _write_shared_vrm(tmp_path)

        page = vram_cache.get(str(tmp_path))

        assert page.byte_size == 1024 * 512 * 2

    def test_missing_shared_vrm_raises(self, vram_cache, tmp_path):
        with pytest.raises(FileNotFoundError):
            vram_cache.get(tmp_path)


class TestInvalidate:

    def test_invalidate_forces_next_get_to_reread(self, vram_cache, tmp_path, monkeypatch):
        _write_shared_vrm(tmp_path)

        calls = 0
        original = vram_cache._reader.read

        def counting_read(data):
            nonlocal calls
            calls += 1
            return original(data)

        monkeypatch.setattr(vram_cache._reader, "read", counting_read)

        vram_cache.get(tmp_path)
        vram_cache.invalidate()
        vram_cache.get(tmp_path)

        assert calls == 2
