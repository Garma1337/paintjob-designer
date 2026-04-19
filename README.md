# Paintjob Designer

A graphical editor for Crash Team Racing character paintjobs (CLUT swaps) with an accurate 3D preview. Build a library of paintjobs, preview each one on any character from your extracted CTR ISO, and export to JSON, C source, or `PAINTALL.bin`.

Paintjobs are character-agnostic — one paintjob is just 8 × 16 PSX colors and can be worn by any character. The profile binds library paintjobs to their in-game home characters and unlockable IDs.

Not tied to any specific CTR mod — works against base CTR (NTSC-U) out of the box and any mod that ships a target profile.

## Features

### Library-first editing

- **Paintjob library sidebar** — the left pane lists every paintjob in the current session. New, Delete, drag-to-reorder. Library position = in-game paintjob index, so reordering matters for `PAINTALL.bin`.
- **Preview character dropdown** — above the 3D viewer, picks which character's mesh + VRAM the editor previews the active paintjob on. Paintjob-to-character is a viewing choice, not a data binding.
- **Per-paintjob CLUT editing** — click any of the 8 × 16 color swatches to open a PSX-quantized color picker; edits snap to the PS1 5-5-5 color grid as you pick.
- **Highlight button per slot** — click the row's **Highlight** button to dim the 3D kart except for the faces that sample that slot. Click again (or another row) to move the highlight.
- **Transform Colors...** — bulk edit with five modes (replace matches, shift hue, shift brightness, shift saturation, RGB delta) scoped to just one slot or the entire kart; Preview button pushes the transform into the 3D view before you commit.
- **Gradient fill** — right-click a slot row → "Gradient fill..." to fill a contiguous index range with a linear gradient between two endpoints (RGB linear or HSV short-arc on the hue wheel).
- **Animation playback** — if the current preview character has animation frames, pick a clip and scrub through them at a configurable FPS.
- **Reset slot** — one-click revert of any slot to the preview character's VRAM defaults.

### 3D preview

- **Orbit camera** — left-drag to rotate, wheel to zoom, **R** to recenter.
- **Eyedropper** — **right-click** any surface on the kart to sample its slot + CLUT index and open the color picker pre-loaded with that color. Works alongside orbit without a mode switch.
- **Full Gouraud + textured shading** — PSX-accurate rendering: untextured faces use their authored per-vertex colors; textured faces modulate by `2 × vertex_color` like the real PS1 GPU (so greyscale texture templates tint correctly).
- **Half-Lambert soft-light** — UV-mapped atlas, live re-upload when you edit a color.

### Profiles

- **Ships with `vanilla-ntsc-u`** (base CTR) and a `saphi` stub.
- **Switch Profile** action on the top toolbar (and File menu).
- **Profile drives everything** downstream: which characters populate the preview dropdown, which CLUT coordinates are read from VRAM, and which paintjob goes where in `PAINTALL.bin`.

### Import / export

- **File → Open Library...** (Ctrl+O) — load every `*.json` under a directory as a `PaintjobLibrary`. Sorted-filename order controls the library index.
- **File → Save Library As...** (Ctrl+Shift+S) — write each paintjob in the library to a directory, named `NN_<slug>.json` so filesystem sort round-trips the ordering.
- **File → Import Paintjob...** — add a single `.json` file to the library (appends to the end).
- **Right-click a paintjob in the sidebar** — Rename, Export as JSON, Export as Code, Replace from JSON, Delete.
- **JSON** stores `{name, author, base_character_id, slots: {slot_name: [16 colors]}}`. No profile / mesh binding — a paintjob authored against Crash can be previewed on Cortex without modification.
- **C source export** produces a plug-and-play `.c` + `paintjob.h` pair, named after the paintjob.
- **`PAINTALL.bin` export** writes the `TexData` struct the vanilla CTR loads at PS1 address `0x801CE000` — three pointer tables + CLUT and RECT payloads, with pre-computed absolute PS1 pointers. Library size must equal `profile.paintjob_slots` length; unauthored slots backfill from each paintjob's home character's VRAM.

### Quality of life

