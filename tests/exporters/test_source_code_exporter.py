# coding: utf-8

import pytest

from paintjob_designer.models import (
    CharacterPaintjob,
    Paintjob,
    SinglePaintjob,
    SlotColors,
)
from tests.conftest import slot_of


def _all_slots(value: int = 0x1234) -> dict[str, SlotColors]:
    names = ("front", "back", "floor", "brown", "motorside", "motortop", "bridge", "exhaust")
    return {n: slot_of(value) for n in names}


class TestEmitSingle:

    def test_writes_one_c_file(self, source_code_exporter, tmp_path):
        paintjob = SinglePaintjob(name="Lime", slots=_all_slots(value=0x03EB))
        out = tmp_path / "lime.c"

        source_code_exporter.export_single(paintjob, out, identifier="lime", paint_index=16)

        assert out.exists()

    def test_includes_local_paintjob_header(self, source_code_exporter, tmp_path):
        paintjob = SinglePaintjob(slots=_all_slots())
        out = tmp_path / "p.c"

        source_code_exporter.export_single(paintjob, out, identifier="foo", paint_index=1)

        text = out.read_text()
        assert '#include "paintjob.h"' in text
        # Old Saphi-specific includes should not appear in a plug-and-play export.
        assert "<common.h>" not in text
        assert "saphi" not in text

    def test_writes_self_contained_paintjob_header_alongside(self, source_code_exporter, tmp_path):
        paintjob = SinglePaintjob(slots=_all_slots())
        out = tmp_path / "p.c"

        source_code_exporter.export_single(paintjob, out, identifier="foo", paint_index=1)

        header = tmp_path / "paintjob.h"
        assert header.exists()
        content = header.read_text()
        assert "#ifndef PAINTJOB_H" in content
        assert "typedef union" in content

        for slot in ("front", "back", "floor", "brown", "motorside", "motortop", "bridge", "exhaust"):
            assert f"const char* {slot}" in content

        assert "const char* p[8]" in content

    def test_creates_parent_directory_for_single_export(self, source_code_exporter, tmp_path):
        paintjob = SinglePaintjob(slots=_all_slots())
        nested = tmp_path / "deeply" / "nested" / "p.c"

        source_code_exporter.export_single(paintjob, nested, identifier="foo", paint_index=1)

        assert nested.exists()
        assert (nested.parent / "paintjob.h").exists()

    def test_slot_arrays_use_identifier_suffix(self, source_code_exporter, tmp_path):
        paintjob = SinglePaintjob(slots={
            "front": slot_of(value=0x1111),
            "back": slot_of(value=0x2222),
        })
        out = tmp_path / "p.c"

        source_code_exporter.export_single(paintjob, out, identifier="test", paint_index=1)

        text = out.read_text()
        assert "short front_test[16]" in text
        assert "short back_test[16]" in text

    def test_color_values_rendered_as_hex(self, source_code_exporter, tmp_path):
        paintjob = SinglePaintjob(slots={"front": slot_of(value=0x7FFF)})
        out = tmp_path / "p.c"

        source_code_exporter.export_single(paintjob, out, identifier="x", paint_index=1)

        text = out.read_text()
        # 16 copies of 0x7fff in the front slot array.
        assert text.count("0x7fff") == 16

    def test_aggregator_uses_paint_index(self, source_code_exporter, tmp_path):
        paintjob = SinglePaintjob(slots=_all_slots())
        out = tmp_path / "p.c"

        source_code_exporter.export_single(paintjob, out, identifier="x", paint_index=16)

        text = out.read_text()
        assert "Texture PAINT16[]" in text
        assert ".sdata" in text

    def test_aggregator_points_at_all_slots(self, source_code_exporter, tmp_path):
        paintjob = SinglePaintjob(slots=_all_slots())
        out = tmp_path / "p.c"

        source_code_exporter.export_single(paintjob, out, identifier="x", paint_index=1)

        text = out.read_text()
        for slot in ("front", "back", "floor", "brown", "motorside", "motortop", "bridge", "exhaust"):
            assert f".{slot} = (char*){slot}_x," in text

    def test_slots_emitted_in_canonical_order(self, source_code_exporter, tmp_path):
        # Even if the source dict was built back-to-front, the output should
        # put `front_*` before `back_*`.
        paintjob = SinglePaintjob(slots={
            "back": slot_of(),
            "front": slot_of(),
        })
        out = tmp_path / "p.c"

        source_code_exporter.export_single(paintjob, out, identifier="x", paint_index=1)

        text = out.read_text()
        assert text.index("front_x") < text.index("back_x")

    def test_rejects_empty_identifier(self, source_code_exporter, tmp_path):
        with pytest.raises(ValueError, match="identifier"):
            source_code_exporter.export_single(
                SinglePaintjob(slots=_all_slots()),
                tmp_path / "p.c",
                identifier="", paint_index=1,
            )

    def test_rejects_zero_paint_index(self, source_code_exporter, tmp_path):
        with pytest.raises(ValueError, match="paint_index"):
            source_code_exporter.export_single(
                SinglePaintjob(slots=_all_slots()),
                tmp_path / "p.c",
                identifier="x", paint_index=0,
            )


class TestEmitSet:

    def test_writes_one_file_per_character(self, source_code_exporter, tmp_path):
        paintjob = Paintjob(characters={
            "crash":  CharacterPaintjob(slots=_all_slots()),
            "cortex": CharacterPaintjob(slots=_all_slots()),
        })
        out_dir = tmp_path / "paintjobs"

        source_code_exporter.export_set(
            paintjob, out_dir,
            paint_index_by_character={"crash": 1, "cortex": 2},
        )

        assert (out_dir / "crash.c").exists()
        assert (out_dir / "cortex.c").exists()

    def test_each_file_uses_its_own_paint_index(self, source_code_exporter, tmp_path):
        paintjob = Paintjob(characters={
            "crash":  CharacterPaintjob(slots=_all_slots()),
            "cortex": CharacterPaintjob(slots=_all_slots()),
        })
        out_dir = tmp_path / "paintjobs"

        source_code_exporter.export_set(
            paintjob, out_dir,
            paint_index_by_character={"crash": 1, "cortex": 2},
        )

        assert "Texture PAINT1[]" in (out_dir / "crash.c").read_text()
        assert "Texture PAINT2[]" in (out_dir / "cortex.c").read_text()

    def test_identifier_override_per_character(self, source_code_exporter, tmp_path):
        paintjob = Paintjob(characters={
            "tropy": CharacterPaintjob(slots=_all_slots()),
        })
        out_dir = tmp_path / "paintjobs"

        # Disk-name convention (e.g. "ntropy.c") can differ from character id.
        source_code_exporter.export_set(
            paintjob, out_dir,
            paint_index_by_character={"tropy": 13},
            identifier_by_character={"tropy": "ntropy"},
        )

        assert (out_dir / "ntropy.c").exists()
        assert "short front_ntropy[16]" in (out_dir / "ntropy.c").read_text()

    def test_writes_shared_paintjob_header_in_output_directory(
        self, source_code_exporter, tmp_path,
    ):
        paintjob = Paintjob(characters={
            "crash":  CharacterPaintjob(slots=_all_slots()),
            "cortex": CharacterPaintjob(slots=_all_slots()),
        })
        out_dir = tmp_path / "paintjobs"

        source_code_exporter.export_set(
            paintjob, out_dir,
            paint_index_by_character={"crash": 1, "cortex": 2},
        )

        # One shared paintjob.h for the whole directory.
        assert (out_dir / "paintjob.h").exists()
