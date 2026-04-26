# coding: utf-8

import numpy as np

from paintjob_designer.models import BlendingMode


class BlendModeGrouper:
    """Builds per-blend-mode vertex-index arrays for `glDrawElements`.

    The kart viewer uploads one big interleaved VBO of triangles ordered
    by the assembler. To render PSX semi-transparency correctly each blend
    mode needs its own draw pass with different `glBlendFunc`/`glBlendEquation`
    state. This grouper turns the per-triangle blend-mode list into one
    EBO per mode (each EBO indexes into the VBO at vertex granularity:
    `[3T, 3T+1, 3T+2]` for every triangle T using that mode).
    """

    _VERTICES_PER_TRIANGLE = 3

    def group_triangle_indices(
        self, blend_modes: list[BlendingMode],
    ) -> dict[BlendingMode, np.ndarray]:
        """Return a `{mode: u32 vertex-index array}` map covering every triangle.

        Modes with no triangles are omitted from the result (the renderer
        skips empty draw passes anyway).
        """
        # Collect per-mode triangle indices in one pass over the blend list.
        per_mode: dict[BlendingMode, list[int]] = {}
        for tri_idx, mode in enumerate(blend_modes):
            per_mode.setdefault(mode, []).append(tri_idx)

        return {
            mode: self._triangle_indices_to_vertex_indices(triangles)
            for mode, triangles in per_mode.items()
            if triangles
        }

    def _triangle_indices_to_vertex_indices(
        self, triangle_indices: list[int],
    ) -> np.ndarray:
        # Each triangle T owns vertices [3T, 3T+1, 3T+2] in the flat VBO;
        # build the index array via vectorised arithmetic so the glDrawElements
        # call can run straight off the result without further reshaping.
        base = np.array(triangle_indices, dtype=np.uint32) * self._VERTICES_PER_TRIANGLE
        offsets = np.arange(self._VERTICES_PER_TRIANGLE, dtype=np.uint32)
        return (base[:, None] + offsets[None, :]).ravel()