- **Drag-and-drop** — drop a paintjob `.json` onto the window to append it to the library.
- **Transparency-slot indicator** — an orange border on the first color of each row warns that index 0 is the PSX transparency sentinel.

## Requirements

- Python 3.11+
- PySide6
- PyOpenGL
- numpy
- An extracted CTR ISO on disk (you provide this — no copyrighted assets ship with the tool)

## Setup

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1   # Windows PowerShell
# or: source .venv/bin/activate  # Linux/macOS

pip install -r requirements.txt
```

## Usage

```bash
python main.py
```

Or as a module:

```bash
python -m paintjob_designer
```

On first launch, use **File → Load ISO...** to point the tool at the root of your extracted CTR directory (the folder that contains `bigfile/`). The ISO path is remembered across sessions.

## Building an Executable

The GitHub Actions workflow in `.github/workflows/release.yml` builds Windows + Linux one-dir bundles via PyInstaller and publishes them as `.7z` artifacts on manual trigger. To build locally:

```bash
pip install pyinstaller
pyinstaller --noconsole --name PaintjobDesigner \
  --add-data "config/profiles;config/profiles" \
  --add-data "paintjob_designer/exporters/templates;paintjob_designer/exporters/templates" \
  --add-data "paintjob_designer/gui/widget/shaders;paintjob_designer/gui/widget/shaders" \
  main.py
```

(On Linux/macOS replace the `;` separators with `:`.)

The output is in `dist/PaintjobDesigner/`.

## Running Tests

```bash
pytest
```

~300 tests, all headless — no GL context or ISO needed.

## Project Structure

```
config/
    profiles/               Target profile JSONs (vanilla-ntsc-u.json, saphi.json)

paintjob_designer/
    core/                   DI container, binary / bitstream readers
    models/                 Plain-dataclass domain types
                              (PsxColor, Paintjob, PaintjobLibrary, Profile,
                               PaintjobSlotProfile, CtrMesh, ...)
    color/
        converter           PSX15 <-> RGB888 conversion, hex formatting
        transform           Bulk-transform logic (replace / hue / brightness / saturation / RGB delta)
        gradient            Two-endpoint linear gradients in RGB or HSV space
    profile/                ProfileReader + ProfileRegistry (loads bundled
                            profile JSON; parses `paintjob_slots` binding)
    paintjob/               PaintjobReader / PaintjobWriter (.json I/O)
    vram/                   VramReader (.vrm + TIM decode), VramCache
    ctr/                    CtrModelReader (.ctr parsing), VertexAssembler,
                            AnimationDecoder
    render/
        atlas_renderer      VRAM + Paintjob -> RGBA atlas
        psx_rgba_lut        65536-entry u16 -> packed-RGBA LUT
        vram_region_decoder Per-region 4bpp decoder
        slot_region_deriver Groups mesh faces by CLUT into SlotRegions
        atlas_uv_mapper     Byte-space TextureLayout UVs -> normalized atlas UVs
        orbit_camera        Yaw/pitch camera + bbox fit + view/projection matrices
        ray_picker          Möller-Trumbore ray/triangle picker for the eyedropper
    exporters/
        source_code_exporter    .c / paintjob.h pair
        binary_exporter         PAINTALL.bin — N paintjobs × M characters
        templates/              paintjob.h template
    gui/
        main_window.py      Orchestrator
        widget/             KartViewer (GL), SlotEditor, SlotRow,
                            PaintjobLibrarySidebar, ColorSwatch,
                            PsxColorButton, ColorPicker
            shaders/        GLSL vert/frag
        dialog/             ProfilePicker, SourceCodeExportOptions,
                            TransformColors, GradientFill
        handler/            Character / Color / Project handlers
        command/            Undo commands — one class per file
                            (SetSlotColor, ResetSlot, BulkTransform)
    services.py             DI container wiring

.github/
    workflows/release.yml   Windows + Linux build + release workflow
```

## Documentation

- **[User Guide](documentation/user-guide.md)** — Non-obvious behaviors: library semantics, preview character vs home character, PSX transparency sentinel, profile switching, PAINTALL.bin layout, and more.
