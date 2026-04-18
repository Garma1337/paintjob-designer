# coding: utf-8

import pytest

from paintjob_designer.models import AssembledMesh, TextureLayout


class TestMap:

    def test_emits_three_uvs_per_triangle(self, atlas_uv_mapper):
        assembled = AssembledMesh(
            positions=[(0.0, 0.0, 0.0)] * 3,
            uvs=[(0, 0), (10, 0), (0, 10)],
            texture_layout_indices=[1],
        )
        layouts = [TextureLayout(page_x=0, page_y=0)]

        uvs = atlas_uv_mapper.map(assembled, layouts)

        assert len(uvs) == 3

    def test_page_offset_shifts_atlas_u_by_256_per_page_index(self, atlas_uv_mapper):
        # Page (3, 0): base atlas_u = 3*256 = 768. UV byte 100 -> atlas_u = 868.
        assembled = AssembledMesh(
            positions=[(0.0, 0.0, 0.0)] * 3,
            uvs=[(100, 0), (0, 0), (0, 0)],
            texture_layout_indices=[1],
        )
        layouts = [TextureLayout(page_x=3, page_y=0)]

        atlas_u, atlas_v = atlas_uv_mapper.map(assembled, layouts)[0]

        assert atlas_u == pytest.approx(868 / 4096)
        assert atlas_v == pytest.approx(0.0)

    def test_page_y_offset_shifts_atlas_v_by_256(self, atlas_uv_mapper):
        assembled = AssembledMesh(
            positions=[(0.0, 0.0, 0.0)] * 3,
            uvs=[(0, 50), (0, 0), (0, 0)],
            texture_layout_indices=[1],
        )
        layouts = [TextureLayout(page_x=0, page_y=1)]

        atlas_u, atlas_v = atlas_uv_mapper.map(assembled, layouts)[0]

        assert atlas_u == pytest.approx(0.0)
        assert atlas_v == pytest.approx(306 / 512)

    def test_untextured_triangle_yields_sentinel_uvs(self, atlas_uv_mapper):
        # Untextured triangles get the negative-U sentinel so the fragment
        # shader can branch on it and flat-fill instead of sampling the atlas.
        assembled = AssembledMesh(
            positions=[(0.0, 0.0, 0.0)] * 3,
            uvs=[(100, 100)] * 3,
            texture_layout_indices=[0],
        )

        uvs = atlas_uv_mapper.map(assembled, [])

        sentinel = atlas_uv_mapper.UNTEXTURED_SENTINEL
        assert uvs == [sentinel, sentinel, sentinel]

    def test_max_uv_reaches_right_edge_of_page(self, atlas_uv_mapper):
        # UV byte 255 at page (15, 1) -> atlas_u = 15*256 + 255 = 4095 -> 4095/4096.
        assembled = AssembledMesh(
            positions=[(0.0, 0.0, 0.0)] * 3,
            uvs=[(255, 255), (0, 0), (0, 0)],
            texture_layout_indices=[1],
        )
        layouts = [TextureLayout(page_x=15, page_y=1)]

        atlas_u, atlas_v = atlas_uv_mapper.map(assembled, layouts)[0]

        assert atlas_u == pytest.approx(4095 / 4096)
        assert atlas_v == pytest.approx(511 / 512)

    def test_multiple_triangles_each_use_their_own_tex_index(self, atlas_uv_mapper):
        assembled = AssembledMesh(
            positions=[(0.0, 0.0, 0.0)] * 6,
            uvs=[(10, 0), (0, 0), (0, 0), (10, 0), (0, 0), (0, 0)],
            texture_layout_indices=[1, 2],
        )
        layouts = [
            TextureLayout(page_x=0, page_y=0),   # triangle 0
            TextureLayout(page_x=5, page_y=1),   # triangle 1
        ]

        uvs = atlas_uv_mapper.map(assembled, layouts)

        # Triangle 0 first vertex: page (0, 0), uv_byte (10, 0).
        assert uvs[0] == pytest.approx((10 / 4096, 0))
        # Triangle 1 first vertex: page (5, 1), uv_byte (10, 0) -> atlas (1290, 256).
        assert uvs[3] == pytest.approx(((5 * 256 + 10) / 4096, 256 / 512))
