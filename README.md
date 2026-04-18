# Paintjob Designer

A graphical editor for Crash Team Racing character paintjobs (CLUT swaps) with an accurate 3D preview. Pick a character from your extracted CTR ISO, recolor their eight palette slots, and export to JSON, C source, or a binary CLUT dump.

Not tied to any specific CTR mod — works against base CTR (NTSC-U) out of the box and any mod that ships a target profile.

## Features

### Editing

- **Per-character CLUT editing** — click any of the 8 × 16 color swatches to open a PSX-quantized color picker; edits snap to the PS1 5-5-5 color grid as you pick
- **Hover-to-highlight** — clicking a slot row dims the 3D kart except for the faces that sample that slot, so you always know what a color change will actually affect
- **Animation playback** — if the loaded kart has animation frames, pick a clip and scrub through them at a configurable FPS to see how the paintjob looks across the full motion range
- **Undo / redo** — one session-wide stack that spans character switches (Ctrl+Z / Ctrl+Shift+Z)
- **Reset slot** — one-click revert of any slot to the vanilla VRAM colors

### 3D preview

- **Orbit camera** — left-drag to rotate, wheel to zoom, **R** to recenter
- **Flat-shaded textured kart** — half-Lambert shading, UV-mapped atlas, live re-upload when you edit a color
- **Incremental atlas updates** — only the edited slot's VRAM region is re-uploaded on each pick, not the full 4096×512 atlas
- **Graceful GL fallback** — if OpenGL 3.3 isn't available, the 3D pane is replaced with a placeholder and the rest of the editor keeps working

### Profiles

- **Ships with `vanilla-ntsc-u`** (base CTR) and a `saphi` stub
- **Switch Profile** action on the top toolbar (and File menu)
- **Profile drives everything** downstream: which characters appear in the sidebar, which CLUT coordinates are read, and how the binary export orders its entries
- **Active profile is always visible** in the window title and status bar

### Import / export

- **Right-click a character** → Import Paintjob from JSON, Export as JSON, Export as Code (.c)
- **Top toolbar** → Export All as JSON / Code / Binary (batch over every character the session has touched)
- **JSON** is character-agnostic — just slot names × 16 colors — so a paintjob designed for one character can be imported onto another
- **C source export** produces a plug-and-play `.c` + `paintjob.h` pair
- **Binary export** emits a `N × 256-byte` CLUT dump in profile character order, suitable for base-CTR patchers with fixed offsets

### Quality of life

- **Drag-and-drop** — drop a paintjob `.json` onto the window to apply it to the currently-selected character
- **Transparency-slot indicator** — an orange border on the first color of each row warns that index 0 is the PSX transparency sentinel
- **Schema migration** — older paintjob files keep loading as the format evolves; newer-than-supported files are rejected with a clear message
- **Round-trip safety** — colors roundtrip as the full PSX u16 (including the stp bit), so black opaque samples don't collapse to transparent on reimport

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

~240 tests, all headless — no GL context or ISO needed.

## Project Structure

```
config/
    profiles/               Target profile JSONs (vanilla-ntsc-u.json, saphi.json)

paintjob_designer/
    core/                   DI container, binary / bitstream readers
    models/                 Plain-dataclass domain types (PsxColor, CtrMesh, Paintjob, Profile, ...)
    color/                  PSX15 <-> RGB888 conversion, hex formatting
    profile/                ProfileReader + ProfileRegistry (loads bundled profile JSON)
    paintjob/               SinglePaintjobReader / Writer (.json import/export with schema migration)
    vram/                   VramReader (.vrm + TIM decode), VramCache
    ctr/                    CtrModelReader (.ctr parsing), VertexAssembler, AnimationDecoder
    render/
        atlas_renderer      VRAM + Paintjob -> RGBA atlas
        psx_rgba_lut        65536-entry u16 -> packed-RGBA LUT
        vram_region_decoder Per-region 4bpp decoder
        slot_region_deriver Groups mesh faces by CLUT into SlotRegions
        atlas_uv_mapper     Byte-space TextureLayout UVs -> normalized atlas UVs
        orbit_camera        Yaw/pitch camera + bbox fit + view/projection matrices
    exporters/
        source_code_exporter    .c / paintjob.h pair
        binary_exporter         Flat CLUT blob
        templates/              paintjob.h template
    gui/
        main_window.py      Orchestrator
        widget/             KartViewer (GL), SlotEditor, SlotRow, CharacterSidebar, ColorSwatch, ColorPicker
            shaders/        GLSL vert/frag
        dialog/             ProfilePicker, SourceCodeExportOptions
        handler/            Character / Color / Project handlers
        command/            Undo commands (SetSlotColor, ResetSlot)
    services.py             DI container wiring

.github/
    workflows/release.yml   Windows + Linux build + release workflow
```

## Documentation

- **[User Guide](documentation/user-guide.md)** — Non-obvious behaviors: transparency sentinel, profile switching, import scope, atlas roundtrip, highlight toggling, animation framerate, export scope, VRAM cache, batch export conventions, PyInstaller data bundling
