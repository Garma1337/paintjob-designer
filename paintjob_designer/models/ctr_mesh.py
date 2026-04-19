# coding: utf-8

from dataclasses import dataclass, field
from enum import IntEnum


@dataclass
class Vector3f:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


@dataclass
class Vector3b:
    x: int = 0
    y: int = 0
    z: int = 0


@dataclass
class GouraudColor:
    """4-byte per-vertex color stored at CtrMesh.ptr_clut (RGB + flag byte).

    These are the mesh's Gouraud-shading colors baked into the .ctr — not the
    texture palettes a paintjob replaces. Those live in VRAM at (palette_x*16, palette_y).
    """
    r: int = 0
    g: int = 0
    b: int = 0
    flag: int = 0


class BlendingMode(IntEnum):
    Translucent = 0
    Additive = 1
    Subtractive = 2
    Standard = 3


class BitDepth(IntEnum):
    Bit4 = 0
    Bit8 = 1
    Bit16 = 2
    Bit24 = 3


@dataclass
class TextureLayout:
    """Per-face UV + palette + page mapping. 12 bytes in the .ctr file.

    Packing (ctr-tools `TextureLayout.cs`):
        u8 uv0_u, u8 uv0_v,
        u16 palette   = palette_x (bits 0-5) | palette_y (bits 6-15),
        u8 uv1_u, u8 uv1_v,
        u16 page_data = page_x (bits 0-3) | page_y (bit 4) | blending (bits 5-6) | bpp (bits 7-8),
        u8 uv2_u, u8 uv2_v,
        u8 uv3_u, u8 uv3_v.

    The CLUT this face samples lives in VRAM at (palette_x * 16, palette_y);
    those are the coordinates a paintjob profile targets.
    """
    SIZE = 12

    uv0_u: int = 0
    uv0_v: int = 0
    uv1_u: int = 0
    uv1_v: int = 0
    uv2_u: int = 0
    uv2_v: int = 0
    uv3_u: int = 0
    uv3_v: int = 0

    palette_x: int = 0
    palette_y: int = 0

    page_x: int = 0
    page_y: int = 0

    blending: BlendingMode = BlendingMode.Standard
    bpp: BitDepth = BitDepth.Bit4


@dataclass
class CtrDraw:
    """A single draw command — a big-endian u32 from the command list.

    Bit layout (ctr-tools `txt_ctr.txt` + `ctr_ctr.ksy`):
        bit 31 : new_tristrip (reset triangle strip)
        bit 30 : swap_vertex  (swap last two tempCoords entries)
        bit 29 : flip_normal  (reverse last triangle winding)
        bit 28 : cull_backface
        bit 27 : color_scratchpad
        bit 26 : stack_vertex (don't pop a vertex; use stack[stack_index] instead)
        bits 16-23 : stack_index   (write position in the 256-slot vertex stack)
        bits 9-15  : color_index   (into CtrMesh.colors)
        bits 0-8   : tex_index     (1-based into CtrMesh.texture_layouts; 0 = untextured)
    """
    raw: int = 0

    @property
    def new_tristrip(self) -> bool:
        return (self.raw & (1 << 31)) != 0

    @property
    def swap_vertex(self) -> bool:
        return (self.raw & (1 << 30)) != 0

    @property
    def flip_normal(self) -> bool:
        return (self.raw & (1 << 29)) != 0

    @property
    def cull_backface(self) -> bool:
        return (self.raw & (1 << 28)) != 0

    @property
    def color_scratchpad(self) -> bool:
        return (self.raw & (1 << 27)) != 0

    @property
    def stack_vertex(self) -> bool:
        return (self.raw & (1 << 26)) != 0

    @property
    def stack_index(self) -> int:
        return (self.raw >> 16) & 0xFF

    @property
    def color_index(self) -> int:
        return (self.raw >> 9) & 0x7F

    @property
    def tex_index(self) -> int:
        return self.raw & 0x1FF


@dataclass
class CtrDelta:
    """Per-vertex compression delta used by animated `CtrFrame`s.

    Packed into a single u32 (ctr-tools `CtrDelta.cs`):
        bits 0-2   : bits_z   (temporal-stream width for Z; 7 = reset base to 0)
        bits 3-5   : bits_y
        bits 6-8   : bits_x
        bits 9-16  : pos_z    (8-bit base delta)
        bits 17-24 : pos_y
        bits 25-31 : pos_x    (7-bit; left-shifted by 1 at use time)
    """
    bits_x: int = 0
    bits_y: int = 0
    bits_z: int = 0
    pos_x: int = 0
    pos_y: int = 0
    pos_z: int = 0


@dataclass
class CtrFrame:
    """One vertex frame (for animated models, one per keyframe; otherwise a single frame).

    `vertices` are compressed into bytes [0, 255]. Final world-space position per vertex is:
        pos = (vertex_byte / 255.0 + offset) * mesh.scale
    """
    offset: Vector3f = field(default_factory=Vector3f)
    vertices: list[Vector3b] = field(default_factory=list)


@dataclass
class CtrAnim:
    """One animation: a short name plus an ordered list of vertex keyframes."""
    name: str = ""
    frames: list[CtrFrame] = field(default_factory=list)


@dataclass
class CtrMesh:
    """One LOD entry. A `CtrModel` can hold several (hi, med, low).

    `is_animated` is true when `num_anims > 0`. In that case vertex positions live
    in compressed animation frames rather than a single static `frame`, and the
    reader leaves `frame.vertices` empty. (Animation decompression is future work.)
    """
    name: str = ""
    lod_distance: int = 0
    billboard: int = 0
    scale: Vector3f = field(default_factory=Vector3f)
    is_animated: bool = False

    draw_commands: list[CtrDraw] = field(default_factory=list)
    texture_layouts: list[TextureLayout] = field(default_factory=list)
    gouraud_colors: list[GouraudColor] = field(default_factory=list)
    frame: CtrFrame = field(default_factory=CtrFrame)

    # Every animation the mesh carries. Always empty for static meshes.
    # For animated meshes, `frame` mirrors `anims[0].frames[0]` so callers that
    # don't care about playback still see a sensible default pose.
    anims: list[CtrAnim] = field(default_factory=list)


@dataclass
class CtrModel:
    """Top-level object inside a `.ctr` file (wrapped in an outer PatchedContainer)."""
    name: str = ""
    thread_id: int = 0
    meshes: list[CtrMesh] = field(default_factory=list)


@dataclass
class AssembledMesh:
    """Flat triangle list assembled from a `CtrMesh`'s draw-command stream.

    All three per-vertex arrays (positions, uvs, texture_layout_indices_per_vertex) are
    aligned: index `i*3 + j` is the `j`-th vertex of triangle `i`. The per-triangle
    `texture_layout_indices` list is 1-based into `CtrMesh.texture_layouts` (0 =
    untextured). UVs are in the original 0..255 byte space of the source TextureLayout,
    not yet normalized to the TL's bounding box — renderers apply that transform.

    `gouraud_colors` carries the per-vertex Gouraud color (normalized 0..1 RGB).
    Textured triangles ignore it in the shader; untextured triangles use it as
    their base color so the faces render with the mesh's baked-in colors instead
    of a flat placeholder grey.
    """
    positions: list[tuple[float, float, float]] = field(default_factory=list)
    uvs: list[tuple[int, int]] = field(default_factory=list)
    texture_layout_indices: list[int] = field(default_factory=list)
    gouraud_colors: list[tuple[float, float, float]] = field(default_factory=list)

    @property
    def triangle_count(self) -> int:
        return len(self.texture_layout_indices)
