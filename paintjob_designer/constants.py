# coding: utf-8

"""Shared numeric constants for PSX color math and CTR data layout.

These are the invariants (bit widths, component ranges, fixed palette
sizes) that appear in color conversion, rendering, and model/UI code.
Keeping them here means readers don't sprinkle `0x1F` or `0x8000`
literals, and tests/tools can reference the same names.
"""

# PSX 15-bit BGR color layout.
# Each component is 5 bits; packed as STP|B|G|R in a 16-bit word.
PSX_BITS_PER_COMPONENT = 5
PSX_COMPONENT_MAX = 31
PSX_COMPONENT_MASK = 0x1F

PSX_RED_SHIFT = 0
PSX_GREEN_SHIFT = 5
PSX_BLUE_SHIFT = 10
PSX_STP_SHIFT = 15

PSX_STP_BIT = 0x8000    # high bit: stencil / semi-transparency flag
PSX_RGB_MASK = 0x7FFF   # mask off STP to test "is RGB black?"
PSX_U16_MASK = 0xFFFF

# CTR renders any RGB-black texel as transparent in-game, regardless of
# the stp bit. Use this value when constructing a transparent placeholder
# (distinct from the raw STP bit, which just happens to share the value).
PSX_TRANSPARENT_VALUE = 0x8000

# 8-bit RGB
RGB_COMPONENT_MAX = 255

# CTR CLUT: one 4bpp paintable slot has 16 colors.
CLUT_PALETTE_SIZE = 16
