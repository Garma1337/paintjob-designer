# CTR Paintjob Designer

A graphical editor for Crash Team Racing character paintjobs (CLUT swaps + optional custom 4bpp textures) with an accurate 3D preview. Build a library of paintjobs against your extracted CTR ISO and save it as a directory of JSON files — the **library directory is the designer's only output**.

Downstream mods (e.g. Saphi) own their own tools that consume the library and produce mod-specific artifacts (source files, binaries, linker scripts). The designer is just a front-end for the visual creation of paintjobs; each mod owns the integration.

# Features

## Library-first editing

- **Per-paintjob CLUT editing** — click any of the 8 × 16 color swatches to open a PSX-quantized color picker; edits snap to the PS1 5-5-5 color grid as you pick.
- **Texture import** — replace a slot's pixels with a PNG. The image is quantized to 15 colors + transparent, packed 4bpp, and baked into the paintjob JSON alongside the CLUT. Imported textures stay portable across every character (except `floor`, whose VRAM rect size varies).
- **Transform Colors panel** — modeless panel with six stackable modes (replace matching color, replace hue, shift hue, shift saturation, shift brightness, RGB delta) scoped to one slot or the entire kart. Slider changes stream into the 3D view live; Apply commits the full stack as a single undo entry.
- **Preview character dropdown** — picks which character's mesh + VRAM the editor previews the active paintjob on. Paintjob-to-character is a viewing choice, not a data binding.

## 3D preview

- **Orbit camera** — left-drag to rotate, wheel to zoom, **R** to recenter.
- **Eyedropper** — right-click any surface on the kart to sample its slot + CLUT index and open the color picker pre-loaded with that color.
- **PSX-accurate shading** — untextured faces use per-vertex Gouraud colors; textured faces modulate by `2 × vertex_color` like the real PS1 GPU, so greyscale texture templates tint correctly.

## Profiles

Ships with `vanilla-ntsc-u` (base CTR) and `saphi`. The profile drives which characters populate the preview dropdown and which CLUT coordinates are read from VRAM. Switch Profile from the toolbar or File menu.

## Library I/O

- **File → Open Library...** (Ctrl+O) — load every `*.json` under a directory as a `PaintjobLibrary`.
- **File → Save Library As...** (Ctrl+Shift+S) — write each paintjob to a directory as `NN_<slug>.json` so filesystem sort round-trips the ordering. **This is the designer's primary output.**
- **Right-click a paintjob** in the sidebar for rename, set author, change base character, single-paintjob export, replace, and delete.

See [documentation/library_format.md](documentation/library_format.md) for the on-disk JSON schema consumer tools read, and [documentation/user-guide.md](documentation/user-guide.md) for everything else.

# Requirements

- Python 3.11+
- PySide6
- PyOpenGL
- numpy
- An extracted CTR ISO on disk (you provide this — no copyrighted assets ship with the tool)


# Documentation

See the [documentation overview](./documentation/README.md).