# coding: utf-8

import struct

import pytest

from paintjob_designer.color.converter import ColorConverter
from paintjob_designer.config.iso_root_validator import IsoRootValidator
from paintjob_designer.ctr.animation import AnimationDecoder
from paintjob_designer.ctr.reader import CtrModelReader
from paintjob_designer.ctr.vertex_assembler import VertexAssembler
from paintjob_designer.exporters.binary_exporter import BinaryExporter
from paintjob_designer.exporters.source_code_exporter import SourceCodeExporter
from paintjob_designer.gui.handler.character_handler import CharacterHandler
from paintjob_designer.gui.handler.color_handler import ColorHandler
from paintjob_designer.gui.handler.project_handler import ProjectHandler
from paintjob_designer.models import SlotColors, PsxColor
from paintjob_designer.paintjob.single_reader import SinglePaintjobReader
from paintjob_designer.paintjob.single_writer import SinglePaintjobWriter
from paintjob_designer.profile.reader import ProfileReader
from paintjob_designer.profile.registry import ProfileRegistry
from paintjob_designer.render.atlas_renderer import AtlasRenderer
from paintjob_designer.render.atlas_uv_mapper import AtlasUvMapper
from paintjob_designer.render.slot_region_deriver import SlotRegionDeriver
from paintjob_designer.vram.cache import VramCache
from paintjob_designer.vram.reader import VramReader


@pytest.fixture
def color_converter():
    return ColorConverter()


@pytest.fixture
def iso_root_validator():
    return IsoRootValidator()


@pytest.fixture
def profile_reader():
    return ProfileReader()


@pytest.fixture
def profile_registry(profile_reader):
    return ProfileRegistry(profile_reader)


@pytest.fixture
def animation_decoder():
    return AnimationDecoder()


@pytest.fixture
def ctr_model_reader(animation_decoder):
    return CtrModelReader(animation_decoder)


@pytest.fixture
def vertex_assembler():
    return VertexAssembler()


@pytest.fixture
def slot_region_deriver():
    return SlotRegionDeriver()


@pytest.fixture
def vram_reader():
    return VramReader()


@pytest.fixture
def vram_cache(vram_reader):
    return VramCache(vram_reader)


@pytest.fixture
def atlas_renderer(color_converter):
    return AtlasRenderer(color_converter)


@pytest.fixture
def atlas_uv_mapper():
    return AtlasUvMapper()


@pytest.fixture
def character_handler(ctr_model_reader, vram_cache, slot_region_deriver, atlas_renderer):
    return CharacterHandler(ctr_model_reader, vram_cache, slot_region_deriver, atlas_renderer)


@pytest.fixture
def color_handler(vram_cache, atlas_renderer):
    return ColorHandler(vram_cache, atlas_renderer)


@pytest.fixture
def project_handler(single_paintjob_reader, single_paintjob_writer):
    return ProjectHandler(single_paintjob_reader, single_paintjob_writer)


@pytest.fixture
def single_paintjob_reader(color_converter):
    return SinglePaintjobReader(color_converter)


@pytest.fixture
def single_paintjob_writer(color_converter):
    return SinglePaintjobWriter(color_converter)


@pytest.fixture
def source_code_exporter():
    return SourceCodeExporter()


@pytest.fixture
def binary_exporter():
    return BinaryExporter()


def slot_of(value: int = 0x1234) -> SlotColors:
    """Build a `SlotColors` with 16 copies of `PsxColor(value=value)`.

    Default (`0x1234`) is a non-zero non-black value so `value == 0` tests
    don't silently pass on a slot full of transparent sentinels.
    """
    return SlotColors(colors=[PsxColor(value=value) for _ in range(SlotColors.SIZE)])


def atlas_pixel(rgba: bytearray, x: int, y: int, atlas_width: int) -> tuple[int, int, int, int]:
    """Read an RGBA tuple from a packed atlas buffer.

    `atlas_width` is a param rather than a constant import because this
    helper is used against both the real `AtlasRenderer.ATLAS_WIDTH` and
    smaller synthesized buffers in decoder tests.
    """
    off = (y * atlas_width + x) * 4
    return tuple(rgba[off:off + 4])


def encode_bitstream(bits: list[int]) -> bytes:
    """Encode a bit sequence for `BitStreamReader` consumption.

    The reader consumes 4-byte LE u32 blocks, bit-reverses each, then pulls
    LSB-first. To put bit `i` at cache position `i` (i.e. delivered on the
    i-th `take_bit()`), the encoder writes bit `i` at MSB-offset `i` of the
    enclosing big-endian u32, then stores that u32 little-endian.
    """
    padded = bits + [0] * ((-len(bits)) % 32)
    out = bytearray()

    for start in range(0, len(padded), 32):
        u32 = 0
        for i in range(32):
            if padded[start + i]:
                u32 |= 1 << (31 - i)

        out.extend(u32.to_bytes(4, "little"))

    return bytes(out)


