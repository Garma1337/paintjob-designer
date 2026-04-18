# coding: utf-8

from paintjob_designer.models import AssembledMesh, TextureLayout
from paintjob_designer.render.atlas_renderer import AtlasRenderer


# Each VRAM "page" is 64 VRAM px wide = 256 atlas px wide in 4bpp-stretched space;
# and 256 VRAM px tall. Byte-space UVs from a TextureLayout are already in
# 4bpp-texel coordinates within the page, so combining the two is a straight add.
_PAGE_STRIDE_ATLAS_X = 256
_PAGE_STRIDE_ATLAS_Y = 256


class AtlasUvMapper:
    """Turns per-vertex byte-space UVs into normalized 0..1 atlas UVs.

    `VertexAssembler` hands out UVs in the original byte space of each
    `TextureLayout` (0..255 within a 256×256 texture page). The atlas the 3D
    viewer samples from is a single 4096×512 RGBA image assembled by
    `AtlasRenderer`, where every 4bpp texel occupies one atlas pixel and VRAM
    pages lay out side-by-side horizontally. This class bridges the two so the
    GL texture sample lands on the right pixel.

    Untextured triangles (`tex_index == 0`) get the sentinel UV
    `UNTEXTURED_SENTINEL = (-1.0, -1.0)`. The fragment shader recognizes the
    negative U and draws a flat fill instead of sampling the texture — without
    that, those triangles would sample the top-left of the atlas (often
    transparent) and get discarded by the alpha test.
    """

    ATLAS_WIDTH = AtlasRenderer.ATLAS_WIDTH
    ATLAS_HEIGHT = AtlasRenderer.ATLAS_HEIGHT
    UNTEXTURED_SENTINEL = (-1.0, -1.0)

    def map(
        self,
        assembled: AssembledMesh,
        texture_layouts: list[TextureLayout],
    ) -> list[tuple[float, float]]:
        uvs: list[tuple[float, float]] = []

        for triangle_index in range(assembled.triangle_count):
            tex_index = assembled.texture_layout_indices[triangle_index]

            if tex_index == 0:
                uvs.extend([self.UNTEXTURED_SENTINEL] * 3)
                continue

            tl = texture_layouts[tex_index - 1]
            base_u = tl.page_x * _PAGE_STRIDE_ATLAS_X
            base_v = tl.page_y * _PAGE_STRIDE_ATLAS_Y

            for vertex_in_triangle in range(3):
                u_byte, v_byte = assembled.uvs[triangle_index * 3 + vertex_in_triangle]
                uvs.append((
                    (base_u + u_byte) / self.ATLAS_WIDTH,
                    (base_v + v_byte) / self.ATLAS_HEIGHT,
                ))

        return uvs
