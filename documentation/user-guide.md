[<- Back](./README.md)

# User Guide

Things that aren't obvious from the UI. The basics — click a swatch, pick a color — aren't covered here; read on for the advanced details.

## Table of Contents

- [First Launch and ISO Layout](#first-launch-and-iso-layout)
- [Profiles](#profiles)
  - [Switching Profiles Resets the Session](#switching-profiles-resets-the-session)
- [The Three Sidebar Tabs](#the-three-sidebar-tabs)
  - [Per-Tab State](#per-tab-state)
- [Paintjob Library](#paintjob-library)
  - [Library Position Matters](#library-position-matters)
  - [Sidebar Context Menu](#sidebar-context-menu)
  - [Kart vs Hovercraft Paintjobs](#kart-vs-hovercraft-paintjobs)
- [Skin Library](#skin-library)
  - [Sidebar Context Menu](#sidebar-context-menu-1)
  - [Vertex Slots Tab](#vertex-slots-tab)
  - [Vertex Transform Panel](#vertex-transform-panel)
- [Preview Tab](#preview-tab)
- [Preview Character](#preview-character)
- [Slot Editor](#slot-editor)
  - [Top Button Strip](#top-button-strip)
  - [The First Color Is Transparent](#the-first-color-is-transparent)
  - [Highlight Button](#highlight-button)
  - [Reset vs Undo](#reset-vs-undo)
- [3D Preview](#3d-preview)
  - [Orbit Camera Controls](#orbit-camera-controls)
  - [Eyedropper](#eyedropper)
  - [Why Some Faces Can't Be Edited](#why-some-faces-cant-be-edited)
  - [When the 3D View Doesn't Come Up](#when-the-3d-view-doesnt-come-up)
- [Animation Playback](#animation-playback)
- [Color Picker](#color-picker)
- [Color Palettes](#color-palettes)
- [Transform Colors](#transform-colors)
  - [Modes](#modes)
  - [Scope](#scope)
  - [Live Preview and Apply](#live-preview-and-apply)
- [Gradient Fill](#gradient-fill)
- [Texture Import](#texture-import)
  - [Rotate Texture](#rotate-texture)
- [Undo / Redo](#undo--redo)
- [Library I/O](#library-io)
  - [Paintjob Library](#paintjob-library-io)
  - [Skin Library](#skin-library-io)
  - [Drag-and-Drop](#drag-and-drop)

## First Launch and ISO Layout

On first launch the window opens with empty sidebars and the status bar asks you to load an ISO. Use **File → Load ISO...** and point it at the root of your extracted CTR directory — specifically the folder that contains `bigfile/`. If a character's mesh isn't present, previewing that character shows a load-failed message; every other feature still works.

The ISO path is remembered across sessions, so you only have to do this once per machine.

## Profiles

A **profile** tells the editor which game you're authoring for — which characters exist, what their kart-side and skin-side slots are called, and where each slot's CLUT lives in video memory. Two profiles ship in the box:

- **vanilla-ntsc-u** — the original NTSC-U release of CTR.
- **saphi** — the Saphi mod.

Switch between them from **File → Switch Profile...**. To author for a different mod, drop its profile JSON into the editor's `config/profiles/` folder and it'll appear in the picker on next launch.

### Switching Profiles Resets the Session

Confirming a profile switch clears the current paintjob library, skin library, and undo history. Character ids, slot names, and slot lists can all differ between profiles, so carrying over the in-progress work wouldn't be safe. Save the libraries first if it matters.

Your choice is remembered, so the next launch starts on the same profile.

## The Three Sidebar Tabs

The left sidebar has three tabs that share the 3D viewer + slot/vertex editors on the right:

- **Paintjobs** — kart-side recolors. Edits CLUTs that the in-game paintjob system swaps (front, back, motor, exhaust, etc.). Color Palettes are nested at the bottom of this tab — see [Color Palettes](#color-palettes).
- **Skins** — character-bound recolors. Edits the character's own skin-side CLUTs (face, accessories) plus per-vertex gouraud colors (driver body).
- **Preview** — read-only composition view. Pick a character + paintjob + skin and see them all combined.

### Per-Tab State

Each editing tab keeps its own state: which asset is selected and which character is being previewed against it. Switching away and back restores both.

- Switch to a tab for the first time → the first asset auto-selects, and the first compatible preview character is auto-picked + rendered.
- Within a tab, picking a different paintjob/skin keeps the previously-picked preview character if it's still compatible; otherwise falls back to the first compatible one.
- Switching paintjobs to one of a different `kart_type` (kart ↔ hovercraft) repopulates the combo with the new compatible characters.

## Paintjob Library

The Paintjobs tab lists every paintjob in the current session. **New** asks you to pick a base character first — that character's `kart_type` decides whether the paintjob is kart-only or hovercraft-only, and that character's vanilla CLUTs seed every kart slot. **Delete** asks for confirmation before removing the selected paintjob, and clears the undo history at the same time. Rows can be dragged to reorder.

Each paintjob carries:

- **Name** — shown in the sidebar; used as the default filename when exporting.
- **Author** — a credit line, shown in a muted second line under the name in the sidebar when set.
- **Kart type** — `kart` or `hovercraft`. Set at creation time from the base character's vehicle type.
- **Base character** — the character this paintjob conceptually belongs to. The preview falls back to this character's vanilla palette for unedited slots; downstream tools may use it as a "home character" hint.
- **Slot colors and textures** — the 16 colors per kart slot, and optionally imported pixel data for slots that carry custom textures.

### Library Position Matters

The sidebar's top-to-bottom order becomes the library's index order. When you save, each paintjob is written with a numeric prefix (`00_...`, `01_...`) that preserves the order. Downstream tools that consume the library use that index — typically to map library positions to in-game paintjob slots — so reordering the sidebar has real downstream effects.

### Sidebar Context Menu

Right-click a paintjob row for:

- **Rename...** — change the display name. Doesn't reset the preview.
- **Set author...** — change the author credit. Doesn't reset the preview.
- **Change base character...** — change which character this paintjob belongs to.
- **Export as JSON...** — save just that paintjob to a file of your choice.
- **Replace from JSON...** — overwrite the selected paintjob with one loaded from a file. Clears the undo history.
- **Delete** — remove the paintjob after a confirmation. Clears the undo history.

### Kart vs Hovercraft Paintjobs

CTR's roster has standard-kart racers (15 characters in vanilla) and one hovercraft racer (Oxide). Their kart-side CLUTs are structured differently, so paintjobs are scoped to one or the other:

- A **kart** paintjob has 8 slots (`front`, `back`, `floor`, `brown`, `motorside`, `motortop`, `bridge`, `exhaust`) and previews on any standard-kart character.
- A **hovercraft** paintjob has 1 slot (the hover skirt CLUT) and only previews on Oxide.

The preview-character dropdown filters automatically by the active paintjob's kart type, so a hovercraft paintjob never lets you pick Crash and a kart paintjob never lets you pick Oxide.

## Skin Library

The Skins tab lists every skin in the current session. **New** asks you to pick the character to skin — the resulting skin is locked to that character forever (no equivalent of paintjob's character-portability). The character's vanilla skin-side CLUTs seed the skin so it opens looking exactly like the in-game character before any edits.

Each skin carries:

- **Name** — shown in the sidebar; default filename on export.
- **Author** — credit line, shown muted under the name.
- **Bound character** — required, set at creation; can't be changed (unlike paintjob's editable base character).
- **Slot colors and textures** — the 16 colors per skin slot, optional imported pixel data per slot.
- **Vertex overrides** — RGB replacements for entries in the character's gouraud color table. Skin-only feature — paintjobs don't have these.

### Sidebar Context Menu

Right-click a skin row for:

- **Rename...** / **Set author...** — same as paintjobs. Don't reset the preview.
- **Export as JSON...** — save just this skin.
- **Replace from JSON...** — overwrite from a file. Clears undo.
- **Delete** — confirmation prompt. Clears undo.

There's no "Change bound character" — moving a skin between characters would corrupt it (skin slot names key into one specific character's VRAM rects).

### Vertex Slots Tab

When a skin is selected, the right pane shows a second tab labeled **Vertex slots** alongside the regular CLUT slot editor. It's a per-vertex row list — one row per entry in the active character's gouraud color table (`v0`, `v1`, …). Standard racers have 19–64 entries.

Each row carries a swatch + **Highlight** toggle + **Reset** button, mirroring the CLUT slot editor:

- **Click the swatch** — opens an RGB picker. The override is saved on the skin and re-rendered live.
- **Highlight** — dims every kart triangle that doesn't sample this vertex color, so you can see exactly where it lands on the model. Same toggle semantics as the CLUT highlight (only one active at a time).
- **Reset** — drops the override and reverts to the baked color. Disabled when the row isn't currently overridden.
- **Override marker** — overridden rows draw an orange border so you can scan for what you've changed.
- **Right-click the swatch** — context menu with a Reset entry.

Above the list, a button strip exposes **Transform...** (opens the modeless vertex transform panel — see below) and **Reset all** (drops every vertex override on the active skin in one undo step).

The Vertex slots tab is disabled in paintjob mode (paintjobs can't carry vertex overrides) and read-only in preview mode.

### Vertex Transform Panel

The **Transform...** button on the Vertex slots tab opens a modeless panel with the same Apply / Close lifecycle and the same operation pipeline as the CLUT Transform Colors panel — see [Transform Colors](#transform-colors) for the full mode list. Applied to every gouraud vertex color in the character's table.

**Important restriction.** CTR's renderer does texture modulation on textured triangles (`texture × vertex_color × 2`), so changing a vertex color used by a textured face also tints the paintjob's pixels. The panel auto-skips any gouraud index referenced by a textured triangle and reports the count in the intro line ("X of Y colors will be considered..."). Indices used only by untextured (Gouraud-only) triangles are the safe set the panel actually rewrites.

Implementation note: vertex transform round-trips through the PSX 5-bit grid for the HSV math, so an extreme transform may snap colors slightly. For most paintjob-style operations (hue rotation, brightness shift) the snap is invisible.

## Preview Tab

The Preview tab is read-only. It has three combos:

- **Character** — any character from the active profile.
- **Paintjob** — any paintjob whose `kart_type` matches the chosen character. "(none)" leaves kart slots at their vanilla values.
- **Skin** — any skin bound to the chosen character. "(none)" leaves the skin slots and vertex colors at their vanilla values.

The 3D viewer shows the composition: paintjob CLUTs + skin CLUTs + skin vertex overrides, all on the chosen character's mesh. Editing is disabled (the swatch grid and vertex grid are visible but inactive); switch to the Paintjobs or Skins tab to make changes.

The top "Preview on:" strip is hidden in this tab — the sidebar's character combo replaces it.

## Preview Character

The **Preview on:** dropdown above the 3D viewer (visible in the Paintjobs and Skins tabs) picks which character's mesh and palette the editor renders the active asset against.

- In paintjob mode: lists every character whose `kart_type` matches the active paintjob's `kart_type`.
- In skin mode: only the skin's bound character.

Slots you haven't explicitly authored inherit the preview character's original palette, so the 3D view always shows what the game would draw if the active asset were applied to *that* character.

The dropdown remembers the last character you used per tab (paintjob vs skin) and restores it when you come back.

## Slot Editor

Each row shows a slot's 16 colors across the top, with **Highlight** and **Reset** buttons underneath. Clicking a color opens the color picker; changes apply immediately and stream into the 3D preview.

The slot list is filtered by the active editor mode:

- Paintjob mode → only the character's `kart_slots`.
- Skin mode → only the character's `skin_slots`.
- Preview mode → both, but disabled.

Right-click a color for the per-color menu (**Transform colors...** scoped to this slot, pre-filled with the clicked color). Right-click the slot row (outside any color) for the whole-slot menu — **Transform colors...**, **Gradient fill...**, **Apply Color Palette**, and **Import texture...** if the slot is texture-portable.

### Top Button Strip

The slot editor has a button strip above the rows with two whole-asset actions, parallel to the Vertex slots tab:

- **Transform...** — opens the Transform Colors panel scoped to All kart slots / All skin slots, depending on the active mode.
- **Reset all** — reverts every visible slot to the active asset's base/bound character defaults. Bundled into a single undo macro so one Ctrl+Z reverses the whole sweep.

Both buttons are disabled in preview mode and when no asset is selected.

### The First Color Is Transparent

The first color of every row has an **orange border** and a tooltip explaining that this slot is the game's transparency marker. Pixels that land on it render fully transparent regardless of what color you pick, so editing it almost never does what you'd expect. The marker is a warning, not a lock — you can still edit it if you mean to. Any CLUT entry whose 15 colour bits are zero (`#0000` or `#8000`) renders transparent in the live preview, matching the in-game behavior.

### Highlight Button

Each slot row has a checkable **Highlight** button. Clicking it dims every part of the 3D kart that *doesn't* use that slot, so you can see at a glance which surfaces the slot paints. Clicking the same button again clears the highlight; clicking another row's button moves it. Switching paintjobs or preview characters clears the highlight automatically.

### Reset vs Undo

- **Reset button** — replaces every color in that slot with the original palette of the asset's **base/bound character** — *not* the current preview character. This way editing Crash's paintjob while previewing on Cortex still resets to Crash's original palette, which is what you mean by "revert." Ctrl+Z un-resets cleanly.
- **Ctrl+Z** — reverses the most recent edit (color pick, reset, gradient fill, palette apply, or transform), regardless of which paintjob/skin is currently selected. If the reverted edit targets a different asset than the one on screen, the sidebar automatically moves to that asset (and switches tab if needed) so the visible state tracks the change.

The undo history is session-wide and never auto-clears when you switch assets. It does clear when you import or replace a paintjob/skin, delete one, switch profiles, or load a different ISO — in those cases the previous edits can no longer be replayed meaningfully.

## 3D Preview

### Orbit Camera Controls

- **Left-drag** — orbit the camera around the kart.
- **Wheel** — zoom in and out.
- **R** — reset the view (same as **View → Reset Camera**). Reset returns to the framing the editor chose when the character loaded, not a blank world origin.

### Eyedropper

**Alt+Click any surface on the 3D kart** to sample the slot and color under the cursor. The color picker opens pre-loaded with that color so one click + one pick changes the asset. If the click lands on a part of the model that isn't editable in the active mode (wheels, shared driver geometry in paintjob mode, kart slots in skin mode), the status bar says so and no picker opens.

Orbit and zoom still work with left-drag and the wheel regardless — eyedropper is bound to Alt+Click specifically.

### Why Some Faces Can't Be Edited

Character models mix several kinds of surfaces, and the editor mode decides which are interactive:

- **Kart-side CLUT surfaces** — sampled from the kart slots a paintjob edits. Most of the kart body is built this way. Editable in paintjob mode.
- **Skin-side CLUT surfaces** — sampled from skin slots (face, accessories). Editable in skin mode.
- **Gouraud-shaded surfaces** — driver body. Editable via the Vertex slots tab in skin mode.
- **Fixed surfaces** — hard-coded colors baked into the model that no paintjob/skin touches (wheel rims). Reported as "not editable" by the eyedropper.

The editor renders all of them the way the real game does, so the preview matches what the PS1 would draw. CTR ships many textures as greyscale templates that tint at runtime; you'll see them in their final tinted colors in the preview.

### When the 3D View Doesn't Come Up

Some systems can't bring up hardware 3D (old drivers, remote desktop without graphics acceleration, and so on). In that case the 3D pane is replaced with a message telling you so. The slot editor, sidebars, and library saving all stay fully functional — only the live preview is disabled.

## Animation Playback

The Animation panel below the sidebar shows up when the preview character has animation clips baked in. Pick a clip, press Play, and the 3D viewer steps through its frames at the FPS you've set.

**FPS is a preview control, not saved data.** The game doesn't carry an intended framerate; 30 fps is a preview default because it reads well for idle loops. Nothing about the saved asset cares about this value.

A **Loop** checkbox controls end-of-clip behavior. Unchecked (the default), playback stops on the last frame and resets the button to Play; clicking Play again rewinds to the start. Checked, playback wraps back to frame 0 indefinitely.

## Color Picker

Every color you pick is **snapped to the PSX color grid** before being written back: the PS1 supports only a limited palette (32 levels per channel), so the editor rounds your choice to the nearest representable color. What you see in the swatch after picking is exactly what the game will display. The snap is lossy — `#FF7F3A` going in might come back as `#FF7F38`.

The picker also exposes the **alpha** slider for the PSX semi-transparency bit. Alpha < 128 collapses the color to the transparent sentinel.

## Color Palettes

Color Palettes live nested inside the Paintjobs tab as a second list below the paintjob list. They're a workflow aid for paintjobs only — a saved palette is 16 PSX colors you can apply across multiple paintjob slots without re-picking.

- **New** — opens an empty palette in the editor for hand-picking.
- **From Slot** — captures the focused slot's 16 colors into a new palette.
- **Edit** / **Rename** / **Delete** — standard list operations.
- **Apply** — right-click any slot row in paintjob mode → **Apply Color Palette** → pick a saved palette. The palette's colors become that slot's colors as a single undo entry.

Palettes aren't tied to a specific paintjob and persist across sessions in the same config blob the libraries do.

## Transform Colors

The **Transform Colors...** action (the slot editor's top **Transform...** button, or right-click menus on slot rows) opens a **modeless panel** for bulk edits. The panel stays open while you orbit the 3D view, switch assets, or focus different slots — each change updates what the panel is about to touch. Applying a batch lands as a single undo entry, so one Ctrl+Z reverts the whole composition at once.

The vertex editor's **Transform...** button opens the parallel [Vertex Transform Panel](#vertex-transform-panel), which uses the exact same operation pipeline.

Every operation lives in its own section with an enable checkbox. Tick multiple sections and they compose in a **fixed order**:

1. Replace matching color
2. Replace hue
3. Shift hue
4. Shift saturation
5. Shift brightness
6. RGB delta
7. Invert colors

Selective operations (the two Replace modes) run first, so their output is what the later ones see — e.g. swap green to red, then a downstream "shift hue" rotates the whole palette with the swap already baked in. The order isn't configurable; predictable composition beats reordering.

### Modes

- **Replace matching color** — pick a "Match" and a "Replace with" color. Every color in scope that exactly matches the Match color is rewritten.
- **Replace hue** — pick a "From hue" color, a "To hue" color, and a tolerance (0–180°). Every color whose hue is within ±tolerance of the From hue is rotated to the To hue, preserving saturation and brightness. A gradient of greens keeps its relative shading when it lands in the reds. Near-gray pixels are skipped, so whites and grays don't get tinted along with the colors you actually mean to change.
- **Shift hue** — slider in degrees (−180° to +180°). Rotates every color around the color wheel.
- **Shift brightness / saturation** — sliders in percent. Brightens/darkens and adds/removes saturation.
- **RGB delta** — three sliders for red, green, and blue. Adds or subtracts per channel.
- **Invert colors** — flips every channel (`255 − r`, `255 − g`, `255 − b`). Parameter-less; toggle the section to apply. Auto-unchecks itself after Apply so the next batch doesn't double-invert the freshly-baked baseline.

The transparency sentinel (any all-zero CLUT entry) is never touched by any mode — it's a structural marker, not a real color.

### Scope

- **Current slot** — transforms the 16 colors of the focused slot.
- **All kart slots** — every kart-side slot of the active paintjob. Only enabled in paintjob mode.
- **All skin slots** — every skin-side slot of the active skin. Only enabled in skin mode.

The off-mode scope is always disabled — paintjobs can't write to skin slots and vice versa.

How you opened the panel picks the starting scope:

- Right-click a **color** → panel opens scoped to this slot, with Replace matching color pre-filled to the clicked color.
- Right-click a **slot row** → panel opens scoped to this slot.
- Slot editor's **Transform...** button → panel opens scoped to "All kart slots" or "All skin slots" depending on the active tab.

### Live Preview and Apply

Slider, checkbox, and picker changes stream a **live preview** straight into the asset and 3D view. There's no separate "Preview" button; what you see while dialing is the current stack. A summary line at the bottom reports how many colors would actually change.

**Apply** commits the current composition as one undo entry and resets every section's sliders to zero (enable checkboxes stay on, so the next round doesn't require re-ticking the same operations). Closing the panel reverts every pending preview change — nothing uncommitted survives the close.

Even a whole-kart hue shift across 100+ colors lands in a single frame, so the preview feels immediate.

## Gradient Fill

Right-click a slot row → **Gradient fill...** fills a contiguous range of the slot's colors with a linear interpolation between two endpoint colors. Available in both paintjob and skin mode.

- **Color space** — *RGB* interpolates per channel (predictable but can wash out at midpoints; red → blue passes through grey). *HSV* walks the shorter arc around the color wheel, so red → blue goes through magenta instead.
- **From / To index** — which colors to fill. Defaults skip the transparency slot.
- **Endpoints** — both are preserved exactly; intermediate colors are rounded to the PS1 color grid.
- One Ctrl+Z reverts the whole fill.

## Texture Import

Right-click a slot row → **Import texture...** → pick a PNG → the slot's colors and pixels are baked from the image (15 colors + transparent, packed 4bpp). Available for both paintjobs and skins on slots whose VRAM rect dimensions are dim-invariant across characters.

- The dialog refuses slots flagged as `non_portable` in the profile (kart `floor` is the canonical case — different dimensions per character, so an imported image couldn't reuse cleanly across the roster).
- Multi-region slots (slots that occupy multiple disjoint VRAM rectangles) aren't supported yet — the dialog rejects with a clear message.
- A second context-menu entry, **Remove imported texture**, appears when the slot already has imported pixels and drops them while keeping the CLUT colors as-is.

### Rotate Texture

Once a slot has imported pixels, the slot context menu also gains a **Rotate texture** submenu with three options: 90° clockwise, 180°, 270° clockwise. Rotation is lossless (a pure permutation of the 4bpp palette indices).

- **180°** is always available.
- **90° / 270°** are only available when the texture is square (width == height). They swap dimensions, and the slot's VRAM rect is fixed, so non-square 90/270 rotations would no longer fit. The submenu disables them with an explanatory tooltip.

Rotation clears the undo history (commands captured pre-rotate slot refs).

## Undo / Redo

- **Ctrl+Z / Ctrl+Shift+Z** (or Ctrl+Y) — single session-wide history.
- Undo works across asset selections AND across modes: edit paintjob A, switch to skin Y, edit Y, Ctrl+Z twice — Y's edit reverts first, then A's. If the reverted edit targets an asset that isn't currently selected, the sidebar (and tab, if needed) auto-switches.
- **Importing or replacing an asset, deleting an asset, switching profiles, or loading a different ISO** all clear the undo history.

## Library I/O

The editor's outputs are **two library directories** — one for paintjobs, one for skins. Downstream mod-specific tools read each and produce whatever their mod needs. See [paintjob_library_format.md](schema/paintjob_library_format.md) and [skin_library_format.md](schema/skin_library_format.md) for the on-disk formats.

### Paintjob Library

- **File → Export Paintjob Library As...** (Ctrl+Shift+S) writes every paintjob in the library to a chosen directory, using a numeric filename prefix so the order round-trips on the next load.
- **File → Import Paintjobs...** (Ctrl+O) appends one or more paintjob files to the end of the current library.
- Right-click a paintjob → **Export as JSON...** writes just that paintjob to a chosen path. Default filename comes from the paintjob's name.
- Right-click → **Replace from JSON...** overwrites the selected entry from a file.

The Paintjobs sidebar also has dedicated **Export...** and **Delete** buttons.

### Skin Library

- **File → Export Skin Library As...** writes every skin to a chosen directory.
- **File → Import Skins...** appends skin files to the current skin library.
- Right-click a skin → **Export as JSON...** / **Replace from JSON...** — same shape as paintjobs.

The Skins sidebar has the same set of buttons as Paintjobs.

### Drag-and-Drop

Drag a paintjob JSON file onto the main window to append it to the paintjob library (same as **File → Import Paintjobs...**). Drag-drop currently routes everything to the paintjob library — for skins, use the menu or sidebar import.
