# coding: utf-8

import numpy as np

from paintjob_designer.models import BlendingMode
from paintjob_designer.render.blend_mode_grouper import BlendModeGrouper


class TestBlendModeGrouper:

    def setup_method(self) -> None:
        self._grouper = BlendModeGrouper()

    def test_single_mode_returns_one_bucket_with_all_vertices(self) -> None:
        modes = [BlendingMode.Standard] * 3

        groups = self._grouper.group_triangle_indices(modes)

        assert set(groups.keys()) == {BlendingMode.Standard}
        # 3 triangles × 3 verts = vertex indices 0..8.
        assert groups[BlendingMode.Standard].tolist() == list(range(9))

    def test_mixed_modes_split_into_per_mode_buckets(self) -> None:
        modes = [
            BlendingMode.Standard,
            BlendingMode.Translucent,
            BlendingMode.Standard,
            BlendingMode.Additive,
        ]

        groups = self._grouper.group_triangle_indices(modes)

        # Standard at triangles 0 and 2 → vertex indices [0,1,2, 6,7,8].
        assert groups[BlendingMode.Standard].tolist() == [0, 1, 2, 6, 7, 8]
        # Translucent at triangle 1 → [3, 4, 5].
        assert groups[BlendingMode.Translucent].tolist() == [3, 4, 5]
        # Additive at triangle 3 → [9, 10, 11].
        assert groups[BlendingMode.Additive].tolist() == [9, 10, 11]

    def test_modes_with_no_triangles_are_omitted(self) -> None:
        modes = [BlendingMode.Standard, BlendingMode.Standard]

        groups = self._grouper.group_triangle_indices(modes)

        assert BlendingMode.Translucent not in groups
        assert BlendingMode.Additive not in groups
        assert BlendingMode.Subtractive not in groups

    def test_empty_input_returns_empty_dict(self) -> None:
        assert self._grouper.group_triangle_indices([]) == {}

    def test_returned_arrays_are_uint32_for_glDrawElements(self) -> None:
        modes = [BlendingMode.Standard]

        groups = self._grouper.group_triangle_indices(modes)

        assert groups[BlendingMode.Standard].dtype == np.uint32
