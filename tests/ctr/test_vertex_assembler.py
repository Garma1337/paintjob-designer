# coding: utf-8

import pytest

from paintjob_designer.models import (
    CtrDraw,
    CtrFrame,
    CtrMesh,
    TextureLayout,
    Vector3b,
    Vector3f,
)


def _cmd(
    new_tristrip: bool = False,
    swap_vertex: bool = False,
    flip_normal: bool = False,
    stack_vertex: bool = False,
    stack_index: int = 0,
    color_index: int = 0,
    tex_index: int = 0,
) -> int:
    raw = 0
    if new_tristrip:
        raw |= 1 << 31

    if swap_vertex:
        raw |= 1 << 30

    if flip_normal:
        raw |= 1 << 29

    if stack_vertex:
        raw |= 1 << 26

    raw |= (stack_index & 0xFF) << 16
    raw |= (color_index & 0x7F) << 9
    raw |= tex_index & 0x1FF
    return raw


def _mesh(
    commands: list[int],
    vertex_bytes: list[tuple[int, int, int]],
    layouts: list[TextureLayout] | None = None,
) -> CtrMesh:
    return CtrMesh(
        scale=Vector3f(1.0, 1.0, 1.0),
        draw_commands=[CtrDraw(raw=c) for c in commands],
        texture_layouts=layouts or [],
        frame=CtrFrame(
            offset=Vector3f(0.0, 0.0, 0.0),
            vertices=[Vector3b(*v) for v in vertex_bytes],
        ),
    )


class TestAssemblerEdges:

    def test_empty_mesh_yields_empty_assembly(self, vertex_assembler):
        result = vertex_assembler.assemble(CtrMesh())

        assert result.triangle_count == 0
        assert result.positions == []
        assert result.uvs == []
        assert result.texture_layout_indices == []

    def test_animated_mesh_without_vertices_yields_empty_assembly(self, vertex_assembler):
        # is_animated + empty frame.vertices: parser leaves verts empty until
        # animation decoding lands later. Assembler must not crash.
        mesh = CtrMesh(
            is_animated=True,
            draw_commands=[CtrDraw(raw=_cmd(new_tristrip=True, stack_index=0))],
        )

        result = vertex_assembler.assemble(mesh)

        assert result.triangle_count == 0

    def test_skips_commands_with_out_of_range_tex_index(self, vertex_assembler):
        # tex_index=5 but only 1 layout present -> stop before emitting anything.
        commands = [
            _cmd(new_tristrip=True, stack_index=0),
            _cmd(stack_index=1),
            _cmd(stack_index=2, tex_index=5),
        ]
        mesh = _mesh(
            commands,
            [(0, 0, 0), (255, 0, 0), (0, 255, 0)],
            layouts=[TextureLayout()],
        )

        result = vertex_assembler.assemble(mesh)

        assert result.triangle_count == 0


class TestTristripBasics:

    def test_single_triangle_positions_are_in_vertex_order(self, vertex_assembler):
        # After the batch-reverse step, a plain tristrip's first triangle comes out
        # as [v0, v1, v2] (the raw three consumed vertices in order).
        mesh = _mesh(
            [
                _cmd(new_tristrip=True, stack_index=0),
                _cmd(stack_index=1),
                _cmd(stack_index=2),
            ],
            [(0, 0, 0), (255, 0, 0), (0, 255, 0)],
        )

        result = vertex_assembler.assemble(mesh)

        assert result.triangle_count == 1
        # The Y/Z swap in CalculateFinalVertex maps byte (0, 255, 0) -> world (0, 0, 1).
        assert result.positions[0] == pytest.approx((0.0, 0.0, 0.0))
        assert result.positions[1] == pytest.approx((1.0, 0.0, 0.0))
        assert result.positions[2] == pytest.approx((0.0, 0.0, 1.0))

    def test_strip_of_two_triangles_shares_two_vertices(self, vertex_assembler):
        mesh = _mesh(
            [
                _cmd(new_tristrip=True, stack_index=0),
                _cmd(stack_index=1),
                _cmd(stack_index=2),  # emits [v0, v1, v2]
                _cmd(stack_index=3),  # emits [v1, v2, v3]
            ],
            [(0, 0, 0), (255, 0, 0), (0, 255, 0), (0, 0, 255)],
        )

        result = vertex_assembler.assemble(mesh)

        assert result.triangle_count == 2
        # Triangle 0: v0, v1, v2
        assert result.positions[0:3] == [
            pytest.approx((0.0, 0.0, 0.0)),
            pytest.approx((1.0, 0.0, 0.0)),
            pytest.approx((0.0, 0.0, 1.0)),
        ]
        # Triangle 1: v1, v2, v3
        # v3 = Vector3b(0, 0, 255) -> (0, 255/255, 0/255) with Y/Z swap = (0, 1, 0)
        assert result.positions[3:6] == [
            pytest.approx((1.0, 0.0, 0.0)),
            pytest.approx((0.0, 0.0, 1.0)),
            pytest.approx((0.0, 1.0, 0.0)),
        ]

    def test_new_tristrip_resets_the_strip(self, vertex_assembler):
        # Without the reset, 5 commands would produce 3 triangles.
        # With a reset at command 3, we only get 1 triangle (from commands 0..2).
        mesh = _mesh(
            [
                _cmd(new_tristrip=True, stack_index=0),
                _cmd(stack_index=1),
                _cmd(stack_index=2),                   # emits triangle
                _cmd(new_tristrip=True, stack_index=3),  # resets
                _cmd(stack_index=4),                   # still strip_length < 2
            ],
            [(0, 0, 0), (255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)],
        )

        result = vertex_assembler.assemble(mesh)

        assert result.triangle_count == 1


