# coding: utf-8

from paintjob_designer.models import Palette, PaletteLibrary, PsxColor


def _colors(values: list[int]) -> list[PsxColor]:
    return [PsxColor(value=v) for v in values]


class TestPaletteDefaults:

    def test_defaults_are_empty(self):
        palette = Palette()

        assert palette.name == ""
        assert palette.colors == []

    def test_name_and_colors_preserved(self):
        palette = Palette(name="Warm", colors=_colors([0x001F, 0x03FF]))

        assert palette.name == "Warm"
        assert [c.value for c in palette.colors] == [0x001F, 0x03FF]


class TestPaletteRoundTrip:

    def test_round_trip_through_model_dump_and_validate(self):
        # The config store persists palettes via `model_dump()` → JSON dict
        # → `model_validate()` on load, so that specific round-trip has to
        # preserve every field including the PSX hex color serialization.
        original = Palette(name="Neon", colors=_colors([0x7FFF, 0x8000, 0x0000]))

        rebuilt = Palette.model_validate(original.model_dump())

        assert rebuilt.name == original.name
        assert [c.value for c in rebuilt.colors] == [c.value for c in original.colors]

    def test_hex_string_color_round_trip(self):
        # PsxColor serializes as a hex string like "#7fff", so the dump
        # puts strings in `colors` — `model_validate` must accept that.
        original = Palette(name="Hex", colors=_colors([0x7FFF]))

        dumped = original.model_dump()

        # Sanity: colors are serialized as hex strings, not int dicts.
        assert isinstance(dumped["colors"][0], str)
        assert dumped["colors"][0].startswith("#")

        rebuilt = Palette.model_validate(dumped)

        assert rebuilt.colors[0].value == 0x7FFF


class TestPaletteLibraryDefaults:

    def test_empty_library(self):
        library = PaletteLibrary()

        assert library.palettes == []

    def test_round_trip_preserves_order(self):
        library = PaletteLibrary(palettes=[
            Palette(name="a", colors=_colors([0x0001])),
            Palette(name="b", colors=_colors([0x0002])),
            Palette(name="c", colors=_colors([0x0003])),
        ])

        rebuilt = PaletteLibrary.model_validate(library.model_dump())

        assert [p.name for p in rebuilt.palettes] == ["a", "b", "c"]
        assert [p.colors[0].value for p in rebuilt.palettes] == [1, 2, 3]