def pack_delta(
    bits_x: int, bits_y: int, bits_z: int,
    pos_x: int, pos_y: int, pos_z: int,
) -> int:
    """Pack a `CtrDelta` u32 — mirrors the layout in `ctr/animation.py`."""
    return (
        ((bits_x & 0x7) << 6)
        | ((bits_y & 0x7) << 3)
        | ((bits_z & 0x7) << 0)
        | ((pos_x & 0x7F) << 25)
        | ((pos_y & 0xFF) << 17)
        | ((pos_z & 0xFF) << 9)
    )


_MESH_HEADER_SIZE = 64
_GTE_SCALE_SMALL = 4096


def _pad_fixed(s: bytes, n: int) -> bytes:
    return s.ljust(n, b"\x00")[:n]


def _align4(buf: bytearray) -> None:
    while len(buf) % 4:
        buf.append(0)


def _write_animations(inner: bytearray, hs: int, animations: list[dict]) -> None:
    """Append an animation block (ptr_anims table + per-anim header/deltas/frames)."""
    ptr_anims = len(inner)
    struct.pack_into("<I", inner, hs + 0x38, ptr_anims)

    anims_array_start = len(inner)
    inner += b"\x00" * (4 * len(animations))
    _align4(inner)

    for idx, anim in enumerate(animations):
        anim_start = len(inner)
        struct.pack_into("<I", inner, anims_array_start + idx * 4, anim_start)

        inner += _pad_fixed(anim.get("name", f"anim{idx}").encode("ascii"), 16)

        frames = anim["frames"]
        deltas = anim.get("deltas")

        if deltas is not None:
            encoded = [encode_bitstream(f.get("bits", [])) for f in frames]
            max_stream = max((len(b) for b in encoded), default=0)
            encoded = [b + b"\x00" * (max_stream - len(b)) for b in encoded]
            frame_size = 0x1C + max_stream
        else:
            num_verts = anim.get("num_verts_for_raw", 0)
            encoded = None
            frame_size = 0x1C + num_verts * 3
            if frame_size % 4:
                frame_size += 4 - (frame_size % 4)

        inner += struct.pack("<HH", len(frames), frame_size)
        ptr_deltas_pos = len(inner)
        inner += struct.pack("<I", 0)

        for fi, frame in enumerate(frames):
            frame_start = len(inner)
            ox, oy, oz = frame.get("offset", (0.0, 0.0, 0.0))
            inner += struct.pack(
                "<hhhH",
                int(ox * _GTE_SCALE_SMALL),
                int(oy * _GTE_SCALE_SMALL),
                int(oz * _GTE_SCALE_SMALL),
                0,
            )
            inner += b"\x00" * 16
            inner += struct.pack("<I", 0x1C)

            if encoded is not None:
                inner += encoded[fi]
            else:
                for v in frame.get("vertices", []):
                    inner += bytes((v[0] & 0xFF, v[1] & 0xFF, v[2] & 0xFF))

            while len(inner) - frame_start < frame_size:
                inner.append(0)

        if deltas is not None:
            struct.pack_into("<I", inner, ptr_deltas_pos, len(inner))

            for d in deltas:
                inner += struct.pack("<I", pack_delta(
                    d.get("bits_x", 0), d.get("bits_y", 0), d.get("bits_z", 0),
                    d.get("pos_x", 0), d.get("pos_y", 0), d.get("pos_z", 0),
                ))

            _align4(inner)


def _build_tim_block(origin_x: int, origin_y: int, width: int, height: int, pixels: bytes) -> bytes:
    """Build one TIM bitmap block (12-byte header + pixel payload).

    `width` is in 16bpp pixels and must match `len(pixels) / (2 * height)`.
    """
    payload_size = width * height * 2
    if len(pixels) < payload_size:
        pixels = pixels + b"\x00" * (payload_size - len(pixels))

    block = struct.pack("<IHHHH", payload_size + 12, origin_x, origin_y, width, height)
    return block + pixels[:payload_size]


def build_tim(
    bpp: int,
    image: dict,
    clut: dict | None = None,
) -> bytes:
    """Build a single TIM: magic + flags + optional CLUT block + image block.

    `image` / `clut` dicts each carry `origin_x, origin_y, width, height, pixels`.
    """
    flags = (bpp & 0x3) | (0x8 if clut is not None else 0)
    out = struct.pack("<II", 0x10, flags)
    if clut is not None:
        out += _build_tim_block(
            clut["origin_x"], clut["origin_y"], clut["width"], clut["height"], clut["pixels"],
        )

    out += _build_tim_block(
        image["origin_x"], image["origin_y"], image["width"], image["height"], image["pixels"],
    )

    return out


def build_vrm_bytes(tims: list[bytes]) -> bytes:
    """Wrap one or more TIM payloads in the CTR stream container.

    Layout: u4 `0x20` magic, then for each TIM `(u4 data_size, TIM bytes)`, then a
    `u4 0` terminator.
    """
    out = bytearray(struct.pack("<I", 0x20))
    for tim in tims:
        out += struct.pack("<I", len(tim))
        out += tim

    out += struct.pack("<I", 0)
    return bytes(out)


