# coding: utf-8

from pathlib import Path

from paintjob_designer.models import Paintjob, SinglePaintjob, SlotColors

# The canonical 8-slot order used in CTR kart paintjob .c files.
# We always export slots in this order, even if the source
# paintjob only populates a subset — missing slots are skipped but the
# aggregator still uses named field designators.
_CANONICAL_SLOT_ORDER = (
    "front", "back", "floor", "brown",
    "motorside", "motortop", "bridge", "exhaust",
)

# Filename the exported `.c` files include; we write this header alongside
# every export so each paintjob is self-contained — drop the two files into
# any build that accepts the PSX-GCC section attributes and it compiles
# without reaching for a mod-specific header.
_HEADER_FILENAME = "paintjob.h"

# The header's contents live as a plain `.h` file under `templates/` instead
# of a big triple-quoted string — that way the canonical copy matches exactly
# what gets written next to the generated `.c` (line endings, trailing
# newline, everything), and editors give us C syntax highlighting while
# tweaking it.
_HEADER_TEMPLATE_PATH = Path(__file__).parent / "templates" / _HEADER_FILENAME


class SourceCodeExporter:
    """Writes CTR kart paintjobs as C source files.

    Call `export_single` for a standalone paintjob (one `.c` file) or
    `export_set` for a multi-character project (one `.c` per character in an
    output directory).
    """

    def export_single(
        self,
        paintjob: SinglePaintjob,
        dest: Path,
        identifier: str,
        paint_index: int,
    ) -> None:
        """Write one `.c` file for a standalone paintjob, plus `paintjob.h`
        alongside it so the export is plug-and-play.

        `identifier` becomes the per-slot variable-name suffix (e.g. `"lime"`
        produces `front_lime`, `back_lime`, ...). `paint_index` is the 1-based
        `PAINT<N>` aggregator slot.
        """
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(
            self._render(paintjob.slots, identifier, paint_index, paintjob.name),
            encoding="utf-8",
        )
        self._write_header(dest.parent)

    def export_set(
        self,
        paintjob: Paintjob,
        dest_dir: Path,
        paint_index_by_character: dict[str, int],
        identifier_by_character: dict[str, str] | None = None,
    ) -> None:
        """Write one `.c` per character in `dest_dir`, plus a shared `paintjob.h`.

        `paint_index_by_character` decides each character's `PAINT<N>` slot —
        callers typically map this from the vanilla CTR paintjob order
        (crash=1, cortex=2, ...). `identifier_by_character` lets callers
        override the variable-name suffix per character; missing entries fall
        back to the character id.
        """
        dest_dir.mkdir(parents=True, exist_ok=True)
        identifier_by_character = identifier_by_character or {}

        for character_id, character_paintjob in paintjob.characters.items():
            identifier = identifier_by_character.get(character_id, character_id)
            paint_index = paint_index_by_character.get(character_id, 1)
            out = dest_dir / f"{identifier}.c"
            out.write_text(
                self._render(
                    character_paintjob.slots, identifier, paint_index, "",
                ),
                encoding="utf-8",
            )

        self._write_header(dest_dir)

    def _write_header(self, directory: Path) -> None:
        """Write `paintjob.h` into `directory`, overwriting any existing copy.

        Always writing it keeps exports self-contained — callers can drop a
        freshly-exported `.c`/`.h` pair into any build without hunting down a
        mod-specific header. The template is read on every call rather than
        cached since the file is ~500 bytes and exports are user-triggered.
        """
        content = _HEADER_TEMPLATE_PATH.read_text(encoding="utf-8")
        (directory / _HEADER_FILENAME).write_text(content, encoding="utf-8")

    def _render(
        self,
        slots: dict[str, SlotColors],
        identifier: str,
        paint_index: int,
        source_name: str,
    ) -> str:
        if not identifier:
            raise ValueError("identifier must be a non-empty string")

        if paint_index < 1:
            raise ValueError(f"paint_index must be >= 1, got {paint_index}")

        lines: list[str] = [f'#include "{_HEADER_FILENAME}"', ""]

        if source_name:
            lines.append(f"// Exported from paintjob: {source_name}")
            lines.append("")

        for slot_name in _CANONICAL_SLOT_ORDER:
            if slot_name not in slots:
                continue

            lines.append(self._render_slot_array(slot_name, identifier, slots[slot_name]))
            lines.append("")

        lines.append(self._render_aggregator(slots, identifier, paint_index))
        return "\n".join(lines) + "\n"

    def _render_slot_array(
        self, slot_name: str, identifier: str, slot: SlotColors,
    ) -> str:
        values = ",".join(f"0x{c.value:x}" for c in slot.colors)
        return (
            f"short {slot_name}_{identifier}[16] "
            f"__attribute__ ((section (\".data\"))) = {{\n"
            f"{values},}};"
        )

    def _render_aggregator(
        self, slots: dict[str, SlotColors], identifier: str, paint_index: int,
    ) -> str:
        field_lines = []
        for slot_name in _CANONICAL_SLOT_ORDER:
            if slot_name not in slots:
                continue

            field_lines.append(
                f"\t\t.{slot_name} = (char*){slot_name}_{identifier},"
            )

        fields_block = "\n".join(field_lines)

        return (
            f"Texture PAINT{paint_index}[] "
            f"__attribute__ ((section (\".sdata\"))) = {{\n"
            f"\t[0] =\n"
            f"\t{{\n"
            f"{fields_block}\n"
            f"\t}},\n"
            f"}};"
        )
