[<- Back](./README.md)

# Paintjobs Explained

**Vanilla CTR has paintjobs — just not ones the player can pick.** Every character wears one fixed palette, baked at build time into a single file called `PAINTALL.BIN`. There is no menu, no cycling, no per-session choice: Crash always wears his palette, Cortex always wears his, and the game has no mechanism to swap them.

This document explains what CTR actually stores, what "paintjob swapping" really does at a foundational level, what's missing from vanilla's infrastructure that keeps new paintjobs out of the game, and why the designer emits a JSON library instead of a binary you can paste into your ISO.

## Table of Contents

- [What CTR Actually Stores](#what-ctr-actually-stores)
- [What "Paintjob Swapping" Actually Does](#what-paintjob-swapping-actually-does)
- [Vanilla's Fixed Mapping](#vanillas-fixed-mapping)
- [What a Paintjob Mod Adds](#what-a-paintjob-mod-adds)
- [Why the Designer Outputs JSON](#why-the-designer-outputs-json)
- [Division of Labor: Designer vs Mod](#division-of-labor-designer-vs-mod)
- [Common Questions](#common-questions)

## What CTR Actually Stores

Every kart in vanilla CTR shares the **same pixel texture** — one 4-bit-per-pixel image that covers the front panel, back panel, floor, motor, exhaust, bridge, and so on. What makes Crash's kart look different from Cortex's isn't the geometry or the pixels; it's the **palettes** the game binds when it draws each character.

The data shape per character is:

1. **One 4bpp texture in VRAM** — shared across every character. Each pixel is a 4-bit *index* (0–15), not a color.
2. **Eight 16-color palettes (CLUTs), one per slot.** The paintjob designer's canonical slot names match exactly: `front`, `back`, `floor`, `brown`, `motorside`, `motortop`, `bridge`, `exhaust`. Different triangles of the mesh sample different CLUTs, so the same texture can render as eight independently-colored body parts.
3. **A file called `PAINTALL.BIN`** that bundles every character's eight CLUTs into one asset. Vanilla ships this with about 15 entries (one per character). The game loads the whole thing at startup and uploads the right character's CLUTs to VRAM as each character is brought up.

There is no "paintjob record" distinct from the character — *a character's paintjob is just the row of CLUTs assigned to that character in `PAINTALL.BIN`.*

## What "Paintjob Swapping" Actually Does

Conceptually, changing a paintjob is nothing more than:

> At the right point in the character-load flow, overwrite the 16-color rectangles in VRAM with a different set of values from `PAINTALL.BIN`.

The shared texture doesn't change. The UVs don't change. The mesh doesn't change. Only the content of the CLUT rectangles changes, and because the pixel indices were the only thing tying geometry to colors, every face that sampled through those CLUTs now shows the new colors.

So a paintjob, as data, is really just *"a bag of bytes that go into specific VRAM rectangles at character-load time."* `PAINTALL.BIN` is the on-disk wrapper for those bags.

## Vanilla's Fixed Mapping

Vanilla ships the lookup code, the data file, and the VRAM upload — the entire machinery — but with one significant limitation for modders: **the mapping from character to paintjob is 1:1 and baked in.** The relevant facts:

- **One paintjob per character.** `PAINTALL.BIN` contains roughly 15 entries, one for each vanilla character. There is no array of alternates.
- **Selection is implicit.** When character C is loaded, the game takes the Cth entry of `PAINTALL.BIN` and uploads its CLUTs to VRAM. The player never picks.
- **Entry count is a build-time constant.** The struct that holds the table is sized by a compile-time macro. You can't append entries to `PAINTALL.BIN` and expect the game to find them — the loader walks a fixed-size array.

So vanilla has every building block a paintjob system needs **except** variability: more than one palette per character, a way for the game to know which one to load, and a way for the player to choose. Adding any of that requires changing code, not just data.

## What a Paintjob Mod Adds

The CTR-ModSDK project has one working paintjob mod — `mods/Modules/PaintJobs_OnlyUSA` — that turns vanilla's fixed palette into a selectable one. Looking at what it touches shows exactly which gaps a mod has to fill:

- **Extended `PAINTALL.BIN`.** The mod rebuilds the file with 21 entries instead of 15 — the original 15 plus 6 new variants. The struct layout is unchanged; only the entry count and the bundled data grow. The mod's `tex.h` bumps `NUM_PAINT_JOB` from 15 to 21 so the array sizing matches the new binary.
- **Per-player paintjob index.** The mod keeps a small `characterIndex[character]` array tracking which paintjob each player has selected per character, since "paintjob N of character C" is now a live choice instead of a compile-time constant.
- **Character-select UX.** Hooks into the character-select menu wire L2/R2 to cycle through the 21 paintjobs for the highlighted character. The selected index drives a `loadCLUT()` call that uploads the chosen entry's CLUTs to VRAM.
- **Game-code patches.** The mod hooks `GAMEPROG` and the character-select screen to inject its palette-cycling logic into the vanilla flow. Without these patches the new `PAINTALL.BIN` entries would just sit there — the vanilla loader still wants the old-sized array.

In principle, each mod makes its own decisions about:

- How many paintjobs per character to support (affects number of paintjobs and the on-disk size)
- Which menu screens grow a picker UI and which buttons map to cycling
- Whether paintjob selection survives a race, persists to save data, syncs in multiplayer
- Which regional EXE to patch (the `OnlyUSA` suffix on the example mod isn't decorative — the hooks are offset-specific)

## Why the Designer Outputs JSON

Given the above, the designer's job is narrowly defined:

> Produce the visual content of paintjobs (colors and optional pixels) in a format that any mod's build pipeline can read and pack into its own `PAINTALL.BIN`.

The designer's output is therefore a **library directory** — a folder of per-paintjob JSON files, ordered by filename prefix. This is intentionally one step removed from the game. The mod's own toolchain reads the library and emits the `PAINTALL.BIN` (plus any linker symbols, headers, or patches its build needs) that the patched game actually loads.

## Division of Labor: Designer vs Mod

| Concern                                           | Paintjob Designer | Mod's own tooling |
|---------------------------------------------------|:-----------------:|:-----------------:|
| Painting 16-color palettes                        |         ✓         |                   |
| Importing PNGs into 4bpp texture slots            |         ✓         |                   |
| Storing the authored result (JSON library)        |         ✓         |                   |
| Validating the library against a published schema |         ✓         |                   |
| Rebuilding `PAINTALL.BIN` with extra entries      |                   |         ✓         |
| Bumping paintjob count and recompiling the loader |                   |         ✓         |
| Hooking the character-select menu for cycling UX  |                   |         ✓         |
| Patching the regional EXE                         |                   |         ✓         |
| Rebuilding the ISO                                |                   |         ✓         |

The designer sits upstream of "any specific mod." It produces the *content*. Each mod owns the *delivery*.
