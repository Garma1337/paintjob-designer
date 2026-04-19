# User Guide

This guide covers internal behaviors and details that are not immediately obvious from the editor's UI. Basic things — click a swatch, pick a color — aren't documented here; read on for the gotchas.

## Table of Contents

- [First Launch and ISO Layout](#first-launch-and-iso-layout)
- [Profiles](#profiles)
  - [Switching Profiles Resets the Session](#switching-profiles-resets-the-session)
  - [Where Profile JSONs Live](#where-profile-jsons-live)
- [Character Sidebar](#character-sidebar)
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
  - [Right-Click Targets a Single Character](#right-click-targets-a-single-character)
  - [Toolbar Batch-Exports What You've Edited](#toolbar-batch-exports-what-youve-edited)
  - [JSON Is Character-Agnostic](#json-is-character-agnostic)
  - [JSON Colors Preserve the Full u16](#json-colors-preserve-the-full-u16)
  - [Exports Include Every Slot](#exports-include-every-slot)
  - [Binary Export Zero-Pads Un-edited Characters](#binary-export-zero-pads-un-edited-characters)
- [Schema Migration](#schema-migration)
- [Drag-and-Drop](#drag-and-drop)
- [Packaging Notes](#packaging-notes)

## First Launch and ISO Layout

On first launch the window opens with an empty sidebar and the status bar reading `No ISO loaded — use File → Load ISO...`. Point it at the root of your extracted CTR directory — specifically the folder that contains `bigfile/`. The tool probes `bigfile/models/racers/hi/<character>.ctr` for each profile character; if those aren't present you'll get a per-character "load failed" message when you click them but the rest of the app still works.

The ISO path is saved to `%APPDATA%/python/paintjob-designer/config.json` (or the platform equivalent of `QStandardPaths.AppDataLocation`). Re-pointing via `File → Load ISO...` rewrites the same file.

## Profiles

A **profile** is a JSON file under `config/profiles/` that describes:

- Which characters exist
- Each character's mesh path (relative to the ISO root)
- Each character's slot names + CLUT coordinates

The profile controls every downstream behavior: what fills the sidebar, which CLUT coords are read from VRAM, how binary exports order their entries.

### Switching Profiles Resets the Session

**File → Switch Profile...** (or the toolbar button) opens a picker over `ProfileRegistry.available()`. Confirming clears the in-memory `Paintjob` and undo stack — character IDs may differ between profiles, so edits can't be trusted to map cleanly. Export what you've got before switching if it matters.

The choice is persisted to `last_profile_id` in the config, so the next launch picks up where you left off.

### Where Profile JSONs Live

At build time: `config/profiles/<id>.json`. At runtime in a PyInstaller bundle: extracted under `sys._MEIPASS/config/profiles/` — `ProfileRegistry` handles both layouts automatically.

To add your own profile, drop a JSON file in `config/profiles/`; it shows up in the picker on next launch with its `id` field as the option value and its `display_name` as the visible label.

## Character Sidebar

The active character is always visible on the left. Clicking a row loads the character's mesh, VRAM atlas, and any edits you've already made this session.

**Right-click** any row for the per-character menu: Import from JSON, Export as JSON, Export as Code. Right-click acts on *that* character regardless of which one is currently displayed — the tool quietly warps to the target before running the export so slot defaults come from the right VRAM.

## Slot Editor

Each row shows a slot's 16-color CLUT across its top, plus **Highlight** and **Reset** buttons right-aligned underneath. Clicking a swatch opens the color picker; changes apply immediately and stream into the 3D preview.

Right-click a swatch for the per-color context menu (**Transform colors...** scoped to this slot, prefilled with the clicked swatch as the match color). Right-click the slot row itself (outside any swatch) for the whole-slot menu — **Transform colors...** and **Gradient fill...**

### CLUT Index 0 Is Transparent

The first swatch of every row has an **orange border** and a tooltip explaining that CLUT index 0 is the PSX per-pixel transparency sentinel. Pixels that sample index 0 render fully transparent regardless of the RGB you set — editing this slot almost never does what you'd expect. The marker is a warning, not a lock; you can still edit it if you mean to.

### Highlight Button

Each slot row has a checkable **Highlight** button. Clicking it focuses that slot:

- In the 3D preview, every triangle not in the slot dims to 22% of its lit color.
- Clicking the same button again (or another row's button) clears / moves the focus.
- Switching to a different character clears focus.
- Focus is per-session UI state — it doesn't affect the exported data.

The triangle→slot mapping is built from `SlotRegion.texture_layout_indices`; faces with no slot binding (wheel rims, shared driver geometry) never light up under any slot's focus.

### Reset vs Undo

- **Reset button** — replaces every color in that slot with the VRAM defaults read directly from the `.vrm`. Pushes a `ResetSlotCommand` onto the undo stack, so Ctrl+Z un-resets cleanly.
- **Ctrl+Z** — reverses the most recent edit (color pick, reset, gradient fill, or transform), regardless of whether it was on the current character.

The undo stack is session-wide and never auto-clears across character switches. It does clear when you import a paintjob file (the imported slots aren't reachable through the edit commands). Bulk operations (Transform Colors, Gradient Fill) collapse into a single undo entry — one Ctrl+Z reverts the whole batch.

## 3D Preview

### Orbit Camera Controls

- **Left-drag** — orbit yaw/pitch. Pitch is clamped to ±85° to prevent flipping.
- **Wheel** — zoom. Distance is clamped between 0.1 and 20 units.
- **R** — reset camera (equivalent to **View → Reset Camera**).

### Reset Camera and the Pivot Point

Reset restores the camera to the pose it had right after the current character loaded — *not* world origin. The orbit pivot is the kart's bounding-box center, snapshotted by `OrbitCamera.fit_to_bounds` when the mesh was uploaded. This matters because `paintGL` drops the vertex buffer after upload; a naïve reset would have no bounds to fit and would pivot on (0, 0, 0), which is often far from the kart.

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

If your system can't bring up OpenGL 3.3 core (old drivers, remote desktop without hardware accel, etc.), the 3D pane is replaced with a placeholder label reading "3D preview unavailable" plus the GL error. The slot editor, exports, and undo all stay fully functional — only the live preview is disabled.

## Animation Playback

The Animation panel below the character list shows up for characters whose `.ctr` contains animation frames. Pick a clip, hit Play, and the 3D viewer steps through frames at the FPS you've set.

**FPS is a preview control, not a data field.** PS1 animations don't carry an intended framerate; the editor defaults to 30 fps because that's what looks reasonable for character idle loops. If a clip has bigger frames-per-step, bump the spinner up; nothing about the export or the paintjob itself cares.

Playback re-assembles the mesh geometry on every tick (positions change, UVs don't) — fine for idle anims, measurably slower for very long clips with hundreds of frames.

## Color Picker

The picker is `QColorDialog` with `DontUseNativeDialog` set (the native Windows picker was cramped and wouldn't resize). The window is 1100×640.

Any color you pick is **snapped to the PSX 15-bit grid** before being written back: 5 bits per channel, so 32 levels each. What you see in the swatch after picking is exactly what the game will display. The snap is lossy; `#FF7F3A` going in might come back as `#FF7F38`.

The `stp` bit of the original color is preserved when possible (see [JSON Colors Preserve the Full u16](#json-colors-preserve-the-full-u16)).

## Transform Colors

The **Transform Colors...** action (top toolbar, or right-click menus on swatches and slot rows) opens a dialog for bulk edits. Every change the dialog makes is bundled into a single `BulkTransformCommand`, so Ctrl+Z reverts the whole batch.

### Modes

- **Replace matching color** — pick a "Match" and a "Replace with" color; every CLUT entry in scope whose *full u16 value* equals "Match" gets rewritten. Matching by u16 means stp=0 and stp=1 variants of the same RGB don't collide (a transparent-sentinel black never gets promoted to opaque black by accident).
- **Shift hue** — slider in degrees (−180°..+180°). Converts each color to HSV, rotates hue, converts back. Wraps cleanly around the hue wheel.
- **Shift brightness / saturation** — sliders in percent. Additive on HSV V/S, clamped to [0, 1].
- **RGB delta** — three sliders in RGB units (−255..+255). Additive per channel, clamped to [0, 255].

All modes preserve the stp bit of each edited color. The PSX transparency sentinel (u16 value `0`) is never touched by any mode — it's a structural marker, not a real color.

### Scope

- **Just this slot** — transforms the 16 colors of the clicked slot.
- **Entire kart** — transforms all slots of the current character (8 × 16 = 128 entries).

Entry points pre-fill the scope and, for Replace mode, the Match color:

- Right-click a **swatch** → dialog opens with scope = this slot, Match = the clicked color.
- Right-click a **slot row** → dialog opens with scope = this slot, no Match prefill.
- Toolbar **Transform Colors...** → dialog opens with scope = entire kart.

You can always switch scope inside the dialog.

### Preview vs Apply

The dialog's inline swatch strip shows before → after for every CLUT entry that *would* change — that updates as you move any control.

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
- Undo works across character switches: edit a color on Crash, switch to Cortex, edit Cortex, Ctrl+Z twice — Cortex's edit reverts first, then Crash's.
- **Imports clear the undo stack.** Opening a `.json` overwrites slots at a lower level than the edit commands know about, so pre-import entries would refer to the wrong base. Cleaner to start fresh.
- **Switching profiles clears the undo stack** — character IDs change, old commands can't replay.

## Import / Export

### Right-Click Targets a Single Character

Right-click any sidebar row:

- **Import Paintjob from JSON...** — applies a `.json` to that character's slots, replacing whatever was there
- **Export Paintjob as JSON...** — saves that character's slots
- **Export Paintjob as Code...** — saves that character's slots as a `.c` + `paintjob.h` pair

Import targets the right-clicked character, not the currently-displayed one.

### Toolbar Batch-Exports What You've Edited

The top toolbar has three actions: **Export All as JSON / Code / Binary**.

- **JSON / Code** — one file per character *that has session edits*. A character you never clicked isn't in the output.
- **Binary** — always writes one 256-byte entry per character *in the profile* (see the caveat below).

### JSON Is Character-Agnostic

The `.paintjob.json` format stores `{slot_name: [16 colors]}`. No character ID, no profile ID, no mesh binding. A paintjob authored on Crash can be imported onto Cortex — any slot names the target character doesn't have are ignored; any the target has that the file doesn't cover fall back to VRAM defaults.

### JSON Colors Preserve the Full u16

Each color is serialized as a 4-digit hex string like `"#7fff"` — the raw PSX 16-bit value, *not* `#RRGGBB`. This matters for round-tripping:

- PSX renders `value == 0` as fully transparent, regardless of the stp bit
- A CLUT entry with RGB `(0, 0, 0)` and stp=1 has `value == 0x8000` and renders as *opaque black*
- The same RGB with stp=0 has `value == 0` and renders as transparent

If colors were stored as 6-digit RGB hex, every opaque black would collapse to transparent on reimport. The u16 format makes the whole round-trip exact.

For backwards compatibility the reader also accepts 6-digit `#RRGGBB` strings (treated as stp=0).

### Exports Include Every Slot

Both JSON and Code exports call `extract_character_as_standalone` with `defaults_by_slot` populated from the current character's VRAM. Result: slots you've *edited* win, slots you haven't touched fall back to the VRAM defaults, and every slot the character knows about lands in the output file. This avoids the foot-gun where a partially-edited paintjob reimports with missing-slot holes.

### Binary Export Zero-Pads Un-edited Characters

The binary format expects `N × 256` bytes for `N` characters in profile order. For characters with no session edits, the exporter currently writes zeroes, not VRAM defaults — so a binary export of "crash only" applied to base CTR would blank out every other character's paintjob.

If you're using the binary format against base CTR, edit every character (even just with Reset → Reset → done per slot to populate them) before running Export as Binary. A proper fix would load every character's VRAM at export time; that's not done yet.

## Schema Migration

Paintjob JSONs carry a `schema_version` field. The reader migrates older versions up to the current schema before parsing, so files authored with an older editor keep working. Newer-than-supported files are rejected with `Paintjob schema_version N is newer than this tool supports — upgrade Paintjob Designer to open this file.`

The migration pipeline is centralized in `SinglePaintjobReader._migrate` — format changes should add a step there rather than forcing users to re-author.

## Drag-and-Drop

Drag a `.json` file onto the main window to apply it to the currently-selected character. Same behaviour as right-click → Import. Other file types (including `.paintjobproject.json` from old versions) are silently ignored to avoid the cryptic "open failed" that an unfiltered handler would produce.

## Packaging Notes

- Built with PyInstaller in the release workflow (`.github/workflows/release.yml`). One-dir bundle, Windows + Linux, zipped as `.7z`.
- Three directories have to be `--add-data`-bundled because they're read at runtime:
  - `config/profiles/` — profile JSONs (`ProfileRegistry` falls back to `sys._MEIPASS`)
  - `paintjob_designer/exporters/templates/` — the `paintjob.h` template written next to each `.c` export
  - `paintjob_designer/gui/widget/shaders/` — the vert/frag GLSL files loaded at module import
- The last two live inside the Python package tree, so `Path(__file__).parent / "..."` resolves in both source and frozen builds without special handling.
- No icon by default. Drop a `.ico` into the packaging step if you want custom taskbar branding.

## Known Limitations

- **One mesh only.** The tool reads `model.meshes[0]` of the character's `.ctr` — the high-LOD body. Wheels and flame/plume effects live outside the character's `.ctr` (wheels are sprite icons from `iconGroup[0]`, flames are separate model IDs) and aren't rendered here.
- **Animation framerates are guessed.** No clip metadata carries an intended FPS; 30 is a preview default.
- **Binary export doesn't backfill un-edited characters.** See [Binary Export Zero-Pads](#binary-export-zero-pads-un-edited-characters).
