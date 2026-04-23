[<- Back](./README.md)

# Project Structure

```
config/
    profiles/                       Target profile JSONs (vanilla-ntsc-u.json,
                                    saphi.json) — schema v2 splits each
                                    character's slots into kart_slots /
                                    skin_slots and tags slots non_portable

paintjob_designer/
    core/                           DI container, binary / bitstream readers,
                                    Slugifier
    models/                         Pydantic v2 BaseModels
                                      paintjob.py    Paintjob, PaintjobLibrary,
                                                     SlotColors, SlotRegionPixels,
                                                     KartType, KART_SLOT_NAMES
                                      skin.py        Skin, SkinLibrary
                                      profile.py     Profile, CharacterProfile,
                                                     SlotProfile, ClutCoord
                                      color.py       PsxColor, Rgb888
                                      palette.py     Palette, PaletteLibrary
                                      ctr_mesh.py    CtrMesh, GouraudColor,
                                                     TextureLayout, anim types
                                      vram_page.py   VramPage container
                                      slot_regions.py CharacterSlotRegions, ...

    color/
        converter                   PSX15 <-> RGB888 conversion, hex formatting
        transform                   Bulk-transform pipeline (replace matches,
                                    replace hue, shift hue/sat/brightness, RGB delta)
        gradient                    Two-endpoint linear gradients in RGB or HSV space

    profile/                        ProfileReader + ProfileRegistry
    paintjob/                       PaintjobReader / PaintjobWriter (.json I/O)
    skin/                           SkinReader / SkinWriter (.json I/O)
    vram/                           VramReader (.vrm + TIM decode), VramCache
    ctr/                            CtrModelReader (.ctr parsing), VertexAssembler,
                                    AnimationDecoder

    render/
        atlas_renderer              VRAM + asset -> RGBA atlas
        psx_rgba_lut                65536-entry u16 -> packed-RGBA LUT
                                    (15-bit-zero entries -> alpha 0)
        vram_region_decoder         Per-region 4bpp decoder
        slot_region_deriver         Groups mesh faces by CLUT into SlotRegions
        atlas_uv_mapper             Byte-space TextureLayout UVs -> normalized
                                    atlas UVs
        orbit_camera                Yaw/pitch camera + bbox fit + view matrices
        ray_picker                  Möller-Trumbore ray/triangle picker
                                    (eyedropper)

    texture/
        quantizer                   PIL RGBA -> PSX 4bpp + 16-color CLUT
        importer                    PNG file + resize policy -> QuantizedTexture

    gui/
        main_window.py              Top-level window. Owns the editor surface
                                    and orchestrates the controllers.

        controller/
            library_controller.py   Generic LibraryController[TItem, TLibrary]
                                    base. Owns the shared signals
                                    (selection_changed / library_changed /
                                    mutated / library_reset) and the shared
                                    delete-with-confirm + selection plumbing.
            paintjob_library_controller.py
                                    PaintjobLibraryController. CRUD + dialogs
                                    + per-asset slot seeding.
            skin_library_controller.py
                                    SkinLibraryController. Same shape, skin
                                    slots only, character-bound.
            palette_library_controller.py
                                    PaletteLibraryController. New / edit /
                                    rename / apply.
            character_picker.py     CharacterPicker — wraps PickCharacterDialog;
                                    used by paintjob + skin "new" flows.
            profile_holder.py       ProfileHolder — mutable cell carrying the
                                    active Profile, plus display_name_for(id)
                                    used by sidebars to render character names.
            animation_controller.py AnimationController — owns the animation
                                    panel widget + per-frame playback timer.
            transform_panel_coordinator.py
                                    TransformPanelCoordinator — owns the
                                    Transform Colors panel + the snapshot /
                                    preview / commit / restore lifecycle.
                                    Operates on the active asset (paintjob OR
                                    skin) via duck-typed `.slots[name]` access.

        widget/
            kart_viewer.py          KartViewer (GL) + NullKartViewer (fallback
                                    when GL init fails)
            slot_editor.py          SlotEditor — grid of SlotRow widgets
            slot_row.py             SlotRow — 16 swatches + Highlight + Reset
            color_swatch.py         ColorSwatch — single 5-5-5 PSX color cell
            psx_color_button.py     PsxColorButton — labeled swatch + picker
            color_picker.py         PsxColorPicker (alpha-aware)
            vertex_slot_editor.py   VertexSlotEditor — per-gouraud-index
                                    swatch grid, skin-only
            transform_panel.py      TransformColorsPanel + TransformCandidate
            preview_sidebar.py      PreviewSidebar — character/paintjob/skin
                                    composition combos
            library_sidebar.py      LibrarySidebar base + LibraryRowDelegate.
                                    Owns the list + button row + selection
                                    plumbing for paintjob/skin sidebars.
            paintjob_library_sidebar.py
                                    PaintjobLibrarySidebar (drag-reorder,
                                    context menu, "(textured)" marker).
            skin_library_sidebar.py SkinLibrarySidebar (parallel; no reorder).
            palette_sidebar.py      PaletteSidebar (lives nested in the
                                    Paintjobs tab).
            shaders/                GLSL vert/frag

        dialog/
            pick_character_dialog.py    Modal character picker
            profile_picker_dialog.py    Modal profile switcher
            palette_edit_dialog.py      Edit palette colors
            palette_apply_dialog.py     Map palette → slot indices on apply
            gradient_fill_dialog.py     Two-endpoint gradient builder
            vertex_transform_dialog.py  Bulk vertex-color transform (skins)

        handler/
            character_handler.py    Character bring-up: .ctr parse + VRAM load
                                    + slot derivation + atlas render
            color_handler.py        Per-slot CLUT mutation + atlas patch
            project_handler.py      Paintjob load/save (single + library)

        command/
            undo_command_base.py    UndoCommandBase — handles the shared
                                    "first redo is a no-op" pattern
            set_slot_color_command.py
            reset_slot_command.py
            bulk_transform_command.py
                                    All three subclass UndoCommandBase.
                                    BulkTransformCommand serves both
                                    Transform Colors AND Apply Palette.

        util/
            dialogs.py              MessageDialog (info/warn/error/confirm),
                                    FilePicker (open/save/dir),
                                    InputPrompt (get_text/get_item).
                                    Three single-responsibility wrappers
                                    around QMessageBox / QFileDialog /
                                    QInputDialog so callers can be tested.
            library_writer.py       LibraryWriter — directory-of-JSONs writer
                                    used by both paintjob and skin save flows

    services.py                     DI container wiring

schema/
    paintjobs_library_schema.json   Pydantic-generated JSON Schema for the
                                    paintjob library format
    skins_library_schema.json       Pydantic-generated JSON Schema for the
                                    skin library format
                                    Both regenerated by tools/dump_schema.py;
                                    drift-checked by tests/{paintjob,skin}/
                                    test_schema.py.

tests/
    gui/
        controller/                 LibraryController + the three subclasses
                                    + dialog-fake fixtures
        command/                    Undo command behavior + UndoCommandBase
        handler/                    CharacterHandler / ColorHandler / ProjectHandler
        util/                       LibraryWriter
    color/                          ColorConverter / ColorTransformer / GradientGenerator
    config/                         IsoRootValidator / ConfigStore
    core/                           Container / Slugifier / readers
    ctr/                            CtrModelReader / VertexAssembler / AnimationDecoder
    paintjob/                       Reader / Writer / schema drift
    skin/                           Reader / Writer / library / schema drift
    profile/                        Reader / Registry
    render/                         Atlas / camera / ray-picker / decoders
    texture/                        Quantizer / Importer
    vram/                           Reader / Cache
    models/                         Color / mesh / paintjob / palette / skin /
                                    slot_regions / vram_page

.github/
    workflows/release.yml           Windows + Linux build + release workflow

launcher/
    run.bat                         Windows launcher — creates `.venv`,
                                    installs requirements, runs `main.py`
    run.sh                          Linux launcher — equivalent for POSIX
                                    (workflow copies these to the archive
                                    root on release)

tools/
    dump_schema.py                  Regenerate the JSON Schema files from
                                    the pydantic models. Targets a list of
                                    (model, filename) pairs — currently
                                    Paintjob and Skin.
    inspect_clut_palette.py         CLI: dump per-CLUT palette strips and
                                    decoded region samples for any racer's
                                    .ctr — used when adding new profile
                                    entries.
```

