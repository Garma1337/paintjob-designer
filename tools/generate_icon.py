#!/usr/bin/env python

"""Generate `app.ico` at the repository root for the Paintjob Designer.

The icon is a 4x4 grid of CLUT swatches — the exact visual metaphor the
editor uses for a slot's 16-color palette.

    python tools/generate_icon.py

Produces a multi-resolution `.ico` (16, 32, 48, 64, 128, 256) so Windows
can pick the right size for title bar vs alt-tab vs taskbar without
rescaling artifacts.
"""

from pathlib import Path

from PIL import Image, ImageDraw


_REPO_ROOT = Path(__file__).resolve().parent.parent
_OUTPUT = _REPO_ROOT / "app.ico"


# 4x4 swatch palette — reads as "paint colors" at every size.
# Top-left cell is the PSX transparency sentinel (index 0); it gets an
# orange border to match the slot editor's marker convention.
_PALETTE = [
    # row 0
    (0x00, 0x00, 0x00, 0xFF),  # transparent (stp=0) → shown as black chip
    (0xE8, 0x3E, 0x3E, 0xFF),  # red
    (0xF0, 0x8C, 0x38, 0xFF),  # orange
    (0xF0, 0xD8, 0x40, 0xFF),  # yellow
    # row 1
    (0x9A, 0xDE, 0x3A, 0xFF),  # lime
    (0x38, 0xC8, 0x58, 0xFF),  # green
    (0x30, 0xB8, 0xC0, 0xFF),  # cyan
    (0x3E, 0x7E, 0xE8, 0xFF),  # blue
    # row 2
    (0x60, 0x48, 0xD0, 0xFF),  # indigo
    (0xA6, 0x48, 0xD8, 0xFF),  # purple
    (0xE0, 0x48, 0xB0, 0xFF),  # magenta
    (0xE0, 0x78, 0x8C, 0xFF),  # pink
    # row 3
    (0x8A, 0x60, 0x48, 0xFF),  # brown
    (0xC0, 0x9C, 0x78, 0xFF),  # tan
    (0xB8, 0xB8, 0xB8, 0xFF),  # light grey
    (0xFF, 0xFF, 0xFF, 0xFF),  # white
]

_BG = (32, 32, 40, 255)
_TRANSPARENCY_BORDER = (255, 140, 40, 255)  # same "warning" orange as the slot editor


def _render(size: int) -> Image.Image:
    """Render the icon at `size` x `size` pixels.

    Layout:
      - 6%-of-size margin around the grid
      - 4x4 swatches with a 1-pixel-ish gap
      - Rounded outer frame (subtle) so the icon has a silhouette at small sizes
    """
    img = Image.new("RGBA", (size, size), _BG)
    draw = ImageDraw.Draw(img)

    # Rounded outer frame keeps the icon readable when Windows puts it on
    # light backgrounds (the dark chip silhouette is enough to pop).
    corner = max(2, size // 10)
    draw.rounded_rectangle(
        [(0, 0), (size - 1, size - 1)],
        radius=corner,
        fill=_BG,
    )

    margin = max(2, size // 14)
    inner = size - 2 * margin
    gap = max(1, size // 48)
    cell = (inner - 3 * gap) // 4

    # Any leftover from the integer division goes into the bottom-right margin
    # — invisible at 16px, irrelevant at 256.
    grid_w = cell * 4 + gap * 3

    offset_x = (size - grid_w) // 2
    offset_y = (size - grid_w) // 2

    for row in range(4):
        for col in range(4):
            idx = row * 4 + col
            x0 = offset_x + col * (cell + gap)
            y0 = offset_y + row * (cell + gap)
            x1 = x0 + cell - 1
            y1 = y0 + cell - 1
            rect = [(x0, y0), (x1, y1)]
            draw.rectangle(rect, fill=_PALETTE[idx])

            if idx == 0:
                border_w = max(1, size // 64)
                for i in range(border_w):
                    draw.rectangle(
                        [(x0 + i, y0 + i), (x1 - i, y1 - i)],
                        outline=_TRANSPARENCY_BORDER,
                    )

    return img


def main() -> None:
    # Windows .ico is multi-resolution; each frame gets embedded and the OS
    # picks whichever matches the display context best.
    base = _render(256)
    sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    base.save(_OUTPUT, format="ICO", sizes=sizes)
    print(f"Wrote {_OUTPUT}")


if __name__ == "__main__":
    main()
