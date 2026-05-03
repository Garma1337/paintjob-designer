# CTR Paintjob Designer

A graphical editor for Crash Team Racing **paintjobs** (kart-only CLUT swaps + optional 4bpp textures) and **skins** (per-character recolors that touch the character's own CLUTs *and* gouraud vertex colors), with an accurate 3D preview. Build a library of paintjobs and a library of skins against your extracted CTR ISO and save each as a directory of JSON files — those **two library directories are the designer's only output**.

Downstream mods (e.g. Saphi) own their own tools that consume the libraries and produce mod-specific artifacts (source files, binaries, linker scripts). The designer is just a front-end for the visual creation of paintjobs and skins; each mod owns the integration.

# Features

## Paintjob & skin authoring

- **Paintjobs** — author kart-side CLUT swaps and optional 4bpp textures. Kart-only and portable across every character of the same kart type (standard kart vs hovercraft).
- **Skins** — author character-bound recolors that touch the character's own skin-side CLUTs and the gouraud vertex colors driving the driver body.
- **Composed preview** — combine any character with a compatible paintjob and a compatible skin to see how they look together.

## Editing

- **Per-slot CLUT editing** — pick any of a slot's 16 colors through a PSX-quantized color picker; edits snap to the PS1 5-5-5 color grid as you pick.
- **Orphan slots** — surfaces CLUTs that wouldn't otherwise be reachable: profile slots whose VRAM coord isn't sampled by any mesh triangle (menu screens, particles, etc.) and mesh-sampled CLUTs the profile doesn't categorize (under a synthesized `unmatched@x,y` name). Both flavors are editable.
- **Vertex-color editing** (skins only) — every entry in the character's gouraud-color table is editable; the override is saved on the skin and re-rendered live.
- **Texture import / export** — replace a slot's pixels with a PNG (quantized to 15 colors + transparent, packed 4bpp, baked into the asset JSON), or export the slot's current pixels back to PNG for round-tripping through an external editor. Both single-region and multi-region slots are supported.
- **Transform Colors** — seven stackable color operations (replace matching color, replace hue, shift hue, shift saturation, shift brightness, RGB delta, invert), scoped to the current slot or to every kart/skin slot at once. Changes stream into the 3D view live; the full stack commits as a single undo entry.
- **Vertex transform** — the same color operations applied to a skin's gouraud vertex colors, auto-restricted to vertex indices used only by untextured triangles so `texture × vertex_color` modulation can't tint paintjob surfaces.
- **Color Palettes** — save the 16 colors of a slot as a reusable palette, build one from a quantized PNG, or hand-pick one. Apply to other slots later.
- **Library filter** — narrow the visible paintjobs, skins, or palettes by name.

## 3D preview

- **Orbit camera** — left-drag to rotate, wheel to zoom, **R** to recenter.
- **Eyedropper** — Alt+click any surface on the kart to sample its slot + CLUT index and open the color picker pre-loaded with that color.
- **PSX-accurate shading** — untextured faces use per-vertex Gouraud colors; textured faces modulate by `2 × vertex_color` like the real PS1 GPU, so greyscale texture templates tint correctly. Black pixels (`#0000`) render fully transparent — matching the in-game behavior of the PSX transparency sentinel.
- **PSX semi-transparent blend modes** — the viewer reads each triangle's blend mode (Standard / Add / Subtract / Multiply) and renders semi-transparent surfaces (visors, glass, glows) in separate passes with the correct GPU blend equation, instead of drawing them all opaque.

## Profiles

Ships with `vanilla-ntsc-u` (base CTR) and `saphi`. The profile drives which characters are available, which CLUTs belong to the kart vs the skin side, and which slots are flagged as non-portable (e.g. `floor`).

See [documentation/paintjob_library_format.md](documentation/schema/paintjob_library_format.md) and [documentation/skin_library_format.md](documentation/schema/skin_library_format.md) for the on-disk JSON schemas consumer tools read, and [documentation/user-guide.md](documentation/user-guide.md) for everything else.

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
