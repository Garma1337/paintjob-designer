# CTR Paintjob Designer

A graphical editor for Crash Team Racing **paintjobs** (kart-only CLUT swaps + optional 4bpp textures) and **skins** (per-character recolors that touch the character's own CLUTs *and* gouraud vertex colors), with an accurate 3D preview. Build a library of paintjobs and a library of skins against your extracted CTR ISO and save each as a directory of JSON files — those **two library directories are the designer's only output**.

Downstream mods (e.g. Saphi) own their own tools that consume the libraries and produce mod-specific artifacts (source files, binaries, linker scripts). The designer is just a front-end for the visual creation of paintjobs and skins; each mod owns the integration.

# Features

## Three sidebar tabs

The left sidebar has three tabs that share the 3D viewer + slot editor on the right:

- **Paintjobs** — kart-slot CLUTs (front, back, motor, exhaust, etc.) and optional 4bpp textures. Paintjobs are kart-only and portable across every character of the same kart type (kart vs hovercraft). Color Palettes are nested under this tab.
- **Skins** — character-bound recolors. Edits the character's own skin-slot CLUTs and the gouraud vertex colors that drive the driver body. A skin only previews on its bound character.
- **Preview** — pick any character + any compatible paintjob + any compatible skin and see them composed together. Read-only.

Each editing tab keeps its own state (selected asset, last-viewed character) so switching back and forth restores what you were looking at.

## Library-first editing

- **Per-slot CLUT editing** — click any of the 16 color swatches to open a PSX-quantized color picker; edits snap to the PS1 5-5-5 color grid as you pick.
- **Vertex-color editing** (skins only) — the right pane has a Vertex Slots tab listing every entry in the character's gouraud-color table. Clicking a swatch opens an RGB picker; the override is saved on the skin and re-rendered live.
- **Texture import** — replace a slot's pixels with a PNG. Quantized to 15 colors + transparent, packed 4bpp, baked into the asset's JSON. Available for both paintjobs and skins on slots whose VRAM rect is dim-invariant across characters.
- **Transform Colors panel** — modeless panel with six stackable modes (replace matching color, replace hue, shift hue, shift saturation, shift brightness, RGB delta). Three scopes: Current slot / All kart slots / All skin slots — only the scope matching the active asset's kind is enabled. Slider changes stream into the 3D view live; Apply commits the full stack as a single undo entry.
- **Vertex transform dialog** — the same operation pipeline applied to a skin's gouraud vertex colors as a one-shot batch.
- **Color Palettes** — save the 16 colors of a focused slot as a reusable palette and apply it to other slots later. Lives in the Paintjobs tab.

## 3D preview

- **Orbit camera** — left-drag to rotate, wheel to zoom, **R** to recenter.
- **Eyedropper** — Alt+click any surface on the kart to sample its slot + CLUT index and open the color picker pre-loaded with that color.
- **PSX-accurate shading** — untextured faces use per-vertex Gouraud colors; textured faces modulate by `2 × vertex_color` like the real PS1 GPU, so greyscale texture templates tint correctly. Black pixels (`#0000`) render fully transparent — matching the in-game behavior of the PSX transparency sentinel.

## Profiles

Ships with `vanilla-ntsc-u` (base CTR) and `saphi`. The profile drives which characters populate the preview dropdowns, which CLUTs belong to the kart vs the skin side, and which slots are flagged as non-portable (e.g. `floor`). Switch Profile from the File menu.

See [documentation/paintjob_library_format.md](documentation/paintjob_library_format.md) and [documentation/skin_library_format.md](documentation/skin_library_format.md) for the on-disk JSON schemas consumer tools read, and [documentation/user-guide.md](documentation/user-guide.md) for everything else.

# Requirements

Make sure you have the following set up before running the Paintjob Designer:

- [Python](https://www.python.org/downloads/) 3.11+ installed
- An extracted vanilla CTR ISO on disk (no copyrighted assets ship with the tool)

If you are not using the portable version of the installer, the following Python libraries will be installed when running the `run.bat` / `run.sh`:

- PySide6
- PyOpenGL
- numpy
- pydantic

# Documentation

See the [documentation overview](./documentation/README.md).
