# User Guide

This guide covers internal behaviors and details that aren't immediately obvious from the editor's UI. Basic things — click a swatch, pick a color — aren't documented here; read on for the gotchas.

## Table of Contents

- [First Launch and ISO Layout](#first-launch-and-iso-layout)
- [Profiles](#profiles)
  - [Switching Profiles Resets the Session](#switching-profiles-resets-the-session)
  - [Where Profile JSONs Live](#where-profile-jsons-live)
  - [paintjob_slots Binding](#paintjob_slots-binding)
- [Paintjob Library](#paintjob-library)
  - [Library Position Is the In-Game Paintjob Index](#library-position-is-the-in-game-paintjob-index)
  - [Sidebar Context Menu](#sidebar-context-menu)
- [Preview Character](#preview-character)
  - [Home Character vs Preview Character](#home-character-vs-preview-character)
- [Slot Editor](#slot-editor)
  - [CLUT Index 0 Is Transparent](#clut-index-0-is-transparent)
  - [Highlight Button](#highlight-button)
  - [Reset vs Undo](#reset-vs-undo)
- [3D Preview](#3d-preview)
  - [Orbit Camera Controls](#orbit-camera-controls)
  - [Reset Camera and the Pivot Point](#reset-camera-and-the-pivot-point)
  - [Eyedropper (Right-Click)](#eyedropper-right-click)
  - [Gouraud + PSX Texture Modulation](#gouraud--psx-texture-modulation)
  - [GL Init Failure](#gl-init-failure)
- [Animation Playback](#animation-playback)
- [Color Picker](#color-picker)
- [Transform Colors](#transform-colors)
  - [Modes](#modes)
  - [Scope](#scope)
  - [Preview vs Apply](#preview-vs-apply)
- [Gradient Fill](#gradient-fill)
- [Undo / Redo](#undo--redo)
- [Import / Export](#import--export)
  - [Open Library / Save Library](#open-library--save-library)
  - [Single-Paintjob Export](#single-paintjob-export)
  - [JSON Is Character-Agnostic](#json-is-character-agnostic)
  - [JSON Colors Preserve the Full u16](#json-colors-preserve-the-full-u16)
  - [Exports Backfill Unauthored Slots](#exports-backfill-unauthored-slots)
  - [PAINTALL.BIN Layout](#paintallbin-layout)
- [Schema](#schema)
- [Drag-and-Drop](#drag-and-drop)
- [Packaging Notes](#packaging-notes)

## First Launch and ISO Layout

On first launch the window opens with an empty sidebar and the status bar reading `No ISO loaded — use File → Load ISO...`. Point it at the root of your extracted CTR directory — specifically the folder that contains `bigfile/`. The tool probes `bigfile/models/racers/hi/<character>.ctr` for each profile character; if those aren't present you'll get a "load failed" status when that character is previewed but the rest of the app still works.

The ISO path is saved to `%APPDATA%/python/paintjob-designer/config.json` (or the platform equivalent of `QStandardPaths.AppDataLocation`). Re-pointing via **File → Load ISO...** rewrites the same file.

## Profiles

A **profile** is a JSON file under `config/profiles/` that describes three things:

- **Characters** — id, display name, mesh path (relative to ISO root), slot names + CLUT coordinates (both race and menu).
- **Paintjob slots** — the ordered binding table that PAINTALL.bin's `colors[N]` materializes: each entry carries a display name and an optional home character.
- **VRAM page dimensions** — usually the PS1 default 1024×512.

The profile controls every downstream behavior: which characters populate the preview dropdown, which CLUT coords are read from VRAM, and which index each library paintjob occupies in the binary output.

### Switching Profiles Resets the Session

**File → Switch Profile...** (or the toolbar button) opens a picker over `ProfileRegistry.available()`. Confirming clears the in-memory library and undo stack — character IDs, slot names, and paintjob bindings can all differ between profiles, so carry-over isn't safe. Save the library first if it matters.

The choice is persisted to `last_profile_id` in the config, so the next launch picks up where you left off.

### Where Profile JSONs Live

At build time: `config/profiles/<id>.json`. At runtime in a PyInstaller bundle: extracted under `sys._MEIPASS/config/profiles/` — `ProfileRegistry` handles both layouts automatically.

To add your own profile, drop a JSON file in `config/profiles/`; it shows up in the picker on next launch with its `id` field as the option value and its `display_name` as the visible label.

### paintjob_slots Binding

`profile.paintjob_slots[]` declares what PAINTALL.bin's `colors[N]` should contain. Each entry:

```json
{
  "name": "Crash",
  "default_character_id": "crash"
}
```

- `name` — display label shown in the game's paintjob-cycle menu / API.
- `default_character_id` — the character this paintjob is the home palette for. The game's runtime sets that character's `paintJobIndex` to this position on boot, and the exporter backfills this paintjob's unauthored slots from this character's VRAM. `null` means "no home character" — a shared paintjob with no default owner.

Unlock gating (what the game checks to decide if a paintjob is selectable in the menu) is mod-runtime C config, not paintjob-designer config — the editor doesn't model it.

When exporting PAINTALL.bin the library must have exactly `len(paintjob_slots)` paintjobs — the ordering lines up 1:1. The editor doesn't auto-populate the library from `paintjob_slots`; that's an intentional separation: the binding is static config, the library is authored content.

## Paintjob Library

The **left sidebar** lists every paintjob in the current session, not characters. **New** creates a blank paintjob at the end; **Delete** removes the selected one (and clears undo history so stale refs can't haunt the stack). Drag-to-reorder is enabled — rows moved via drag-drop update `PaintjobLibrary.move` under the hood.

Each paintjob carries four pieces of data:

- `name` — free-form; shown in the sidebar label and used as the default filename when exporting.
- `author` — metadata that round-trips through JSON.
- `base_character_id` — optional "home" character hint (see [Home Character vs Preview Character](#home-character-vs-preview-character)).
- `slots` — dict of 8 slot names → 16 colors each. Only slots the artist has touched are populated; unauthored slots fall back to VRAM at display and export time.

### Library Position Is the In-Game Paintjob Index

The sidebar's top-to-bottom order is the same as the `colors[N]` array PAINTALL.bin emits, which is the same as each character's `paintJobIndex` state at runtime. Reordering the sidebar re-indexes everything downstream. The default `NN_<slug>.json` filename `Save Library As...` uses encodes the position as a `00_`, `01_`, ... prefix so that `Open Library...`'s sorted-filename load round-trips the order.

### Sidebar Context Menu

Right-click a paintjob row for:

- **Rename...** — edit the paintjob's `name` field. Affects sidebar label and default export filename.
- **Export as JSON...** — save just that paintjob to a user-chosen path.
- **Export as Code...** — emit a `.c` + `paintjob.h` pair for that paintjob.
- **Replace from JSON...** — overwrite the selected paintjob with one loaded from disk. Clears undo.
- **Delete** — remove from the library. Clears undo.

## Preview Character

The **Preview on:** dropdown above the 3D viewer picks which character's mesh + VRAM the active paintjob is shown on. Paintjobs don't belong to characters — the dropdown is purely a viewing concern, so an "Saphi" paintjob can be auditioned on Crash, Cortex, or Penta without changing any data.

Switching preview character reloads the mesh and reruns the atlas decode against the current paintjob. Unauthored slots inherit VRAM defaults from the **preview character** (not `base_character_id`), so the 3D view always matches what the game would draw if *that* character wore this paintjob.

### Home Character vs Preview Character

Two distinct ideas:

- **Preview character** — chosen via the dropdown. Drives the 3D mesh and the fallback VRAM for unauthored slots *in the editor*.
- **Home character** — the character this paintjob belongs to in-game. Set via the paintjob's `base_character_id` field, or via `profile.paintjob_slots[i].default_character_id` (the profile binding wins at export time). Drives the fallback VRAM when exporting PAINTALL.bin — the game needs every slot populated with concrete CLUT bytes, and the home character's VRAM is the obvious source.

The editor displays what the paintjob looks like *right now on the preview character*. The exported file reflects what the paintjob looks like *at runtime on its home character*. The two usually agree but they're independent knobs.

## Slot Editor

Each row shows a slot's 16-color CLUT across its top, plus **Highlight** and **Reset** buttons right-aligned underneath. Clicking a swatch opens the color picker; changes apply immediately and stream into the 3D preview.

Right-click a swatch for the per-color context menu (**Transform colors...** scoped to this slot, prefilled with the clicked swatch as the match color). Right-click the slot row itself (outside any swatch) for the whole-slot menu — **Transform colors...** and **Gradient fill...**

### CLUT Index 0 Is Transparent

The first swatch of every row has an **orange border** and a tooltip explaining that CLUT index 0 is the PSX per-pixel transparency sentinel. Pixels that sample index 0 render fully transparent regardless of the RGB you set — editing this slot almost never does what you'd expect. The marker is a warning, not a lock; you can still edit it if you mean to.

### Highlight Button

Each slot row has a checkable **Highlight** button. Clicking it focuses that slot:

- In the 3D preview, every triangle not in the slot dims to 22% of its lit color.
- Clicking the same button again (or another row's button) clears / moves the focus.
- Switching to a different paintjob or preview character clears focus.
- Focus is per-session UI state — it doesn't affect the exported data.

The triangle → slot mapping is built from `SlotRegion.texture_layout_indices`; faces with no slot binding (wheel rims, shared driver geometry) never light up under any slot's focus.

### Reset vs Undo

- **Reset button** — replaces every color in that slot with the preview character's VRAM defaults. Pushes a `ResetSlotCommand` onto the undo stack, so Ctrl+Z un-resets cleanly.
- **Ctrl+Z** — reverses the most recent edit (color pick, reset, gradient fill, or transform), regardless of which paintjob currently selected. If the reverted edit targets a different paintjob than the one on screen, the sidebar selection automatically moves to that paintjob so the visible state tracks the unwound change.

The undo stack is session-wide and never auto-clears when you switch paintjobs. It does clear when you import a file or delete a paintjob — their commands' captured refs would otherwise point at stale data.

## 3D Preview

### Orbit Camera Controls

- **Left-drag** — orbit yaw/pitch. Pitch is clamped to ±85° to prevent flipping.
- **Wheel** — zoom. Distance is clamped between 0.1 and 20 units.
- **R** — reset camera (equivalent to **View → Reset Camera**).

### Reset Camera and the Pivot Point

Reset restores the camera to the pose it had right after the current preview character loaded — *not* world origin. The orbit pivot is the kart's bounding-box center, snapshotted by `OrbitCamera.fit_to_bounds` when the mesh was uploaded. This matters because `paintGL` drops the vertex buffer after upload; a naïve reset would have no bounds to fit and would pivot on (0, 0, 0), which is often far from the kart.

### Eyedropper (Right-Click)

**Right-click any surface on the 3D kart** to sample the slot + CLUT index under the cursor. The tool:

1. Ray-picks the triangle under the click (`paintjob_designer/render/ray_picker.py` — Möller–Trumbore against the flat triangle list).
2. Interpolates the hit's byte-space UV from the three vertex UVs via the hit's barycentric weights.
3. Maps the triangle's texture layout to its paintjob slot (via `SlotRegion.texture_layout_indices`).
4. Samples the atlas at the hit pixel and matches the RGB back to one of the slot's 16 PsxColors.
5. Opens the color picker pre-loaded with that color so one right-click + one picker pick → the color is changed.

If the click lands on an untextured face (Gouraud-only, wheel, or otherwise not paintjob-editable), the status bar reports that the face isn't bound to any slot and no picker opens. Rotation and zoom still work with left-drag / wheel in either case — there's no eyedropper mode to toggle.

### Gouraud + PSX Texture Modulation

Character meshes mix two face types:

- **Textured faces** sample a VRAM CLUT through a `TextureLayout` — these are the ones the paintjob edits.
- **Untextured faces** (`draw.tex_index == 0`) carry per-vertex **Gouraud colors** baked into the `.ctr`. They're not paintjob-editable but are rendered in their authored colors (Crash's red pants, Pura's orange fur, etc.) via the fragment shader's per-vertex color attribute.

Textured faces on PSX are modulated by `2 × vertex_color` (128/255 = "neutral / show texture as-authored"). A lot of CTR meshes ship greyscale texture templates that rely on that modulation to come out skin/fur-colored at runtime. The editor applies the same `clamp(texture × vcolor × 2, 0, 1)` in its fragment shader so the preview matches what the PS1 GPU would draw — without it, those faces show up as literal grey.

### GL Init Failure

If your system can't bring up OpenGL 3.3 core (old drivers, remote desktop without hardware accel, etc.), the 3D pane is replaced with a placeholder label reading "3D preview unavailable" plus the GL error. The slot editor, sidebar, and exports all stay fully functional — only the live preview is disabled.

## Animation Playback

The Animation panel below the sidebar shows up when the preview character's `.ctr` contains animation frames. Pick a clip, hit Play, and the 3D viewer steps through frames at the FPS you've set.

**FPS is a preview control, not a data field.** PS1 animations don't carry an intended framerate; the editor defaults to 30 fps because that's what looks reasonable for character idle loops. Nothing about the export or the paintjob itself cares about this value.

Playback re-assembles the mesh geometry on every tick (positions change, UVs don't) — fine for idle anims, measurably slower for very long clips with hundreds of frames.

## Color Picker

The picker is `QColorDialog` with `DontUseNativeDialog` set (the native Windows picker was cramped and wouldn't resize). The window is 1100×640.

Any color you pick is **snapped to the PSX 15-bit grid** before being written back: 5 bits per channel, so 32 levels each. What you see in the swatch after picking is exactly what the game will display. The snap is lossy; `#FF7F3A` going in might come back as `#FF7F38`.

The `stp` bit of the original color is preserved when possible (see [JSON Colors Preserve the Full u16](#json-colors-preserve-the-full-u16)).

## Transform Colors

The **Transform Colors...** action (top toolbar, or right-click menus on swatches and slot rows) opens a dialog for bulk edits. Every change the dialog makes is bundled into a single `BulkTransformCommand`, so Ctrl+Z reverts the whole batch. All transforms target the currently-selected paintjob.

### Modes

- **Replace matching color** — pick a "Match" and a "Replace with" color; every CLUT entry in scope whose *full u16 value* equals "Match" gets rewritten. Matching by u16 means stp=0 and stp=1 variants of the same RGB don't collide (a transparent-sentinel black never gets promoted to opaque black by accident).
- **Shift hue** — slider in degrees (−180°..+180°). Converts each color to HSV, rotates hue, converts back. Wraps cleanly around the hue wheel.
- **Shift brightness / saturation** — sliders in percent. Additive on HSV V/S, clamped to [0, 1].
- **RGB delta** — three sliders in RGB units (−255..+255). Additive per channel, clamped to [0, 255].

All modes preserve the stp bit of each edited color. The PSX transparency sentinel (u16 value `0`) is never touched by any mode — it's a structural marker, not a real color.

### Scope

- **Just this slot** — transforms the 16 colors of the clicked slot.
- **Entire kart** — transforms every slot of the active paintjob (8 × 16 = 128 entries).

Entry points pre-fill the scope and, for Replace mode, the Match color:

- Right-click a **swatch** → dialog opens with scope = this slot, Match = the clicked color.
- Right-click a **slot row** → dialog opens with scope = this slot, no Match prefill.
- Toolbar **Transform Colors...** → dialog opens with scope = entire kart.

You can always switch scope inside the dialog.

### Preview vs Apply

The dialog's inline swatch strip shows before → after for every CLUT entry that *would* change — updates as you move any control.

The **Preview** button pushes the current transform into the real paintjob + 3D view. Rotate the kart, check how it looks, tweak the sliders, click Preview again. The paintjob is kept in a "what the transform would commit" state until you close the dialog. Cancel reverts everything the previews ever touched. Apply commits the final transform as one undo entry; the live state from your last Preview click is re-applied from a clean snapshot first, so residue from previous Preview clicks that touched different indices can't leak in.

Performance: bulk updates batch per slot (one atlas render + one full-atlas GL upload per Preview / Apply) — an entire-kart hue shift of 100+ colors across 8 slots lands in a single frame.

## Gradient Fill

Right-click a slot row → **Gradient fill...** fills a contiguous index range with a linear interpolation between two endpoint colors.

- **Color space** — `RGB (linear per channel)` or `HSV (short arc on hue wheel)`. RGB is predictable but can wash out at midpoints (e.g. red → blue passes through desaturated grey). HSV picks the shorter arc around the hue wheel, so red → blue goes through magenta instead.
- **From / To index** — the contiguous range to fill. Defaults skip index 0 (the transparency sentinel).
- **Endpoints** — both are preserved exactly; intermediate colors are PSX-quantized to the 5-5-5 grid. All output colors inherit the start endpoint's stp bit.
- Result is pushed as one `BulkTransformCommand` — one Ctrl+Z reverts the whole fill.

## Undo / Redo

- **Ctrl+Z / Ctrl+Shift+Z** (or Ctrl+Y) — single session-wide stack.
- Undo works across sidebar selections: edit paintjob A, switch to paintjob B, edit B, Ctrl+Z twice — B's edit reverts first, then A's. If the reverted edit targets a paintjob that isn't currently selected, the sidebar auto-switches to it.
- **Imports clear the undo stack.** Loading a library or importing/replacing a paintjob creates state the edit commands can't reason about.
- **Deleting a paintjob clears the undo stack** — captured paintjob refs would otherwise point at a removed object.
- **Switching profiles clears the undo stack** — character IDs and slot names change, old commands can't replay.

## Import / Export

### Open Library / Save Library

- **File → Open Library...** (Ctrl+O) reads every `*.json` file under a chosen directory in sorted-filename order. The `NN_<name>.json` convention `Save Library As...` writes uses the `NN_` prefix to pin library index → filename index, so a saved library reopens with identical ordering. Non-JSON files in the directory are ignored; a JSON file that fails to parse stops the load with a message naming the offending file.
- **File → Save Library As...** (Ctrl+Shift+S) writes each library paintjob to a chosen directory as `NN_<name-slug>.json`. Same as clicking **Save Library** on the toolbar.
- **File → Import Paintjob...** appends a single `.json` to the end of the library.

### Single-Paintjob Export

Right-click a paintjob in the sidebar:

- **Export as JSON...** — save just that paintjob. Default filename is the paintjob's `name` slugified, falling back to `base_character_id` or `paintjob_NN`.
- **Export as Code...** — emit a `.c` + `paintjob.h` pair. The dialog lets you pick the C identifier used for the slot arrays (`front_<id>`, ...) and the `PAINT<N>` aggregator index; both default to the paintjob's position in the library.

### JSON Is Character-Agnostic

The `.json` format stores `{schema_version, name, author, base_character_id, slots: {slot_name: [16 colors]}}`. No profile ID, no mesh binding. A paintjob authored against Crash can be previewed on Cortex without modification — slot names are shared across characters in the profile, and `base_character_id` is only a preview-fallback hint.

### JSON Colors Preserve the Full u16

Each color is serialized as a 4-digit hex string like `"#7fff"` — the raw PSX 16-bit value, *not* `#RRGGBB`. This matters for round-tripping:

- PSX renders `value == 0` as fully transparent, regardless of the stp bit.
- A CLUT entry with RGB `(0, 0, 0)` and stp=1 has `value == 0x8000` and renders as *opaque black*.
- The same RGB with stp=0 has `value == 0` and renders as transparent.

If colors were stored as 6-digit RGB hex, every opaque black would collapse to transparent on reimport. The u16 format makes the whole round-trip exact. The reader also accepts the legacy 6-digit `#RRGGBB` form (treated as stp=0).

### Exports Backfill Unauthored Slots

Per-paintjob JSON and code exports call `ProjectHandler.with_backfilled_defaults` with the preview character's VRAM defaults, so slots the artist has *edited* win, slots they haven't touched fall back to concrete CLUT bytes, and every slot the profile knows about lands in the output file. This avoids the foot-gun where a partially-authored paintjob reimports with missing-slot holes.

### PAINTALL.BIN Layout

Toolbar → **Export PAINTALL.bin** writes the `TexData` struct the vanilla CTR loads at PS1 RAM address `0x801CE000` and cast directly to a typed pointer:

```c
typedef struct {
    Texture colors[N];         // N = len(profile.paintjob_slots) = library.count()
    Texture colorsMenuPos[M];  // M = len(profile.characters) — menu-screen VRAM
    Texture colorsRacePos[M];  // M = len(profile.characters) — in-race VRAM
} TexData;
```

`Texture` is a union of 8 pointers in canonical slot order (`front, back, floor, brown, motorside, motortop, bridge, exhaust`). `N` and `M` are independent — Saphi has 16 paintjobs across 15 characters, vanilla CTR has 15 of each.

The exporter:

1. **Iterates the library** — paintjob `i` in the sidebar becomes `colors[i]` in the file.
2. **Backfills each paintjob** from its home character's VRAM. Home character is `profile.paintjob_slots[i].default_character_id` (the binding wins), falling back to the paintjob's own `base_character_id` for entries where the binding is `null`. Slots the artist has already authored take priority.
3. **Pre-resolves pointers as absolute PS1 addresses.** After `LOAD_XnfFile` drops the file at `0x801CE000`, the struct casts cleanly and every pointer dereferences correctly without a runtime fixup pass.
4. **Validates up front.** Library size must match `len(profile.paintjob_slots)`; every character must declare all 8 canonical slots with both `clut` (race) and `clut_menu` coordinates; every paintjob must end up with all 8 slots populated after backfill. A single error message lists every missing piece before any bytes are written.

Profile slots accept `clut_menu: {x, y}` alongside `clut: {x, y}`. The menu position differs from the race position because the character-select screen lays all characters out at once — each needs its own VRAM CLUT slot there. Profiles without `clut_menu` can still be used for every other feature; they just can't target PAINTALL.bin.

## Schema

Paintjob JSONs and profile JSONs both carry a `schema_version` field. Both readers reject files with a newer-than-supported version. The editor is pre-release, so no legacy-version migration pipeline is in place — every file must declare the current schema.

## Drag-and-Drop

Drag a `.json` file onto the main window to append it to the library (same as **File → Import Paintjob...**). Other file types are silently ignored to avoid the cryptic "open failed" an unfiltered handler would produce.

## Packaging Notes

- Built with PyInstaller in the release workflow (`.github/workflows/release.yml`). One-dir bundle, Windows + Linux, zipped as `.7z`.
- Three directories have to be `--add-data`-bundled because they're read at runtime:
  - `config/profiles/` — profile JSONs (`ProfileRegistry` falls back to `sys._MEIPASS`)
  - `paintjob_designer/exporters/templates/` — the `paintjob.h` template written next to each `.c` export
  - `paintjob_designer/gui/widget/shaders/` — the vert/frag GLSL files loaded at module import
- The last two live inside the Python package tree, so `Path(__file__).parent / "..."` resolves in both source and frozen builds without special handling.
- No icon by default. Drop a `.ico` into the packaging step if you want custom taskbar branding.

## Known Limitations

- **One mesh only.** The tool reads `model.meshes[0]` of the preview character's `.ctr` — the high-LOD body. Wheels and flame/plume effects live outside the character's `.ctr` (wheels are sprite icons from `iconGroup[0]`, flames are separate model IDs) and aren't rendered here.
- **Animation framerates are guessed.** No clip metadata carries an intended FPS; 30 is a preview default.
- **PAINTALL.bin needs `clut_menu` per slot AND a matching `paintjob_slots` table in the profile.** The binary export fails fast with a list of missing entries; populating the profile JSON unblocks it.