def _encode_texture_layout(tl: dict) -> bytes:
    """Build the 12-byte TextureLayout struct from a dict of fields."""
    palette = (tl.get("palette_x", 0) & 0x3F) | ((tl.get("palette_y", 0) & 0x3FF) << 6)
    page_data = (
        (tl.get("page_x", 0) & 0xF)
        | ((tl.get("page_y", 0) & 0x1) << 4)
        | ((tl.get("blending", 3) & 0x3) << 5)
        | ((tl.get("bpp", 0) & 0x3) << 7)
    )

    return (
        bytes([tl.get("uv0_u", 0), tl.get("uv0_v", 0)])
        + struct.pack("<H", palette)
        + bytes([tl.get("uv1_u", 0), tl.get("uv1_v", 0)])
        + struct.pack("<H", page_data)
        + bytes([tl.get("uv2_u", 0), tl.get("uv2_v", 0)])
        + bytes([tl.get("uv3_u", 0), tl.get("uv3_v", 0)])
    )


def build_ctr_bytes(
    model_name: str = "test",
    thread_id: int = 0,
    meshes: list[dict] | None = None,
) -> bytes:
    """Build minimal valid .ctr file bytes.

    Each mesh dict accepts: name, lod_distance, billboard, scale (3-tuple),
    unk_num, commands (list of u32 raws), colors (list of (r,g,b,flag)),
    texture_layouts (list of dicts per _encode_texture_layout), offset (3-tuple),
    vertices (list of (x,y,z) bytes), num_anims, animations.
    """
    meshes = meshes or []
    inner = bytearray()

    inner += _pad_fixed(model_name.encode("ascii"), 16)
    inner += struct.pack("<h", thread_id)
    inner += struct.pack("<H", len(meshes))
    inner += struct.pack("<I", 0x18)
    assert len(inner) == 0x18

    header_starts = []
    for _ in meshes:
        header_starts.append(len(inner))
        inner += b"\x00" * _MESH_HEADER_SIZE

    for m, hs in zip(meshes, header_starts):
        name = m.get("name", "mesh")
        inner[hs:hs + 16] = _pad_fixed(name.encode("ascii"), 16)
        struct.pack_into("<h", inner, hs + 20, m.get("lod_distance", 1000))
        struct.pack_into("<H", inner, hs + 22, m.get("billboard", 0))
        scale = m.get("scale", (1.0, 1.0, 1.0))
        struct.pack_into("<h", inner, hs + 24, int(scale[0] * _GTE_SCALE_SMALL))
        struct.pack_into("<h", inner, hs + 26, int(scale[1] * _GTE_SCALE_SMALL))
        struct.pack_into("<h", inner, hs + 28, int(scale[2] * _GTE_SCALE_SMALL))

        _align4(inner)

        ptr_cmd = len(inner)
        struct.pack_into("<I", inner, hs + 0x20, ptr_cmd)
        inner += struct.pack("<I", m.get("unk_num", 16))

        for cmd_raw in m.get("commands", []):
            inner += struct.pack("<I", cmd_raw & 0xFFFFFFFF)

        inner += struct.pack("<I", 0xFFFFFFFF)
        _align4(inner)

        tls = m.get("texture_layouts", [])
        ptr_tex = 0

        if tls:
            ptr_tex = len(inner)
            tp_start = len(inner)
            inner += b"\x00" * (4 * len(tls))
            addrs = []
            for tl in tls:
                addrs.append(len(inner))
                inner += _encode_texture_layout(tl)

            for i, addr in enumerate(addrs):
                struct.pack_into("<I", inner, tp_start + i * 4, addr)

            _align4(inner)

        struct.pack_into("<I", inner, hs + 0x28, ptr_tex)

        ptr_clut = len(inner)
        struct.pack_into("<I", inner, hs + 0x2C, ptr_clut)

        for c in m.get("colors", [(0, 0, 0, 0)]):
            inner += bytes((c[0], c[1], c[2], c[3] if len(c) > 3 else 0))

        _align4(inner)

        animations = m.get("animations")

        if animations:
            struct.pack_into("<I", inner, hs + 0x34, len(animations))
            _write_animations(inner, hs, animations)
        else:
            num_anims_raw = m.get("num_anims", 0)
            struct.pack_into("<I", inner, hs + 0x34, num_anims_raw)

            if num_anims_raw == 0:
                ptr_frame = len(inner)
                struct.pack_into("<I", inner, hs + 0x24, ptr_frame)
                ox, oy, oz = m.get("offset", (0.0, 0.0, 0.0))
                inner += struct.pack(
                    "<hhh",
                    *[int(v * _GTE_SCALE_SMALL) for v in (ox, oy, oz)],
                )
                inner += struct.pack("<H", 0)
                inner += b"\x00" * 16
                inner += struct.pack("<I", 0x1C)

                for v in m.get("vertices", []):
                    inner += bytes((v[0] & 0xFF, v[1] & 0xFF, v[2] & 0xFF))

                _align4(inner)

    outer = bytearray()
    outer += struct.pack("<I", len(inner))
    outer += inner
    outer += struct.pack("<I", 0)
    return bytes(outer)