class TestFlipNormalAndSwap:

    def test_flip_normal_swaps_last_two_vertices_of_triangle(self, vertex_assembler):
        # Without flip: first triangle = [v0, v1, v2]. With flip on cmd 2: [v1, v0, v2].
        mesh = _mesh(
            [
                _cmd(new_tristrip=True, stack_index=0),
                _cmd(stack_index=1),
                _cmd(stack_index=2, flip_normal=True),
            ],
            [(0, 0, 0), (255, 0, 0), (0, 255, 0)],
        )

        result = vertex_assembler.assemble(mesh)

        assert result.triangle_count == 1
        assert result.positions[0] == pytest.approx((1.0, 0.0, 0.0))   # v1
        assert result.positions[1] == pytest.approx((0.0, 0.0, 0.0))   # v0
        assert result.positions[2] == pytest.approx((0.0, 0.0, 1.0))   # v2

    def test_swap_vertex_changes_emitted_positions(self, vertex_assembler):
        # Compare with/without swap_vertex on the triangle-emitting command.
        # v0 must be non-zero so the swap (which replaces slot-1 with slot-0) has
        # a visible effect on the output positions.
        verts = [(128, 0, 0), (255, 0, 0), (0, 255, 0)]

        plain = vertex_assembler.assemble(_mesh(
            [
                _cmd(new_tristrip=True, stack_index=0),
                _cmd(stack_index=1),
                _cmd(stack_index=2),
            ],
            verts,
        ))
        swapped = vertex_assembler.assemble(_mesh(
            [
                _cmd(new_tristrip=True, stack_index=0),
                _cmd(stack_index=1),
                _cmd(stack_index=2, swap_vertex=True),
            ],
            verts,
        ))

        assert plain.positions != swapped.positions


class TestStackVertexReuse:

    def test_stack_vertex_does_not_consume_an_array_vertex(self, vertex_assembler):
        # 3 consumes + 1 stack-vertex reuse = 2 triangles from 3 source vertices.
        mesh = _mesh(
            [
                _cmd(new_tristrip=True, stack_index=0),
                _cmd(stack_index=1),
                _cmd(stack_index=2),                   # triangle 0
                _cmd(stack_vertex=True, stack_index=0),  # reuse v0 from stack
            ],
            [(0, 0, 0), (255, 0, 0), (0, 255, 0)],
        )

        result = vertex_assembler.assemble(mesh)

        assert result.triangle_count == 2
        # Triangle 1 uses v1, v2, then stack[0] = v0.
        assert result.positions[3] == pytest.approx((1.0, 0.0, 0.0))   # v1
        assert result.positions[4] == pytest.approx((0.0, 0.0, 1.0))   # v2
        assert result.positions[5] == pytest.approx((0.0, 0.0, 0.0))   # v0


class TestTexturedTriangle:

    def test_textured_triangle_emits_uvs_and_records_tex_index(self, vertex_assembler):
        tl = TextureLayout(
            uv0_u=10, uv0_v=20,
            uv1_u=30, uv1_v=40,
            uv2_u=50, uv2_v=60,
            palette_x=7, palette_y=255,
        )
        mesh = _mesh(
            [
                _cmd(new_tristrip=True, stack_index=0, tex_index=1),
                _cmd(stack_index=1, tex_index=1),
                _cmd(stack_index=2, tex_index=1),
            ],
            [(0, 0, 0), (255, 0, 0), (0, 255, 0)],
            layouts=[tl],
        )

        result = vertex_assembler.assemble(mesh)

        assert result.triangle_count == 1
        assert result.texture_layout_indices == [1]
        # After the reverse, the UVs come out in corner-0/1/2 order.
        assert result.uvs[0] == (10, 20)
        assert result.uvs[1] == (30, 40)
        assert result.uvs[2] == (50, 60)

    def test_untextured_triangle_uvs_are_zero(self, vertex_assembler):
        mesh = _mesh(
            [
                _cmd(new_tristrip=True, stack_index=0),
                _cmd(stack_index=1),
                _cmd(stack_index=2),
            ],
            [(0, 0, 0), (255, 0, 0), (0, 255, 0)],
        )

        result = vertex_assembler.assemble(mesh)

        assert result.uvs == [(0, 0), (0, 0), (0, 0)]
        assert result.texture_layout_indices == [0]


class TestPositionTransform:

    def test_offset_and_scale_applied_to_world_position(self, vertex_assembler):
        mesh = CtrMesh(
            scale=Vector3f(10.0, 20.0, 30.0),
            draw_commands=[CtrDraw(raw=c) for c in [
                _cmd(new_tristrip=True, stack_index=0),
                _cmd(stack_index=1),
                _cmd(stack_index=2),
            ]],
            frame=CtrFrame(
                offset=Vector3f(0.5, -0.25, 0.75),
                vertices=[Vector3b(0, 0, 0), Vector3b(255, 0, 0), Vector3b(0, 255, 0)],
            ),
        )

        result = vertex_assembler.assemble(mesh)

        # vert 0 bytes (0,0,0) -> world ((0/255+0.5)*10, (0/255-0.25)*20, (0/255+0.75)*30)
        # Y/Z swap: world_y uses v.z, world_z uses v.y. For v0 both are 0.
        assert result.positions[0] == pytest.approx((5.0, -5.0, 22.5))
