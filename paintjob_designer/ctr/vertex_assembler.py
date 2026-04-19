# coding: utf-8

from paintjob_designer.models import (
    AssembledMesh,
    CtrMesh,
    Vector3b,
    Vector3f,
)


_STACK_SIZE = 256
_RING_SIZE = 4


class VertexAssembler:
    """Walks a `CtrMesh`'s draw-command tristrip stream and emits flat triangles.

    Port of `CtrMesh.cs:GetVertexBuffer()` in ctr-tools.

    The CTR renderer draws from a 256-slot vertex stack. Each draw command either
    pushes one vertex from the packed array into a stack slot (default) or reuses a
    previously written slot (`stack_vertex` flag). A 4-slot ring buffer holds the last
    four vertices/colors/tex-layouts; once we have at least 3 (strip_length >= 2), each
    subsequent command closes another triangle in the strip. `new_tristrip` resets the
    ring; `swap_vertex` swaps slots 0 and 1; `flip_normal` reverses the last two verts
    of the emitted triangle.

    The emitted positions/uvs are per-triangle in the same order ctr-tools produces
    (post-`verts.Reverse` pass).
    """

    def assemble(self, mesh: CtrMesh, frame=None) -> AssembledMesh:
        """Emit triangles for `mesh`'s draw stream.

        Uses `mesh.frame` by default — suitable for static meshes and for the
        initial pose of animated ones. Pass a specific `CtrFrame` (e.g. from
        `mesh.anims[i].frames[j]`) to assemble a different keyframe during
        playback without mutating the mesh.
        """
        target_frame = frame if frame is not None else mesh.frame
        if not target_frame.vertices:
            return AssembledMesh()

        world_verts = self._decompress_vertices(
            target_frame.vertices, target_frame.offset, mesh.scale,
        )

        result = AssembledMesh()

        stack: list[tuple[float, float, float]] = [(0.0, 0.0, 0.0)] * _STACK_SIZE
        temp_pos: list[tuple[float, float, float]] = [(0.0, 0.0, 0.0)] * _RING_SIZE
        temp_uv: list[tuple[int, int]] = [(0, 0)] * _RING_SIZE
        temp_tex: list[int] = [0] * _RING_SIZE
        temp_color: list[tuple[float, float, float]] = [(1.0, 1.0, 1.0)] * _RING_SIZE

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
            temp_color[3] = self._color_for_draw(mesh, draw)

            if draw.swap_vertex:
                temp_pos[1] = temp_pos[0]
                temp_uv[1] = temp_uv[0]
                temp_tex[1] = temp_tex[0]
                temp_color[1] = temp_color[0]

            if draw.new_tristrip:
                strip_length = 0

            if strip_length >= 2:
                self._emit_triangle(result, temp_pos, temp_color, mesh, draw)

            strip_length += 1

        return result

    def _uv_for_draw(self, mesh: CtrMesh, draw, corner: int) -> tuple[int, int]:
        """UV of the given TextureLayout corner (0..3) for this draw; (0,0) if untextured.

        ctr-tools uses only corners 0..2 when emitting triangles — corner 3 is never
        consumed — so this is really a helper for slot 3 of the ring (which slides down
        and only the lower slots are read out).
        """
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
        mesh: CtrMesh,
        draw,
    ) -> None:
        # ctr-tools emits 3 verts in z = 2, 1, 0 order, then optionally swaps the last
        # two for flip_normal, then reverses the whole triangle at the end. We compose
        # that here so the final output order is `[reversed → [1,2,3]]` for normal and
        # `[reversed → [2,1,3]]` for flip_normal.
        positions = [temp_pos[z + 1] for z in (2, 1, 0)]
        colors = [temp_color[z + 1] for z in (2, 1, 0)]

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

        positions.reverse()
        uvs.reverse()
        colors.reverse()

        result.positions.extend(positions)
        result.uvs.extend(uvs)
        result.texture_layout_indices.append(draw.tex_index)
        result.gouraud_colors.extend(colors)

    def _color_for_draw(self, mesh: CtrMesh, draw) -> tuple[float, float, float]:
        """Normalized RGB for `draw.color_index` into the mesh's Gouraud table.

        Falls back to white (1,1,1) when the index is out of range — some .ctr
        files set color_index on draws whose mesh has no color table.
        """
        if draw.color_index >= len(mesh.gouraud_colors):
            return 1.0, 1.0, 1.0

        c = mesh.gouraud_colors[draw.color_index]
        return c.r / 255.0, c.g / 255.0, c.b / 255.0

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
