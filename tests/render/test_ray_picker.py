# coding: utf-8

import numpy as np
import pytest

from paintjob_designer.render.orbit_camera import OrbitCamera
from paintjob_designer.render.ray_picker import RayTrianglePicker


@pytest.fixture
def picker():
    return RayTrianglePicker()


@pytest.fixture
def camera():
    """Orbit camera aimed at the origin from +Z, yaw/pitch zeroed so picks
    through the viewport center hit the (0,0,0) plane.
    """
    cam = OrbitCamera(default_yaw=0.0, default_pitch=0.0, default_distance=3.0)
    cam.reset()
    return cam


@pytest.fixture
def triangle_at_origin() -> np.ndarray:
    """One large triangle in the z=0 plane straddling the origin."""
    return np.array([
        [-1.0, -1.0, 0.0],
        [ 1.0, -1.0, 0.0],
        [ 0.0,  1.0, 0.0],
    ], dtype=np.float32)


class TestCenterPick:

    def test_clicking_center_hits_center_triangle(self, picker, camera, triangle_at_origin):
        hit = picker.pick(triangle_at_origin, camera, 50, 50, 100, 100)

        assert hit is not None
        assert hit.triangle_index == 0

    def test_barycentric_sums_to_one(self, picker, camera, triangle_at_origin):
        hit = picker.pick(triangle_at_origin, camera, 50, 50, 100, 100)

        total = sum(hit.barycentric)
        assert abs(total - 1.0) < 1e-4


class TestMiss:

    def test_click_outside_triangle_returns_none(self, picker, camera):
        # One small triangle near the origin; click a far corner of the viewport
        # (way off the triangle's screen-space footprint).
        positions = np.array([
            [-0.1, -0.1, 0.0],
            [ 0.1, -0.1, 0.0],
            [ 0.0,  0.1, 0.0],
        ], dtype=np.float32)

        hit = picker.pick(positions, camera, 2, 2, 100, 100)

        assert hit is None

    def test_empty_mesh_returns_none(self, picker, camera):
        hit = picker.pick(
            np.zeros((0, 3), dtype=np.float32), camera, 50, 50, 100, 100,
        )

        assert hit is None

    def test_degenerate_viewport_returns_none(self, picker, camera, triangle_at_origin):
        hit = picker.pick(triangle_at_origin, camera, 0, 0, 0, 0)

        assert hit is None


class TestClosestWins:

    def test_nearer_triangle_is_picked(self, picker, camera):
        # Two triangles along the camera's line of sight — near one at z=1,
        # far one at z=-1. The click must hit the near one.
        near_tri = np.array([
            [-1.0, -1.0, 1.0],
            [ 1.0, -1.0, 1.0],
            [ 0.0,  1.0, 1.0],
        ], dtype=np.float32)
        far_tri = np.array([
            [-1.0, -1.0, -1.0],
            [ 1.0, -1.0, -1.0],
            [ 0.0,  1.0, -1.0],
        ], dtype=np.float32)

        positions = np.vstack([near_tri, far_tri])

        hit = picker.pick(positions, camera, 50, 50, 100, 100)

        assert hit is not None
        assert hit.triangle_index == 0


class TestBackfaceTolerated:

    def test_back_facing_triangle_is_still_pickable(self, picker, camera):
        # Winding flipped so the face normal points away from the camera.
        # CTR meshes are double-sided; the picker must agree with the
        # renderer (which disables GL_CULL_FACE).
        positions = np.array([
            [-1.0, -1.0, 0.0],
            [ 0.0,  1.0, 0.0],
            [ 1.0, -1.0, 0.0],
        ], dtype=np.float32)

        hit = picker.pick(positions, camera, 50, 50, 100, 100)

        assert hit is not None
