[<- Back](./README.md)

# Skin Library Format

This document describes the on-disk format the designer writes when you "Export Skin Library As…". A *skin* is a character-bound recolor: it edits the CLUTs and gouraud vertex colors that paintjobs don't touch (the driver body, the face, character-specific accessories) and is locked to a single character.

For the parallel paintjob-library format (kart-only, character-portable), see [paintjob_library_format.md](./paintjob_library_format.md).

**Machine-readable schema**: [`schema/skins_library_schema.json`](../schema/skins_library_schema.json). Generated from the pydantic models in `paintjob_designer/models/` and kept in lockstep with them via `tests/skin/test_schema.py`. Consumer tools in other languages can validate against this file using any JSON Schema library; the fields / types / examples it emits are authoritative. If the schema and this human-readable doc ever disagree, the schema wins.

## Directory layout

A saved library is a directory of JSON files, one per skin:

```
MySkinLibrary/
├── 00_warpaint_crash.json
├── 01_evil_cortex.json
├── 02_rainbow_pura.json
├── …
```

- Files are named `NN_<slug>.json` where `NN` is the zero-padded library index and `<slug>` is a filesystem-safe derivation of the skin name (falls back to `character_id`, then `skin_NN`).
- Load order is lexicographic on filename, so the `NN_` prefix deterministically round-trips the library's ordering across save/load cycles.
- Skin index has no in-game significance the way a paintjob index does — skins are character-bound, not table-bound. The prefix exists only for stable filename ordering.

## One skin file

Each `.json` is a single `Skin`:

```json
{
  "schema_version": 1,
  "name": "Warpaint Crash",
  "author": "Garma",
  "character_id": "crash",
  "slots": {
    "face": {
      "colors": ["#0000", "#7fff", "#03eb", "..."],
      "pixels": []
    }
  },
  "vertex_overrides": {
    "5":  {"r": 200, "g": 30,  "b": 30},
    "12": {"r": 220, "g": 220, "b": 100}
  }
}
```

### Top-level fields

| Field              | Type     | Meaning                                                                                                                                                                          |
|--------------------|----------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `schema_version`   | int      | Always `1` currently. Consumers should reject newer versions they don't understand.                                                                                              |
| `name`             | string   | Artist-supplied display name. May be empty.                                                                                                                                      |
| `author`           | string   | Artist-supplied author tag. May be empty.                                                                                                                                        |
| `character_id`     | string   | **Required.** The character this skin is bound to. Skin slot names key into that character's specific VRAM rects, so reusing a skin on a different character would miss/corrupt. |
| `slots`            | object   | Map of skin-slot name → slot payload. Same shape as paintjob slots (16 PSX colors + optional 4bpp pixels). Slot names come from the active profile's `skin_slots` list.          |
| `vertex_overrides` | object   | Map of gouraud-table index (string-encoded int) → RGB triple. Skin-only feature. Empty if the skin doesn't override any vertex colors.                                           |

Skins are **character-bound and not portable**. The designer enforces this by:

- Requiring a `character_id` at creation time (the New Skin flow opens a character picker).
- Only seeding the character's `skin_slots` (never `kart_slots`) into a fresh skin.
- Locking the preview character combo to the bound character whenever a skin is selected.

If a saved skin's `character_id` doesn't exist in the active profile, the designer keeps the file in the library but won't render it. Consumers targeting a different mod should check `character_id` against their roster before applying.

### Slot payload

Identical shape to the paintjob format — see [paintjob_library_format.md#slot-payload](./paintjob_library_format.md#slot-payload). The only difference is that skin slots key into the character's *skin*-side CLUTs (face, accessories, character-specific detail textures) rather than the kart-side ones.

### Vertex overrides

Standard CTR character bodies are colored per-vertex (Gouraud) rather than via VRAM CLUTs. The mesh's `gouraud_colors` table holds one RGB triple per gouraud entry; geometry references the table by index. To recolor those surfaces you override entries in this table:

| Field   | Type    | Meaning                                                                                                          |
|---------|---------|------------------------------------------------------------------------------------------------------------------|
| key     | string  | Stringified non-negative integer — the gouraud-table index this override replaces.                               |
| `r`     | int     | Red channel, 0–255 (8-bit). Vertex colors aren't quantized through a CLUT, so the full 8-bit precision is kept.  |
| `g`     | int     | Green channel, 0–255.                                                                                            |
| `b`     | int     | Blue channel, 0–255.                                                                                             |

- Indices not present in `vertex_overrides` keep the mesh's baked color.
- The override's int key is JSON-encoded as a string (pydantic auto-coerces back).
- Consumers applying a skin must look up the active character's mesh, iterate the gouraud table, and substitute overridden indices before submitting vertex colors to the GPU.

## Color format

Skin slot colors use the same PSX 16-bit `#xxxx` format as paintjob slots — see [paintjob_library_format.md#color-format](./paintjob_library_format.md#color-format).

Vertex override colors use plain 8-bit RGB (`r`, `g`, `b` ∈ 0–255) because gouraud colors aren't routed through a CLUT.

## Canonical slot names

Skin slot names are profile-specific and character-specific. The vanilla profile derives them from each character's mesh — many appear as `clut_<x>_<y>` placeholders pending identification (e.g. `clut_18_240` is a face CLUT on most racers). The standard-racer kart and skin slot lists are stored in `config/profiles/vanilla-ntsc-u.json` under each character's `kart_slots` and `skin_slots`.

Consumer tools should treat the slot-name set as authoritative per-profile and per-character; don't hard-code names that aren't in the canonical kart-slot list.