# Architecture Overview

## Single editor + three tabs

The right pane (3D viewer + slot editor + vertex editor tabs) is shared across the three sidebar tabs. Editor mode (`paintjob` / `skin` / `preview`) is set by the active sidebar tab; mode drives:

- Which controller's signals feed the right pane (`paintjob_library_controller` vs `skin_library_controller`).
- Which slot subset the slot editor shows (`character.kart_slots` vs `character.skin_slots`).
- Whether the vertex editor is editable (skin-only) or read-only.
- Which scope the Transform Colors panel exposes (kart / skin / current — off-mode is disabled).
- Whether the right pane responds to writes at all (preview mode is read-only).

## Per-tab state

Asset selection (which paintjob, which skin) is preserved per-controller across tab switches. Preview character is preserved per-mode in `MainWindow._remembered_character_id: dict[str, str]`. Switching tabs restores both — see `_on_sidebar_tab_changed`.

## Asset duck-typing

`Paintjob` and `Skin` both expose a `.slots: dict[str, SlotColors]`. Every commit path operates on a generic "asset" reference (`BulkColorEdit.asset`, `SetSlotColorCommand._asset`, etc.) and lets the underlying handlers duck-type on `.slots[name]`. This keeps one undo / commit pipeline serving both libraries.

## Strict separation

Paintjobs only touch kart slots; skins only touch skin slots. Enforced at:

- Asset creation (controller's `_seed_slots` only iterates the matching slot list).
- Slot editor population (`_active_slot_names` filters by mode).
- Transform Colors panel (off-mode scope is empty → disabled in the combo).
- Slot context menu (preview mode = no menu).

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

431 tests, all headless — no GL context or ISO needed. Controller tests pull in a session-scoped `qapp` fixture from `tests/conftest.py` so the Qt-widget side compiles, but no event loop runs.

# Regenerating Schemas

When you change a model in `paintjob_designer/models/`, regenerate the committed JSON schemas so consumer tools see the new shape:

```bash
python tools/dump_schema.py
```

This writes `schema/paintjobs_library_schema.json` and `schema/skins_library_schema.json`. The matching tests in `tests/paintjob/test_schema.py` and `tests/skin/test_schema.py` will fail in CI if you forget.
