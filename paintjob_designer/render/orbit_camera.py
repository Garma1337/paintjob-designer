# coding: utf-8

import math

import numpy as np


class OrbitCamera:
    """Yaw/pitch orbit camera with distance-based zoom and bbox-fit."""

    # Ranges sized for small kart meshes (~1-2 units across). Callers can
    # tweak per-instance via `configure_limits` if they render something much
    # larger, but the defaults cover every character in the shipped profiles.
    FOV_DEG = 45.0
    NEAR = 0.01
    FAR = 50.0
    MIN_DISTANCE = 0.1
    MAX_DISTANCE = 20.0
    MIN_PITCH = math.radians(-85.0)
    MAX_PITCH = math.radians(85.0)

    def __init__(
        self,
        default_yaw: float = math.radians(35.0),
        default_pitch: float = math.radians(20.0),
        default_distance: float = 2.0,
    ) -> None:
        self._default_yaw = default_yaw
        self._default_pitch = default_pitch
        self._default_distance = default_distance

        self._yaw = default_yaw
        self._pitch = default_pitch
        self._distance = default_distance
        self._target = np.zeros(3, dtype=np.float32)

        # Snapshot of the most recent `fit_to_bounds` result, so `reset` can
        # restore the orbit pivot even if callers have drained any transient
        # position buffer since then.
        self._last_fit_target: np.ndarray | None = None
        self._last_fit_distance: float = default_distance

    def rotate(self, d_yaw: float, d_pitch: float) -> None:
        """Apply an incremental yaw/pitch rotation in radians."""
        self._yaw += d_yaw
        self._pitch = max(self.MIN_PITCH, min(self.MAX_PITCH, self._pitch + d_pitch))

    def zoom(self, factor: float) -> bool:
        """Scale the orbit distance by `factor`. Returns True if distance
        actually changed (i.e. didn't hit a clamp)."""
        new_distance = self._distance * factor
        new_distance = max(self.MIN_DISTANCE, min(self.MAX_DISTANCE, new_distance))
        if new_distance == self._distance:
            return False

        self._distance = new_distance
        return True

    def reset(self) -> None:
        """Restore yaw/pitch to defaults and target/distance to the last fit."""
        self._yaw = self._default_yaw
        self._pitch = self._default_pitch

        if self._last_fit_target is not None:
            self._target = self._last_fit_target.copy()
            self._distance = self._last_fit_distance
        else:
            self._distance = self._default_distance
            self._target = np.zeros(3, dtype=np.float32)

    def fit_to_bounds(self, positions: np.ndarray) -> None:
        """Center the camera on `positions` (shape (N, 3)) and pull back to frame the whole bounding box at the current FOV."""
        if positions.size == 0:
            return

        mn = positions.min(axis=0)
        mx = positions.max(axis=0)
        self._target = ((mn + mx) * 0.5).astype(np.float32)

        bbox_size = float(np.linalg.norm(mx - mn))
        if bbox_size > 0.0:
            fov_rad = math.radians(self.FOV_DEG)
            # 1.8× margin so the kart isn't grazing the viewport edges.
            self._distance = max(
                self.MIN_DISTANCE,
                (bbox_size * 0.5) / math.tan(fov_rad / 2.0) * 1.8,
            )

        self._last_fit_target = self._target.copy()
        self._last_fit_distance = self._distance

    def view_matrix(self) -> np.ndarray:
        eye = self._target + np.array([
            self._distance * math.cos(self._pitch) * math.sin(self._yaw),
            self._distance * math.sin(self._pitch),
            self._distance * math.cos(self._pitch) * math.cos(self._yaw),
        ], dtype=np.float32)

        return self.look_at(
            eye, self._target, np.array([0.0, 1.0, 0.0], dtype=np.float32),
        )

    @staticmethod
    def look_at(
        eye: np.ndarray, center: np.ndarray, up: np.ndarray,
    ) -> np.ndarray:
        f = center - eye
        f = f / np.linalg.norm(f)
        s = np.cross(f, up)
        s = s / np.linalg.norm(s)
        u = np.cross(s, f)

        m = np.eye(4, dtype=np.float32)
        m[0, :3] = s
        m[1, :3] = u
        m[2, :3] = -f
        m[0, 3] = -float(s @ eye)
        m[1, 3] = -float(u @ eye)
        m[2, 3] = float(f @ eye)

        return m

    def projection_matrix(self, aspect: float) -> np.ndarray:
        """Classic right-handed perspective matrix."""
        f = 1.0 / math.tan(math.radians(self.FOV_DEG) / 2.0)
        m = np.zeros((4, 4), dtype=np.float32)
        m[0, 0] = f / aspect
        m[1, 1] = f
        m[2, 2] = (self.FAR + self.NEAR) / (self.NEAR - self.FAR)
        m[2, 3] = (2.0 * self.FAR * self.NEAR) / (self.NEAR - self.FAR)
        m[3, 2] = -1.0
        return m

    @property
    def yaw(self) -> float:
        return self._yaw

    @property
    def pitch(self) -> float:
        return self._pitch

    @property
    def distance(self) -> float:
        return self._distance

    @property
    def target(self) -> np.ndarray:
        return self._target
