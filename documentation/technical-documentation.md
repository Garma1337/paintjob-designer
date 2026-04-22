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

run.bat                     Windows launcher — creates `.venv`, installs requirements, runs `main.py`
run.sh                      Linux launcher — equivalent for POSIX shells
```

# Environment Setup

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1   # Windows PowerShell
source .venv/bin/activate    # Linux/macOS

pip install -r requirements.txt
```

# Release Artifacts

The GitHub Actions workflow in `.github/workflows/release.yml` is manually triggered and produces three `.7z` archives:

- `PaintjobDesigner-windows-portable.7z` — standalone PyInstaller one-dir bundle for Windows. No Python install required. Built on a Windows runner via `pyinstaller PaintjobDesigner.spec`.
- `PaintjobDesigner-windows-source.7z` — repo sources + `run.bat`. Requires a system Python. On first run, `run.bat` creates a local `.venv`, installs `requirements.txt` into it, and then launches `main.py` through the venv interpreter.
- `PaintjobDesigner-linux-source.7z` — repo sources + `run.sh`. POSIX equivalent of the Windows source package.

Only the portable Windows build uses PyInstaller; the two source packages are produced from a single Ubuntu job that copies the repo tree, strips the wrong-platform launcher, and invokes `7z`. This is what keeps build time + artifact size down compared to shipping a PyInstaller bundle for every platform.

## Building the portable installer locally

```bash
pyinstaller PaintjobDesigner.spec
```

The spec file lives at the repo root; it handles icon, data-file bundling, and the PySide6 submodule exclusions that keep the bundle small. Output lands in `dist/PaintjobDesigner/`.

# Running Tests

```bash
pytest
```

~350 tests, all headless — no GL context or ISO needed.
