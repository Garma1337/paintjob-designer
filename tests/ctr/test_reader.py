# coding: utf-8

import pytest

from paintjob_designer.models import BitDepth, BlendingMode
from tests.conftest import build_ctr_bytes


def _triangle_commands(
    tex_index: int = 0,
    color_index: int = 0,
) -> list[int]:
    """Three draw commands that form one triangle (no stack reuse)."""
    base = (color_index & 0x7F) << 9 | (tex_index & 0x1FF)

    # first vertex: NewTriStrip flag (bit 31) + stack slot 0
    cmd0 = (1 << 31) | (0 << 16) | base
    cmd1 = (1 << 16) | base
    cmd2 = (2 << 16) | base
    return [cmd0, cmd1, cmd2]


class TestCtrModelReader:

    def test_reads_model_header(self, ctr_model_reader):
        data = build_ctr_bytes(model_name="crash", thread_id=7, meshes=[
            {
                "name": "crash_hi",
                "commands": _triangle_commands(),
                "vertices": [(1, 2, 3), (4, 5, 6), (7, 8, 9)],
            },
        ])

        model = ctr_model_reader.read(data)

        assert model.name == "crash"
        assert model.thread_id == 7
        assert len(model.meshes) == 1

    def test_reads_mesh_header_fields(self, ctr_model_reader):
        data = build_ctr_bytes(meshes=[
            {
                "name": "x_hi",
                "lod_distance": 1234,
                "billboard": 1,
                "scale": (2.0, 3.0, 4.0),
                "commands": _triangle_commands(),
                "vertices": [(0, 0, 0)] * 3,
            },
        ])

        mesh = ctr_model_reader.read(data).meshes[0]

        assert mesh.name == "x_hi"
        assert mesh.lod_distance == 1234
        assert mesh.billboard == 1
        assert mesh.scale.x == pytest.approx(2.0)
        assert mesh.scale.y == pytest.approx(3.0)
        assert mesh.scale.z == pytest.approx(4.0)

    def test_reads_commands_until_terminator(self, ctr_model_reader):
        data = build_ctr_bytes(meshes=[
            {"commands": _triangle_commands(), "vertices": [(0, 0, 0)] * 3},
        ])

        mesh = ctr_model_reader.read(data).meshes[0]

        assert len(mesh.draw_commands) == 3
        assert mesh.draw_commands[0].new_tristrip is True
        assert mesh.draw_commands[0].stack_index == 0
        assert mesh.draw_commands[1].stack_index == 1
        assert mesh.draw_commands[2].stack_index == 2

    def test_reads_gouraud_colors_based_on_max_index(self, ctr_model_reader):
        commands = _triangle_commands(color_index=3)
        data = build_ctr_bytes(meshes=[
            {
                "commands": commands,
                "colors": [(10, 11, 12, 0), (20, 21, 22, 0), (30, 31, 32, 0), (40, 41, 42, 0)],
                "vertices": [(0, 0, 0)] * 3,
            },
        ])

        mesh = ctr_model_reader.read(data).meshes[0]

        # max color_index seen = 3, so 4 colors are loaded.
        assert len(mesh.gouraud_colors) == 4
        assert mesh.gouraud_colors[3].r == 40
        assert mesh.gouraud_colors[3].g == 41
        assert mesh.gouraud_colors[3].b == 42

    def test_reads_texture_layouts_with_palette_and_page_fields(self, ctr_model_reader):
        data = build_ctr_bytes(meshes=[
            {
                "commands": _triangle_commands(tex_index=1),
                "texture_layouts": [{
                    "uv0_u": 10, "uv0_v": 20,
                    "uv1_u": 30, "uv1_v": 40,
                    "uv2_u": 50, "uv2_v": 60,
                    "uv3_u": 70, "uv3_v": 80,
                    "palette_x": 7, "palette_y": 255,
                    "page_x": 5, "page_y": 1,
                    "blending": BlendingMode.Standard,
                    "bpp": BitDepth.Bit4,
                }],
                "vertices": [(0, 0, 0)] * 3,
            },
        ])

        mesh = ctr_model_reader.read(data).meshes[0]

        assert len(mesh.texture_layouts) == 1
        tl = mesh.texture_layouts[0]
        assert (tl.uv0_u, tl.uv0_v) == (10, 20)
        assert (tl.uv3_u, tl.uv3_v) == (70, 80)
        assert tl.palette_x == 7
        assert tl.palette_y == 255
        assert tl.page_x == 5
        assert tl.page_y == 1
        assert tl.blending == BlendingMode.Standard
        assert tl.bpp == BitDepth.Bit4

    def test_reads_static_frame_vertices(self, ctr_model_reader):
        data = build_ctr_bytes(meshes=[
            {
                "commands": _triangle_commands(),
                "offset": (0.5, -0.25, 1.0),
                "vertices": [(10, 20, 30), (40, 50, 60), (70, 80, 90)],
            },
        ])

        mesh = ctr_model_reader.read(data).meshes[0]

        assert mesh.is_animated is False
        assert mesh.frame.offset.x == pytest.approx(0.5)
        assert mesh.frame.offset.y == pytest.approx(-0.25)
        assert mesh.frame.offset.z == pytest.approx(1.0)
        assert len(mesh.frame.vertices) == 3
        assert (mesh.frame.vertices[2].x, mesh.frame.vertices[2].y, mesh.frame.vertices[2].z) == (70, 80, 90)

    def test_animated_mesh_flag_without_anim_data_leaves_frame_empty(self, ctr_model_reader):
        # num_anims > 0 but no animations dict -> builder leaves ptr_anims=0,
        # reader sees the flag and skips frame parsing.
        data = build_ctr_bytes(meshes=[
            {
                "commands": _triangle_commands(),
                "num_anims": 4,
            },
        ])

        mesh = ctr_model_reader.read(data).meshes[0]

        assert mesh.is_animated is True
        assert mesh.frame.vertices == []

    def test_animated_mesh_decompresses_first_frame_from_bitstream(self, ctr_model_reader):
        # 3 vertices needed (max_verts = 3 from _triangle_commands).
        # Deltas: bits_*=0 for each of 3 verts -> 3 sign bits per vertex = 9 bits total.
        # All sign bits 0 -> temporal 0, so each vertex is just accumulated base pos.
        delta = {"bits_x": 0, "bits_y": 0, "bits_z": 0,
                 "pos_x": 5, "pos_y": 10, "pos_z": 15}

        data = build_ctr_bytes(meshes=[
            {
                "commands": _triangle_commands(),
                "animations": [
                    {
                        "name": "idle",
                        "deltas": [delta, delta, delta],
                        "frames": [
                            {
                                "offset": (0.0, 0.0, 0.0),
                                "bits": [0] * 9,  # 3 verts * 3 sign bits
                            },
                        ],
                    },
                ],
            },
        ])

        mesh = ctr_model_reader.read(data).meshes[0]

        assert mesh.is_animated is True
        assert len(mesh.frame.vertices) == 3
        # base_x accumulates by (pos_x << 1) = 10 each vertex.
        # Y/Z are swapped when storing: final Vector3b = (x, z, y) of accumulated bases.
        assert (mesh.frame.vertices[0].x, mesh.frame.vertices[0].y, mesh.frame.vertices[0].z) == (10, 15, 10)
        assert (mesh.frame.vertices[1].x, mesh.frame.vertices[1].y, mesh.frame.vertices[1].z) == (20, 30, 20)
        assert (mesh.frame.vertices[2].x, mesh.frame.vertices[2].y, mesh.frame.vertices[2].z) == (30, 45, 30)

    def test_animated_uncompressed_frame_reads_raw_vertex_bytes(self, ctr_model_reader):
        # ptr_deltas = 0 path: frame contains raw Vector3b bytes, no bitstream.
        data = build_ctr_bytes(meshes=[
            {
                "commands": _triangle_commands(),
                "animations": [
                    {
                        "name": "idle",
                        "num_verts_for_raw": 3,
                        "frames": [
                            {
                                "offset": (0.0, 0.0, 0.0),
                                "vertices": [(1, 2, 3), (4, 5, 6), (7, 8, 9)],
                            },
                        ],
                    },
                ],
            },
        ])

        mesh = ctr_model_reader.read(data).meshes[0]

        assert mesh.is_animated is True
        assert [(v.x, v.y, v.z) for v in mesh.frame.vertices] == [(1, 2, 3), (4, 5, 6), (7, 8, 9)]

    def test_stack_vertex_command_does_not_consume_an_array_vertex(self, ctr_model_reader):
        # 3 regular commands + 1 stack_vertex reuse => still only 3 vertices in the array.
        commands = _triangle_commands()
        stack_reuse = (1 << 26) | (0 << 16)  # stack_vertex flag, read slot 0
        commands.append(stack_reuse)

        data = build_ctr_bytes(meshes=[
            {"commands": commands, "vertices": [(1, 1, 1), (2, 2, 2), (3, 3, 3)]},
        ])

        mesh = ctr_model_reader.read(data).meshes[0]

        assert len(mesh.frame.vertices) == 3
