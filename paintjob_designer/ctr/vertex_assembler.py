# coding: utf-8

from paintjob_designer.constants import RGB_COMPONENT_MAX
from paintjob_designer.models import (
    AssembledMesh,
    BlendingMode,
    CtrMesh,
    Rgb888,
    Vector3b,
    Vector3f,
)


_STACK_SIZE = 256
_RING_SIZE = 4


class VertexAssembler:
    """Walks a `CtrMesh`'s draw-command tristrip stream and emits flat triangles."""

    def assemble(
        self,
        mesh: CtrMesh,
        frame=None,
        vertex_overrides: dict[int, Rgb888] | None = None,
    ) -> AssembledMesh:
        target_frame = frame if frame is not None else mesh.frame
        if not target_frame.vertices:
            return AssembledMesh()

        overrides = vertex_overrides or {}

        world_verts = self._decompress_vertices(
            target_frame.vertices, target_frame.offset, mesh.scale,
        )

        result = AssembledMesh()

        stack: list[tuple[float, float, float]] = [(0.0, 0.0, 0.0)] * _STACK_SIZE
        temp_pos: list[tuple[float, float, float]] = [(0.0, 0.0, 0.0)] * _RING_SIZE
        temp_uv: list[tuple[int, int]] = [(0, 0)] * _RING_SIZE
        temp_tex: list[int] = [0] * _RING_SIZE
        temp_color: list[tuple[float, float, float]] = [(1.0, 1.0, 1.0)] * _RING_SIZE
        temp_color_index: list[int] = [0] * _RING_SIZE

        vertex_index = 0
        strip_length = 0

        for draw in mesh.draw_commands:
            # Skip commands whose tex_index would overflow the texture-layout array.
            # Matches ctr-tools' guard in GetVertexBuffer.
            if draw.tex_index - 1 >= len(mesh.texture_layouts):
                break

            if not draw.stack_vertex:
                stack[draw.stack_index] = world_verts[vertex_index]
                vertex_index += 1

            temp_pos[0], temp_pos[1], temp_pos[2] = temp_pos[1], temp_pos[2], temp_pos[3]
            temp_pos[3] = stack[draw.stack_index]

            temp_uv[0], temp_uv[1], temp_uv[2] = temp_uv[1], temp_uv[2], temp_uv[3]
            temp_uv[3] = self._uv_for_draw(mesh, draw, corner=3)

            temp_tex[0], temp_tex[1], temp_tex[2] = temp_tex[1], temp_tex[2], temp_tex[3]
            temp_tex[3] = draw.tex_index

            temp_color[0], temp_color[1], temp_color[2] = temp_color[1], temp_color[2], temp_color[3]
            temp_color[3] = self._color_for_draw(mesh, draw, overrides)

            temp_color_index[0], temp_color_index[1], temp_color_index[2] = (
                temp_color_index[1], temp_color_index[2], temp_color_index[3]
            )
            temp_color_index[3] = draw.color_index

            if draw.swap_vertex:
                temp_pos[1] = temp_pos[0]
                temp_uv[1] = temp_uv[0]
                temp_tex[1] = temp_tex[0]
                temp_color[1] = temp_color[0]
                temp_color_index[1] = temp_color_index[0]

            if draw.new_tristrip:
                strip_length = 0

            if strip_length >= 2:
                self._emit_triangle(
                    result, temp_pos, temp_color, temp_color_index, mesh, draw,
                )

            strip_length += 1

        return result

    def _uv_for_draw(self, mesh: CtrMesh, draw, corner: int) -> tuple[int, int]:
        """UV of the given TextureLayout corner (0..3) for this draw; (0,0) if untextured."""
        if draw.tex_index == 0:
            return 0, 0

        tl = mesh.texture_layouts[draw.tex_index - 1]

        return ((tl.uv0_u, tl.uv0_v), (tl.uv1_u, tl.uv1_v),
                (tl.uv2_u, tl.uv2_v), (tl.uv3_u, tl.uv3_v))[corner]

    def _emit_triangle(
        self,
        result: AssembledMesh,
        temp_pos: list[tuple[float, float, float]],
        temp_color: list[tuple[float, float, float]],
        temp_color_index: list[int],
        mesh: CtrMesh,
        draw,
    ) -> None:
        # ctr-tools emits 3 verts in z = 2, 1, 0 order, then optionally swaps the last
        # two for flip_normal, then reverses the whole triangle at the end. We compose
        # that here so the final output order is `[reversed → [1,2,3]]` for normal and
        # `[reversed → [2,1,3]]` for flip_normal.
        positions = [temp_pos[z + 1] for z in (2, 1, 0)]
        colors = [temp_color[z + 1] for z in (2, 1, 0)]
        color_indices = [temp_color_index[z + 1] for z in (2, 1, 0)]

        if draw.tex_index != 0:
            tl = mesh.texture_layouts[draw.tex_index - 1]
            uvs = [(tl.uv0_u, tl.uv0_v), (tl.uv1_u, tl.uv1_v), (tl.uv2_u, tl.uv2_v)]
            # Pick corners in z = 2, 1, 0 order to match positions.
            uvs = [uvs[z] for z in (2, 1, 0)]
        else:
            uvs = [(0, 0), (0, 0), (0, 0)]

        if draw.flip_normal:
            positions[1], positions[2] = positions[2], positions[1]
            uvs[1], uvs[2] = uvs[2], uvs[1]
            colors[1], colors[2] = colors[2], colors[1]
            color_indices[1], color_indices[2] = color_indices[2], color_indices[1]

        positions.reverse()
        uvs.reverse()
        colors.reverse()
        color_indices.reverse()

        result.positions.extend(positions)
        result.uvs.extend(uvs)
        result.texture_layout_indices.append(draw.tex_index)
        result.gouraud_colors.extend(colors)
        result.gouraud_color_indices.append(
            (color_indices[0], color_indices[1], color_indices[2]),
        )

        if draw.tex_index != 0:
            result.blend_modes.append(
                mesh.texture_layouts[draw.tex_index - 1].blending,
            )
        else:
            result.blend_modes.append(BlendingMode.Standard)

    def _color_for_draw(
        self,
        mesh: CtrMesh,
        draw,
        overrides: dict[int, Rgb888],
    ) -> tuple[float, float, float]:
        """Normalized RGB for `draw.color_index` into the mesh's Gouraud table."""
        if draw.color_index >= len(mesh.gouraud_colors):
            return 1.0, 1.0, 1.0

        override = overrides.get(draw.color_index)
        if override is not None:
            return (
                override.r / RGB_COMPONENT_MAX,
                override.g / RGB_COMPONENT_MAX,
                override.b / RGB_COMPONENT_MAX,
            )

        c = mesh.gouraud_colors[draw.color_index]
        return (
            c.r / RGB_COMPONENT_MAX,
            c.g / RGB_COMPONENT_MAX,
            c.b / RGB_COMPONENT_MAX,
        )

    def _decompress_vertices(
        self,
        compressed: list[Vector3b],
        offset: Vector3f,
        scale: Vector3f,
    ) -> list[tuple[float, float, float]]:
        # Port of ctr-tools `CalculateFinalVertex`. Notice the Y/Z axis swap:
        # compressed.y feeds final z, compressed.z feeds final y.
        return [
            (
                (v.x / 255.0 + offset.x) * scale.x,
                (v.z / 255.0 + offset.y) * scale.y,
                (v.y / 255.0 + offset.z) * scale.z,
            )
            for v in compressed
        ]
