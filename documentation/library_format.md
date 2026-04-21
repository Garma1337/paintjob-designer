[<- Back](./README.md)

# Paintjob Library Format

This document describes the on-disk format the paintjob designer writes when you "Save Library As…". The idea is that authors of mods for CTR write their own tools that can consume a paintjob library to integrate it into their mod.

**Machine-readable schema**: [`schema/library.json`](../schema/library.json). Generated from the pydantic models in `paintjob_designer/models/` and kept in lockstep with them via `tests/paintjob/test_schema.py`. Consumer tools in other languages can validate against this file using any JSON Schema library; the fields / types / examples it emits are authoritative. If the schema and this human-readable doc ever disagree, the schema wins.

## Directory layout

A saved library is a directory of JSON files, one per paintjob:

```
MyLibrary/
├── 00_crash.json
├── 01_cortex.json
├── 02_racing_stripes.json
├── 03_penta.json
├── …
└── 15_saphi.json
```

- Files are named `NN_<slug>.json` where `NN` is the zero-padded library index (matching the position in the sidebar) and `<slug>` is a filesystem-safe derivation of the paintjob name (falls back to `base_character_id`, then `paintjob_NN`).
- Load order is lexicographic on filename, so the `NN_` prefix deterministically round-trips the library's ordering across save/load cycles.
- Tools should treat the numeric prefix as authoritative for indexing; the slug is a human-readable hint only.

## One paintjob file

Each `.json` is a single `Paintjob`:

```json
{
  "schema_version": 1,
  "name": "Racing stripes",
  "author": "Garma",
  "base_character_id": "crash",
  "slots": {
    "front": {
      "colors": ["#0000", "#7fff", "#03eb", "..."],
      "pixels": []
    },
    "back": {
      "colors": ["#0000", "#7C00", "..."],
      "pixels": []
    }
  }
}
```

### Top-level fields

| Field               | Type           | Meaning                                                                                                                                                          |
|---------------------|----------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `schema_version`    | int            | Always `1` currently. Consumers should reject newer versions they don't understand.                                                                              |
| `name`              | string         | Artist-supplied display name. May be empty.                                                                                                                      |
| `author`            | string         | Artist-supplied author tag. May be empty.                                                                                                                        |
| `base_character_id` | string \| null | Non-authoritative home-character hint. Used by the designer's preview fallback. Consumers may use it to infer default character bindings but aren't required to. |
| `slots`             | object         | Map of slot name → slot payload. Only slots the artist has explicitly authored appear here; unedited slots are absent, not zero-filled.                          |

Paintjobs are fully character-agnostic. The designer only allows texture imports on slots whose VRAM rect dimensions are invariant across every profile character, so imported pixel buffers upload cleanly to any character. Slots with per-character dim variation (e.g. `floor` in vanilla CTR) are CLUT-editable but not textureable — they have no `pixels` entries in any paintjob.

### Slot payload

Each entry in `slots` is an object with two fields:

```json
{
  "colors": ["#xxxx", "#xxxx", …],  // 16 entries, required
  "pixels": [                       // 0 or more region payloads
    {
      "vram_x": 984,
      "vram_y": 48,
      "width": 32,
      "height": 16,
      "data": "<base64>"
    }
  ]
}
```

| Field    | Type         | Meaning                                                                                                                                                                                                                                                              |
|----------|--------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `colors` | `string[16]` | The slot's 16 CLUT entries as PSX 16-bit hex (`#xxxx`). Always exactly 16 entries. The stp bit is preserved — e.g. `#8000` is not the same as `#0000`. Index 0 is the PSX transparency sentinel by convention; the designer's texture quantizer reserves it.         |
| `pixels` | `object[]`   | Per-region 4bpp pixel payload. Empty = CLUT-only slot (the CLUT alone defines the paintjob's effect on that slot). One or more entries = the paintjob has imported custom textures for this slot. Only slots with dim-invariant VRAM rects may carry pixel payloads. |

### Pixel region payload

When present, each `pixels[]` entry describes one VRAM rectangle:

| Field              | Type   | Meaning                                                                                                                                                                                                                                                                                                    |
|--------------------|--------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `vram_x`, `vram_y` | int    | VRAM position (in 16bpp u16 units) the slot sampled from on the character the artist was previewing at import time. Informational — consumer tools should use each target character's own mesh-derived rect at runtime, not this field. Included to make the payload self-describing and to aid debugging. |
| `width`, `height`  | int    | **Pixel-space** dimensions — the actual number of indexed pixels per row, not VRAM u16 units. For 4bpp payloads `width` is always a multiple of 4 (a VRAM u16 holds 4 nibbles). Consumer tools that emit PSX `RECT` structs must divide `width` by 4 before emitting `RECT.w`.                             |
| `data`             | string | Base64-encoded 4bpp packed pixel bytes. Two pixels per byte, **low nibble = left pixel**, matching the PSX GPU's sample order. Expected byte count = `width * height / 2`.                                                                                                                                 |

## Color format

PSX 16-bit color (`#xxxx`):

```
bit 15:    stp (semi-transparency flag)
bit 14–10: blue  (5 bits)
bit  9–5:  green (5 bits)
bit  4–0:  red   (5 bits)
```

- Value `0x0000` is the PSX per-pixel transparency sentinel.
- The designer's color picker and texture quantizer snap to this 5-5-5 grid; round-tripping through the JSON is exact.

## Pixel format

4bpp packed, two pixels per byte, low nibble = left. For a 32×16 texture (as e.g. Penta's "front" slot):

- 32 pixels × 16 rows = 512 pixels
- 4bpp = 2 pixels per byte → 256 bytes total
- Base64 encoded in `data`

To decode: iterate `data` byte-by-byte, each byte produces two pixel indices (low, high) in that order; each index is 0–15 into `colors`.

## Canonical slot names

The designer uses a fixed 8-slot order that mirrors the PSX `Texture` union used by CTR's vanilla paintjob system:

```
front, back, floor, brown, motorside, motortop, bridge, exhaust
```

Consumer tools should use this exact spelling when looking up entries in the `slots` map. Any slot name not in this list is "unrecognized" — the designer may still preserve round-trip if the JSON has it, but consumers targeting CTR should ignore or error on unknown names.
