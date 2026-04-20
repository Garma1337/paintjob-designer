# Paintjob Designer

A graphical editor for Crash Team Racing character paintjobs (CLUT swaps + optional custom 4bpp textures) with an accurate 3D preview. Build a library of paintjobs against your extracted CTR ISO and save it as a directory of JSON files — the **library directory is the designer's only output**.

Downstream mods (e.g. Saphi) own their own tools that consume the library and produce mod-specific artifacts (source files, binaries, linker scripts). The designer is just a front-end for the visual creation of paintjobs; each mod owns the integration.

## Features

### Library-first editing

- **Per-paintjob CLUT editing** — click any of the 8 × 16 color swatches to open a PSX-quantized color picker; edits snap to the PS1 5-5-5 color grid as you pick.
- **Texture import** — replace a slot's pixels with a PNG. The image is quantized to 15 colors + transparent, packed 4bpp, and baked into the paintjob JSON alongside the CLUT. Imported textures stay portable across every character (except `floor`, whose VRAM rect size varies).
- **Transform Colors panel** — modeless panel with six stackable modes (replace matching color, replace hue, shift hue, shift saturation, shift brightness, RGB delta) scoped to one slot or the entire kart. Slider changes stream into the 3D view live; Apply commits the full stack as a single undo entry.
- **Preview character dropdown** — picks which character's mesh + VRAM the editor previews the active paintjob on. Paintjob-to-character is a viewing choice, not a data binding.

### 3D preview

- **Orbit camera** — left-drag to rotate, wheel to zoom, **R** to recenter.
- **Eyedropper** — right-click any surface on the kart to sample its slot + CLUT index and open the color picker pre-loaded with that color.
- **PSX-accurate shading** — untextured faces use per-vertex Gouraud colors; textured faces modulate by `2 × vertex_color` like the real PS1 GPU, so greyscale texture templates tint correctly.

### Profiles

Ships with `vanilla-ntsc-u` (base CTR) and `saphi`. The profile drives which characters populate the preview dropdown and which CLUT coordinates are read from VRAM. Switch Profile from the toolbar or File menu.

### Library I/O

- **File → Open Library...** (Ctrl+O) — load every `*.json` under a directory as a `PaintjobLibrary`.
- **File → Save Library As...** (Ctrl+Shift+S) — write each paintjob to a directory as `NN_<slug>.json` so filesystem sort round-trips the ordering. **This is the designer's primary output.**
- **Right-click a paintjob** in the sidebar for rename, set author, change base character, single-paintjob export, replace, and delete.

See [documentation/library_format.md](documentation/library_format.md) for the on-disk JSON schema consumer tools read, and [documentation/user-guide.md](documentation/user-guide.md) for everything else.

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
  --icon app.ico \
  --add-data "config/profiles;config/profiles" \
  --add-data "app.ico;." \
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
    models/                 Pydantic v2 BaseModels with a committed JSON Schema
                              (PsxColor, Paintjob, PaintjobLibrary,
                               SlotColors, SlotRegionPixels, Profile,
                               PaintjobSlotProfile, CtrMesh, ...)
    color/
        converter           PSX15 <-> RGB888 conversion, hex formatting
        transform           Bulk-transform logic (replace matches / replace hue / shift hue / saturation / brightness / RGB delta)
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
    texture/
        quantizer               PIL RGBA -> PSX 4bpp + 16-color CLUT
        importer                PNG file + resize policy -> QuantizedTexture
    gui/
        main_window.py      Orchestrator
        widget/             KartViewer (GL), SlotEditor, SlotRow,
                            PaintjobLibrarySidebar, ColorSwatch,
                            PsxColorButton, ColorPicker,
                            TransformColorsPanel (modeless stacked-ops panel)
            shaders/        GLSL vert/frag
        dialog/             ProfilePicker, GradientFill, TextureImport
        handler/            Character / Color / Project handlers
        command/            Undo commands — one class per file
                            (SetSlotColor, ResetSlot, BulkTransform)
    services.py             DI container wiring

schema/
    library.json            Pydantic-generated JSON Schema for the library format
                            (drift-checked by tests/paintjob/test_schema.py)

.github/
    workflows/release.yml   Windows + Linux build + release workflow
```

## Documentation

- **[Library Format](documentation/library_format.md)** — JSON schema of the paintjob library directory. Authoritative contract for downstream consumer tools.
- **[User Guide](documentation/user-guide.md)** — Non-obvious behaviors: library semantics, preview character, PSX transparency sentinel, profile switching, and more.
