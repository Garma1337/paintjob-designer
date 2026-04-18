# coding: utf-8

from paintjob_designer.core.binary_reader import BinaryReader
from paintjob_designer.core.bitstream_reader import BitStreamReader
from paintjob_designer.ctr.animation import AnimationDecoder
from paintjob_designer.models import (
    BitDepth,
    BlendingMode,
    CtrAnim,
    CtrDelta,
    CtrDraw,
    CtrFrame,
    CtrMesh,
    CtrModel,
    GouraudColor,
    TextureLayout,
    Vector3b,
    Vector3f,
)


# PSX GTE fixed-point small scale: raw integer divided by 2**12.
GTE_SCALE_SMALL = 1 << 12

# Mesh header size in bytes (16 name + 4 unk + 2 lod + 2 bb + 6 scale + 2 pad + 8*4 ptrs/flags).
MESH_HEADER_SIZE = 64

# Default frame vertex-data offset within a frame struct (ctr-tools `CtrFrame.ptrVerts`).
FRAME_VERTS_BASE_OFFSET = 0x1C


class CtrModelReader:
    """Parses a CTR character/object model file into a `CtrModel`.

    The file is a PatchedContainer wrapping the inner model data:

        u4 data_size
        bytes[data_size] inner   # parsed as a CtrModel
        u4 ptr_map_size
        u4[ptr_map_size / 4] ptr_map

    Pointer fields inside the inner data are offsets relative to the start of that
    inner slice — the patch table is ignored at read time (it only matters when
    relocating pointers while rewriting the file).

    Port of `CtrModel.cs` + `CtrMesh.cs` in ctr-tools.
    """

    def __init__(self, animation_decoder: AnimationDecoder) -> None:
        self._animations = animation_decoder

    def read(self, data: bytes) -> CtrModel:
        outer = BinaryReader(data)
        data_size = outer.u4()
        inner = outer.read(data_size)
        return self._read_model(inner)

    def _read_model(self, data: bytes) -> CtrModel:
        reader = BinaryReader(data)

        name = reader.read_strz(16)
        thread_id = reader.s2()
        num_meshes = reader.u2()
        ptr_meshes = reader.u4()

        reader.seek(ptr_meshes)
        headers = [self._read_mesh_header(reader) for _ in range(num_meshes)]

        meshes = [self._build_mesh(data, h) for h in headers]

        return CtrModel(name=name, thread_id=thread_id, meshes=meshes)

    def _read_mesh_header(self, reader: BinaryReader) -> "_MeshHeader":
        name = reader.read_strz(16)
        reader.u4()  # unk0
        lod_distance = reader.s2()
        billboard = reader.u2()
        scale = Vector3f(
            x=reader.s2() / GTE_SCALE_SMALL,
            y=reader.s2() / GTE_SCALE_SMALL,
            z=reader.s2() / GTE_SCALE_SMALL,
        )
        reader.u2()  # padding

        ptr_cmd = reader.u4()
        ptr_frame = reader.u4()
        ptr_tex = reader.u4()
        ptr_clut = reader.u4()
        reader.u4()  # unk3
        num_anims = reader.u4()
        ptr_anims = reader.u4()
        reader.u4()  # unk4

        return _MeshHeader(
            name=name,
            lod_distance=lod_distance,
            billboard=billboard,
            scale=scale,
            ptr_cmd=ptr_cmd,
            ptr_frame=ptr_frame,
            ptr_tex=ptr_tex,
            ptr_clut=ptr_clut,
            num_anims=num_anims,
            ptr_anims=ptr_anims,
        )

    def _build_mesh(self, data: bytes, header: "_MeshHeader") -> CtrMesh:
        reader = BinaryReader(data)

        commands = self._read_commands(reader, header.ptr_cmd)

        max_color = max((c.color_index for c in commands), default=0)
        max_tex = max((c.tex_index for c in commands if c.tex_index > 0), default=0)
        max_verts = sum(1 for c in commands if not c.stack_vertex)

        gouraud_colors = self._read_gouraud_colors(reader, header.ptr_clut, max_color + 1)
        texture_layouts = self._read_texture_layouts(reader, header.ptr_tex, max_tex)

        is_animated = header.num_anims > 0
        frame = CtrFrame()
        anims: list[CtrAnim] = []

        if is_animated and header.ptr_anims != 0 and header.num_anims > 0:
            anims = self._read_all_animations(
                reader, header.ptr_anims, header.num_anims, max_verts,
            )

            if anims and anims[0].frames:
                frame = anims[0].frames[0]
        elif not is_animated and header.ptr_frame != 0:
            reader.seek(header.ptr_frame)
            frame = self._read_frame(reader, max_verts)

        return CtrMesh(
            name=header.name,
            lod_distance=header.lod_distance,
            billboard=header.billboard,
            scale=header.scale,
            is_animated=is_animated,
            draw_commands=commands,
            texture_layouts=texture_layouts,
            gouraud_colors=gouraud_colors,
            frame=frame,
            anims=anims,
        )

    def _read_commands(self, reader: BinaryReader, ptr_cmd: int) -> list[CtrDraw]:
        # Draw commands are little-endian u32s despite the ksy claiming `u4be` —
        # ctr-tools reads them via the default LE `ReadUInt32` and its `CtrDraw`
        # unpack expects that byte order (flags in high bits, tex_index in low).
        reader.seek(ptr_cmd)
        reader.u4()  # leading u4, usually 16-64, purpose unconfirmed
        commands: list[CtrDraw] = []

        while True:
            raw = reader.u4()
            if raw == 0xFFFFFFFF:
                return commands

            commands.append(CtrDraw(raw=raw))

    def _read_gouraud_colors(
        self, reader: BinaryReader, ptr_clut: int, count: int,
    ) -> list[GouraudColor]:
        reader.seek(ptr_clut)
        return [
            GouraudColor(r=reader.u1(), g=reader.u1(), b=reader.u1(), flag=reader.u1())
            for _ in range(count)
        ]

    def _read_texture_layouts(
        self, reader: BinaryReader, ptr_tex: int, count: int,
    ) -> list[TextureLayout]:
        if count == 0:
            return []

        reader.seek(ptr_tex)
        layout_ptrs = [reader.u4() for _ in range(count)]

        layouts = []
        for ptr in layout_ptrs:
            reader.seek(ptr)
            layouts.append(self._read_texture_layout(reader))

        return layouts

    def _read_texture_layout(self, reader: BinaryReader) -> TextureLayout:
        uv0_u, uv0_v = reader.u1(), reader.u1()
        palette = reader.u2()
        uv1_u, uv1_v = reader.u1(), reader.u1()
        page_data = reader.u2()
        uv2_u, uv2_v = reader.u1(), reader.u1()
        uv3_u, uv3_v = reader.u1(), reader.u1()

        return TextureLayout(
            uv0_u=uv0_u, uv0_v=uv0_v,
            uv1_u=uv1_u, uv1_v=uv1_v,
            uv2_u=uv2_u, uv2_v=uv2_v,
            uv3_u=uv3_u, uv3_v=uv3_v,
            palette_x=palette & 0x3F,
            palette_y=palette >> 6,
            page_x=page_data & 0xF,
            page_y=(page_data >> 4) & 0x1,
            blending=BlendingMode((page_data >> 5) & 0x3),
            bpp=BitDepth((page_data >> 7) & 0x3),
        )

    def _read_frame(
        self,
        reader: BinaryReader,
        num_verts: int,
        deltas: list[CtrDelta] | None = None,
        frame_size: int | None = None,
    ) -> CtrFrame:
        """Read a single CtrFrame at the reader's current position.

        When `deltas` is None the frame carries raw Vector3b vertex bytes.
        When `deltas` is a list, the frame's vertex section is a compressed bitstream
        and `frame_size` must give the on-disk size of the frame struct so we know
        how many bytes the bitstream occupies.
        """
        offset = Vector3f(
            x=reader.s2() / GTE_SCALE_SMALL,
            y=reader.s2() / GTE_SCALE_SMALL,
            z=reader.s2() / GTE_SCALE_SMALL,
        )
        reader.u2()  # padding
        reader.skip(16)  # 16 unknown bytes, zero at runtime
        ptr_verts = reader.u4()

        extra = ptr_verts - FRAME_VERTS_BASE_OFFSET
        if extra > 0:
            reader.skip(extra)

        if deltas is None:
            vertices = [
                Vector3b(x=reader.u1(), y=reader.u1(), z=reader.u1())
                for _ in range(num_verts)
            ]
        else:
            if frame_size is None:
                raise ValueError("frame_size is required when decoding a compressed frame")

            bitstream_bytes = max(0, frame_size - ptr_verts)
            bitstream_bytes = min(bitstream_bytes, reader.remaining())
            chunk = reader.read(bitstream_bytes)
            vertices = self._animations.decompress_vertices(BitStreamReader(chunk), deltas)

        return CtrFrame(offset=offset, vertices=vertices)

    def _read_all_animations(
        self,
        reader: BinaryReader,
        ptr_anims: int,
        num_anims: int,
        num_verts: int,
    ) -> list[CtrAnim]:
        """Read every animation for this mesh (name + all keyframes).

        Mirrors `CtrAnim.Read` in ctr-tools: pull the pointer array at
        `ptr_anims`, then for each entry walk the anim header (name,
        `num_frames_pack`, `frame_size`, `ptr_deltas`) + delta table +
        back-to-back keyframes.
        """
        reader.seek(ptr_anims)
        anim_ptrs = [reader.u4() for _ in range(num_anims)]
        return [self._read_one_animation(reader, ptr, num_verts) for ptr in anim_ptrs]

    def _read_one_animation(
        self,
        reader: BinaryReader,
        anim_ptr: int,
        num_verts: int,
    ) -> CtrAnim:
        reader.seek(anim_ptr)
        name = reader.read_strz(16)
        num_frames_pack = reader.u2()
        frame_size = reader.u2()
        ptr_deltas = reader.u4()

        duplicate_frames = (num_frames_pack & 0x8000) != 0
        num_frames = num_frames_pack & 0x7FFF
        if duplicate_frames:
            # Bit 15 means every second frame is interpolated at runtime, so
            # only half+1 are stored. We just read what's stored — playback
            # here runs off keyframes, no 60 fps in-betweening.
            num_frames = num_frames // 2 + 1

        frames_start = reader.position

        deltas: list[CtrDelta] | None = None
        if ptr_deltas != 0:
            reader.seek(ptr_deltas)
            deltas = [self._animations.unpack_delta(reader.u4()) for _ in range(num_verts)]

        frames: list[CtrFrame] = []
        for i in range(num_frames):
            reader.seek(frames_start + i * frame_size)
            frames.append(
                self._read_frame(reader, num_verts, deltas=deltas, frame_size=frame_size)
            )

        return CtrAnim(name=name, frames=frames)


class _MeshHeader:
    """Intermediate representation of a mesh header before we dereference its pointers."""

    __slots__ = (
        "name", "lod_distance", "billboard", "scale",
        "ptr_cmd", "ptr_frame", "ptr_tex", "ptr_clut",
        "num_anims", "ptr_anims",
    )

    def __init__(
        self, name: str, lod_distance: int, billboard: int, scale: Vector3f,
        ptr_cmd: int, ptr_frame: int, ptr_tex: int, ptr_clut: int,
        num_anims: int, ptr_anims: int,
    ) -> None:
        self.name = name
        self.lod_distance = lod_distance
        self.billboard = billboard
        self.scale = scale
        self.ptr_cmd = ptr_cmd
        self.ptr_frame = ptr_frame
        self.ptr_tex = ptr_tex
        self.ptr_clut = ptr_clut
        self.num_anims = num_anims
        self.ptr_anims = ptr_anims
