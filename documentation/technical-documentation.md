[<- Back](./README.md)

# Project Structure

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

# Environment Setup

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1   # Windows PowerShell
# or: source .venv/bin/activate  # Linux/macOS

pip install -r requirements.txt
```

# Building an Executable

The GitHub Actions workflow in `.github/workflows/release.yml` builds Windows + Linux one-dir bundles via PyInstaller and publishes them as `.7z` artifacts on manual trigger. To build locally:

```bash
pyinstaller PaintjobDesigner.spec
```

The spec file lives at the repo root; it handles icon, data-file bundling, and the PySide6 submodule exclusions that keep the bundle small. Output lands in `dist/PaintjobDesigner/`.

# Running Tests

```bash
pytest
```

~350 tests, all headless — no GL context or ISO needed.
