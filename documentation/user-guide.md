# User Guide

Things that aren't obvious from the UI. The basics — click a swatch, pick a color — aren't covered here; read on for the gotchas.

## Table of Contents

- [First Launch and ISO Layout](#first-launch-and-iso-layout)
- [Profiles](#profiles)
  - [Switching Profiles Resets the Session](#switching-profiles-resets-the-session)
- [Paintjob Library](#paintjob-library)
  - [Library Position Matters](#library-position-matters)
  - [Sidebar Context Menu](#sidebar-context-menu)
- [Preview Character](#preview-character)
  - [Home Character vs Preview Character](#home-character-vs-preview-character)
  - [Textured Paintjobs Stay Character-Agnostic](#textured-paintjobs-stay-character-agnostic)
- [Slot Editor](#slot-editor)
  - [The First Color Is Transparent](#the-first-color-is-transparent)
  - [Highlight Button](#highlight-button)
  - [Reset vs Undo](#reset-vs-undo)
- [3D Preview](#3d-preview)
  - [Orbit Camera Controls](#orbit-camera-controls)
  - [Eyedropper (Right-Click)](#eyedropper-right-click)
  - [Why Some Faces Can't Be Edited](#why-some-faces-cant-be-edited)
  - [When the 3D View Doesn't Come Up](#when-the-3d-view-doesnt-come-up)
- [Animation Playback](#animation-playback)
- [Color Picker](#color-picker)
- [Transform Colors](#transform-colors)
  - [Modes](#modes)
  - [Scope](#scope)
  - [Live Preview and Apply](#live-preview-and-apply)
- [Gradient Fill](#gradient-fill)
- [Undo / Redo](#undo--redo)
- [Library I/O](#library-io)
  - [Open Library / Save Library](#open-library--save-library)
  - [Exporting a Single Paintjob](#exporting-a-single-paintjob)
  - [Paintjobs Are Character-Agnostic](#paintjobs-are-character-agnostic)
  - [Colors in the JSON File](#colors-in-the-json-file)
- [Drag-and-Drop](#drag-and-drop)

## First Launch and ISO Layout

On first launch the window opens with an empty sidebar and the status bar asks you to load an ISO. Use **File → Load ISO...** and point it at the root of your extracted CTR directory — specifically the folder that contains `bigfile/`. If a character's mesh isn't present, previewing that character shows a load-failed message; every other feature still works.

The ISO path is remembered across sessions, so you only have to do this once per machine.

## Profiles

A **profile** tells the editor which game you're painting for — which characters exist, what their paintjob slots are called, and where the original palettes live in video memory. Two profiles ship in the box:

- **vanilla-ntsc-u** — the original NTSC-U release of CTR.
- **saphi** — the Saphi mod.

Switch between them from the toolbar or **File → Switch Profile...**. To paint for a different mod, drop its profile JSON into the editor's `config/profiles/` folder and it'll appear in the picker on next launch.

### Switching Profiles Resets the Session

Confirming a profile switch clears the current library and the undo history. Character names, slot names, and library sizes can all differ between profiles, so carrying over the in-progress work wouldn't be safe. Save the library first if it matters.

Your choice is remembered, so the next launch starts on the same profile.

## Paintjob Library

The **left sidebar** lists every paintjob in the current session. **New** creates a paintjob pre-filled with the current preview character's original palette — every slot starts fully authored, so no gaps sneak into what you save. **Delete** asks for confirmation before removing the selected paintjob, and clears the undo history at the same time. Rows can be dragged to reorder.

Each paintjob carries four pieces of information:

- **Name** — shown in the sidebar and used as the default filename when saving.
- **Author** — a credit line, shown in a muted second line under the name in the sidebar when you've set one.
- **Base character** — the character this paintjob conceptually belongs to. See [Home Character vs Preview Character](#home-character-vs-preview-character).
- **Slot colors and textures** — the 16 colors per slot, and optionally imported pixel data for slots that carry custom textures.

### Library Position Matters

The sidebar's top-to-bottom order becomes the library's index order. When you save, each paintjob is written with a numeric prefix (`00_...`, `01_...`) that preserves the order when you open the library again. Downstream tools that consume the library use that index — typically to map library positions to in-game paintjob slots — so reordering the sidebar has real downstream effects.

### Sidebar Context Menu

Right-click a paintjob row for:

- **Rename...** — change the display name.
- **Set author...** — change the author credit.
- **Change base character...** — change which character this paintjob belongs to.
- **Export as JSON...** — save just that paintjob to a file of your choice.
- **Replace from JSON...** — overwrite the selected paintjob with one loaded from a file. Clears the undo history.
- **Delete** — remove the paintjob after a confirmation. Clears the undo history.

## Preview Character

The **Preview on:** dropdown above the 3D viewer picks which character's body and palette the editor shows the active paintjob on. Paintjobs don't belong to characters — the dropdown is purely about viewing, so a "Saphi" paintjob can be auditioned on Crash, Cortex, or Penta without changing any saved data.

Switching preview character reloads the model and redraws the paintjob on it. Slots you haven't explicitly authored inherit the preview character's original palette, so the 3D view always shows what the game would draw if *that* character wore the paintjob.

### Home Character vs Preview Character

Two distinct ideas:

- **Preview character** — chosen via the dropdown. Drives the 3D model and the fallback palette for unauthored slots in the editor.
- **Home character** (also called the **base character**) — the character this paintjob conceptually belongs to. Saved with the paintjob and used by downstream tools when they need to decide "whose paintjob is this, really?"

The editor shows what the paintjob looks like *right now on the preview character*. The file carries the home-character hint and leaves interpretation to the tools that read it.

### Textured Paintjobs Stay Character-Agnostic

Right-click a slot → **Import texture...** → pick a PNG → the slot's colors and pixels are baked from the image. Textured paintjobs still apply to every character: the import flow only accepts slots whose size is the same on every character, so the same pixel data uploads cleanly everywhere.

The sidebar marks such paintjobs with `" (textured)"` next to the name — purely informational, so you can tell at a glance which ones carry custom images. Switching the preview character still works normally while a textured paintjob is selected.

**The `floor` slot can't be textured.** Its size varies from character to character, so an imported image couldn't be reused across the roster. The import dialog refuses it with a clear message. You can still edit `floor`'s colors — the palette swap carries over fine.

## Slot Editor

Each row shows a slot's 16 colors across the top, with **Highlight** and **Reset** buttons underneath. Clicking a color opens the color picker; changes apply immediately and stream into the 3D preview.

Right-click a color for the per-color menu (**Transform colors...** scoped to this slot, pre-filled with the clicked color). Right-click the slot row (outside any color) for the whole-slot menu — **Transform colors...** and **Gradient fill...**.

### The First Color Is Transparent

The first color of every row has an **orange border** and a tooltip explaining that this slot is the game's transparency marker. Pixels that land on it render fully transparent regardless of what color you pick, so editing it almost never does what you'd expect. The marker is a warning, not a lock — you can still edit it if you mean to.

### Highlight Button

Each slot row has a checkable **Highlight** button. Clicking it dims every part of the 3D kart that *doesn't* use that slot, so you can see at a glance which surfaces the slot paints. Clicking the same button again clears the highlight; clicking another row's button moves it. Switching paintjobs or preview characters clears the highlight automatically. Highlighting doesn't affect anything that gets saved — it's purely a viewing aid.

### Reset vs Undo

- **Reset button** — replaces every color in that slot with the original palette of the paintjob's **base character** — *not* the current preview character. This way editing Crash's paintjob while previewing on Cortex still resets to Crash's original palette, which is what you mean by "revert." Ctrl+Z un-resets cleanly.
- **Ctrl+Z** — reverses the most recent edit (color pick, reset, gradient fill, or transform), regardless of which paintjob is currently selected. If the reverted edit targets a different paintjob than the one on screen, the sidebar automatically moves to that paintjob so the visible state tracks the change.

The undo history is session-wide and never auto-clears when you switch paintjobs. It does clear when you load a library, import or replace a paintjob, or delete one — in those cases the previous edits can no longer be replayed meaningfully.

## 3D Preview

### Orbit Camera Controls

- **Left-drag** — orbit the camera around the kart.
- **Wheel** — zoom in and out.
- **R** — reset the view (same as **View → Reset Camera**). Reset returns to the framing the editor chose when the character loaded, not a blank world origin.

### Eyedropper (Right-Click)

**Right-click any surface on the 3D kart** to sample the slot and color under the cursor. The color picker opens pre-loaded with that color so one right-click + one pick changes the paintjob. If the click lands on a part of the model that isn't paintjob-editable (wheels, shared driver geometry), the status bar says so and no picker opens.

Orbit and zoom still work with left-drag and the wheel regardless — there's no eyedropper mode to toggle on and off.

### Why Some Faces Can't Be Edited

Character models mix two kinds of surfaces:

- **Paintjob surfaces** — sampled from the palette slots you edit. Most of the kart body is built this way.
- **Fixed surfaces** — hard-coded colors baked into the model itself (Crash's red pants, Pura's orange fur, wheel rims). The paintjob doesn't touch them; the eyedropper reports "not a paintjob face" when you click these.

The editor renders both kinds the way the real game does, so the preview matches what the PS1 would draw. A lot of CTR textures ship as greyscale templates that tint at runtime; you'll see them in their final tinted colors in the preview.

### When the 3D View Doesn't Come Up

Some systems can't bring up hardware 3D (old drivers, remote desktop without graphics acceleration, and so on). In that case the 3D pane is replaced with a message telling you so. The slot editor, sidebar, and library saving all stay fully functional — only the live preview is disabled.

## Animation Playback

The Animation panel below the sidebar shows up when the preview character has animation clips baked in. Pick a clip, press Play, and the 3D viewer steps through its frames at the FPS you've set.

**FPS is a preview control, not saved data.** The game doesn't carry an intended framerate; 30 fps is a preview default because it reads well for idle loops. Nothing about the saved paintjob cares about this value.

Very long clips with hundreds of frames may play back noticeably slower than short idle loops.

## Color Picker

Every color you pick is **snapped to the PSX color grid** before being written back: the PS1 supports only a limited palette (32 levels per channel), so the editor rounds your choice to the nearest representable color. What you see in the swatch after picking is exactly what the game will display. The snap is lossy — `#FF7F3A` going in might come back as `#FF7F38`.

## Transform Colors

The **Transform Colors...** action (top toolbar, or right-click menus on colors and slot rows) opens a **dockable panel** for bulk edits. The panel stays open while you orbit the 3D view, switch paintjobs, or focus different slots — each change updates what the panel is about to touch. Applying a batch lands as a single undo entry, so one Ctrl+Z reverts the whole composition at once.

Every operation lives in its own section with an enable checkbox. Tick multiple sections and they compose in a **fixed order**:

1. Replace matching color
2. Replace hue
3. Shift hue
4. Shift saturation
5. Shift brightness
6. RGB delta

Selective operations (the two Replace modes) run first, so their output is what the later ones see — e.g. swap green to red, then a downstream "shift hue" rotates the whole palette with the swap already baked in. The order isn't configurable; predictable composition beats reordering.

### Modes

- **Replace matching color** — pick a "Match" and a "Replace with" color. Every color in scope that exactly matches the Match color is rewritten.
- **Replace hue** — pick a "From hue" color, a "To hue" color, and a tolerance (0–180°). Every color whose hue is within ±tolerance of the From hue is rotated to the To hue, preserving saturation and brightness. A gradient of greens keeps its relative shading when it lands in the reds. Near-gray pixels are skipped, so whites and grays don't get tinted along with the colors you actually mean to change.
- **Shift hue** — slider in degrees (−180° to +180°). Rotates every color around the color wheel.
- **Shift brightness / saturation** — sliders in percent. Brightens/darkens and adds/removes saturation.
- **RGB delta** — three sliders for red, green, and blue. Adds or subtracts per channel.

The transparency slot (first color of each row) is never touched by any mode — it's a structural marker, not a real color.

### Scope

- **Just this slot** — transforms the 16 colors of the focused slot.
- **Entire kart** — transforms every slot of the active paintjob (128 colors total).

How you opened the panel picks the starting scope:

- Right-click a **color** → panel opens scoped to this slot, with Replace matching color pre-filled to the clicked color.
- Right-click a **slot row** → panel opens scoped to this slot.
- Toolbar **Transform Colors...** → panel opens scoped to the entire kart.

The scope dropdown at the top of the panel stays interactive — switch it any time.

### Live Preview and Apply

Slider, checkbox, and picker changes stream a **live preview** straight into the paintjob and 3D view. There's no separate "Preview" button; what you see while dialing is the current stack. A summary line at the bottom reports how many colors would actually change.

**Apply** commits the current composition as one undo entry and resets every section's sliders to zero (enable checkboxes stay on, so the next round doesn't require re-ticking the same operations). Closing the panel reverts every pending preview change — nothing uncommitted survives the close.

Even a whole-kart hue shift across 100+ colors lands in a single frame, so the preview feels immediate.

## Gradient Fill

Right-click a slot row → **Gradient fill...** fills a contiguous range of the slot's colors with a linear interpolation between two endpoint colors.

- **Color space** — *RGB* interpolates per channel (predictable but can wash out at midpoints; red → blue passes through grey). *HSV* walks the shorter arc around the color wheel, so red → blue goes through magenta instead.
- **From / To index** — which colors to fill. Defaults skip the transparency slot.
- **Endpoints** — both are preserved exactly; intermediate colors are rounded to the PS1 color grid.
- One Ctrl+Z reverts the whole fill.

## Undo / Redo

- **Ctrl+Z / Ctrl+Shift+Z** (or Ctrl+Y) — single session-wide history.
- Undo works across sidebar selections: edit paintjob A, switch to paintjob B, edit B, Ctrl+Z twice — B's edit reverts first, then A's. If the reverted edit targets a paintjob that isn't currently selected, the sidebar auto-switches to it.
- **Loading a library, importing or replacing a paintjob, deleting a paintjob, or switching profiles** all clear the undo history. Previous edits can't be replayed meaningfully once the underlying data has moved out from under them.

## Library I/O

The editor's only output is the **library directory** — a folder of paintjob JSON files. Downstream mod-specific tools read the directory and produce whatever their mod needs (source files, binaries, and so on). See [library_format.md](library_format.md) for the on-disk format.

### Open Library / Save Library

- **File → Open Library...** (Ctrl+O) loads every JSON file in a chosen directory, in filename order. Files the editor can't parse stop the load with a message naming the offending file.
- **File → Save Library As...** (Ctrl+Shift+S) writes every paintjob in the library to a chosen directory, using a numeric filename prefix so the order round-trips on the next open. Same thing the **Save Library** toolbar button does.
- **File → Import Paintjob...** appends a single paintjob file to the end of the current library.

### Exporting a Single Paintjob

Right-click a paintjob → **Export as JSON...** writes just that paintjob to a chosen path. The default filename is built from the paintjob's name, falling back to the base character, and then to a numbered fallback. Useful for sharing a single paintjob outside a library.

### Paintjobs Are Character-Agnostic

A plain paintjob (no imported textures) has no mandatory character — any character can wear it. The base character is only a hint for the preview and for downstream tools.

A textured paintjob **is still character-agnostic**: the import flow only accepts slots whose size is identical across every character, so the same image uploads cleanly on all of them. The one exception is the `floor` slot, which varies per character and therefore can't carry imported images.

### Colors in the JSON File

If you ever open a paintjob JSON by hand, you'll see each color written as a 4-digit hex value like `"#7fff"`. That's the raw 16-bit PS1 color — not a standard `#RRGGBB` web color. The 16-bit form is what the game actually stores, and it's the only way to distinguish opaque black from transparent black (both are RGB 0, 0, 0, but the game treats them as completely different pixels). Saving as plain RGB hex would silently collapse opaque blacks to transparent on reload, so the editor keeps the full 16-bit value.

## Drag-and-Drop

Drag a paintjob JSON file onto the main window to append it to the library (same as **File → Import Paintjob...**). Other file types are silently ignored.
