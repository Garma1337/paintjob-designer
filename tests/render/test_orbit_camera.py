# coding: utf-8

import math

import numpy as np

from paintjob_designer.render.orbit_camera import OrbitCamera


class TestRotate:

    def test_rotate_accumulates_yaw_and_pitch(self):
        cam = OrbitCamera(default_yaw=0.0, default_pitch=0.0)

        cam.rotate(d_yaw=0.5, d_pitch=0.3)

        assert cam.yaw == 0.5
        assert cam.pitch == 0.3

    def test_pitch_clamps_to_upper_pole(self):
        cam = OrbitCamera(default_yaw=0.0, default_pitch=0.0)

        cam.rotate(d_yaw=0.0, d_pitch=math.radians(200.0))

        # Pole limit is ±85°; anything above collapses there.
        assert cam.pitch == OrbitCamera.MAX_PITCH

    def test_pitch_clamps_to_lower_pole(self):
        cam = OrbitCamera(default_yaw=0.0, default_pitch=0.0)

        cam.rotate(d_yaw=0.0, d_pitch=math.radians(-200.0))

        assert cam.pitch == OrbitCamera.MIN_PITCH


class TestZoom:

    def test_zoom_in_shrinks_distance(self):
        cam = OrbitCamera(default_distance=2.0)

        changed = cam.zoom(0.5)

        assert changed is True
        assert cam.distance == 1.0

    def test_zoom_past_min_clamps_and_reports_no_change(self):
        cam = OrbitCamera(default_distance=OrbitCamera.MIN_DISTANCE)

        changed = cam.zoom(0.01)

        assert changed is False
        assert cam.distance == OrbitCamera.MIN_DISTANCE

    def test_zoom_past_max_clamps_and_reports_no_change(self):
        cam = OrbitCamera(default_distance=OrbitCamera.MAX_DISTANCE)

        changed = cam.zoom(100.0)

        assert changed is False
        assert cam.distance == OrbitCamera.MAX_DISTANCE


class TestFitToBounds:

    def test_targets_bbox_center(self):
        cam = OrbitCamera()
        positions = np.array([
            [-1.0,  2.0,  0.0],
            [ 3.0,  6.0,  4.0],
        ], dtype=np.float32)

        cam.fit_to_bounds(positions)

        assert cam.target.tolist() == [1.0, 4.0, 2.0]

    def test_empty_positions_is_noop(self):
        cam = OrbitCamera(default_distance=2.0)
        empty = np.zeros((0, 3), dtype=np.float32)

        cam.fit_to_bounds(empty)

        assert cam.distance == 2.0
        assert cam.target.tolist() == [0.0, 0.0, 0.0]

    def test_fit_snapshots_for_reset(self):
        cam = OrbitCamera(default_distance=10.0)
        positions = np.array([
            [0.0, 0.0, 0.0],
            [4.0, 4.0, 4.0],
        ], dtype=np.float32)

        cam.fit_to_bounds(positions)
        # User spins the camera around…
        cam.rotate(d_yaw=1.0, d_pitch=0.5)
        cam.zoom(0.5)
        # …then resets.
        cam.reset()

        # Target returned to the last fit's center, not the origin.
        assert cam.target.tolist() == [2.0, 2.0, 2.0]


class TestReset:

    def test_reset_without_fit_falls_back_to_defaults(self):
        cam = OrbitCamera(
            default_yaw=math.radians(30.0),
            default_pitch=math.radians(15.0),
            default_distance=5.0,
        )
        cam.rotate(d_yaw=2.0, d_pitch=0.3)
        cam.zoom(0.25)

        cam.reset()

        assert cam.yaw == math.radians(30.0)
        assert cam.pitch == math.radians(15.0)
        assert cam.distance == 5.0
        assert cam.target.tolist() == [0.0, 0.0, 0.0]


class TestMatrices:

    def test_projection_matrix_is_4x4_float32(self):
        cam = OrbitCamera()

        m = cam.projection_matrix(aspect=1.5)

        assert m.shape == (4, 4)
        assert m.dtype == np.float32

    def test_view_matrix_looks_at_target(self):
        cam = OrbitCamera(default_yaw=0.0, default_pitch=0.0, default_distance=5.0)

        view = cam.view_matrix()

        # With yaw=pitch=0, the eye sits at (0, 0, +distance). Applying the
        # view matrix to the target origin should produce (0, 0, -distance)
        # in view space — the target is `distance` units in front of the eye.
        origin = np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float32)
        view_space = view @ origin
        assert view_space[2] == -5.0
