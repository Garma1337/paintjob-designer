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
    """4-byte per-vertex color stored at CtrMesh.ptr_clut (RGB + flag byte)."""
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
    """Per-face UV + palette + page mapping. 12 bytes in the .ctr file."""
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
    """A single draw command — a big-endian u32 from the command list."""
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
    """Per-vertex compression delta used by animated `CtrFrame`s."""
    bits_x: int = 0
    bits_y: int = 0
    bits_z: int = 0
    pos_x: int = 0
    pos_y: int = 0
    pos_z: int = 0


@dataclass
class CtrFrame:
    """One vertex frame (for animated models, one per keyframe; otherwise a single frame)."""
    offset: Vector3f = field(default_factory=Vector3f)
    vertices: list[Vector3b] = field(default_factory=list)


@dataclass
class CtrAnim:
    """One animation: a short name plus an ordered list of vertex keyframes."""
    name: str = ""
    frames: list[CtrFrame] = field(default_factory=list)


@dataclass
class CtrMesh:
    """One LOD entry. A `CtrModel` can hold several (hi, med, low)."""
    name: str = ""
    lod_distance: int = 0
    billboard: int = 0
    scale: Vector3f = field(default_factory=Vector3f)
    is_animated: bool = False

    draw_commands: list[CtrDraw] = field(default_factory=list)
    texture_layouts: list[TextureLayout] = field(default_factory=list)
    gouraud_colors: list[GouraudColor] = field(default_factory=list)
    frame: CtrFrame = field(default_factory=CtrFrame)

    anims: list[CtrAnim] = field(default_factory=list)


@dataclass
class CtrModel:
    """Top-level object inside a `.ctr` file (wrapped in an outer PatchedContainer)."""
    name: str = ""
    thread_id: int = 0
    meshes: list[CtrMesh] = field(default_factory=list)


@dataclass
class AssembledMesh:
    """Flat triangle list assembled from a `CtrMesh`'s draw-command stream."""
    positions: list[tuple[float, float, float]] = field(default_factory=list)
    uvs: list[tuple[int, int]] = field(default_factory=list)
    texture_layout_indices: list[int] = field(default_factory=list)
    gouraud_colors: list[tuple[float, float, float]] = field(default_factory=list)
    gouraud_color_indices: list[tuple[int, int, int]] = field(default_factory=list)

    @property
    def triangle_count(self) -> int:
        return len(self.texture_layout_indices)
