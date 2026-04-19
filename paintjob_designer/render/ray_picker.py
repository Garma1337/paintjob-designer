# coding: utf-8

from dataclasses import dataclass

import numpy as np

from paintjob_designer.render.orbit_camera import OrbitCamera


@dataclass
class RayHit:
    """A single ray/triangle intersection result.

    `barycentric` gives the hit point as `(w0, w1, w2)` weights over the
    triangle's three vertices (summing to ~1). Callers use these to
    interpolate any per-vertex attribute — positions, UVs, colors — at the
    exact hit point without re-casting the ray.
    """

    triangle_index: int
    barycentric: tuple[float, float, float]
    distance: float


class RayTrianglePicker:
    """Casts viewport rays against a flat triangle list and returns the closest hit.

    Stateless — the class exists so the picker can be registered in the DI
    container and injected into `KartViewer` (and unit-tested through its
    public `pick` method) without a module-level function dance. The
    Möller–Trumbore threshold lives on the class so tests can lower it if a
    pathological test case needs more tolerance.
    """

    # Threshold for the Möller–Trumbore determinant; values smaller than this
    # correspond to rays parallel to the triangle plane, which we skip to
    # avoid dividing by ~zero and returning spurious hits.
    PARALLEL_EPSILON = 1e-8

    def pick(
        self,
        positions: np.ndarray,
        camera: OrbitCamera,
        viewport_x: float,
        viewport_y: float,
        viewport_width: int,
        viewport_height: int,
    ) -> RayHit | None:
        """Cast a ray from a viewport pixel and return the closest hit, if any.

        `positions` is the flat triangle-list layout used by `AssembledMesh`
        — `(N*3, 3)`, `(N*9,)`, or `(N, 3, 3)` of float32/64 world-space
        vertex coordinates. We build the ray by un-projecting the viewport
        pixel through the camera's `view @ projection` transform and then
        run Möller–Trumbore against every triangle; at kart-sized counts (a
        few hundred triangles) a brute-force scan completes in well under a
        millisecond per click, which matters less than the simplicity of
        having no acceleration structure to maintain.

        Returns `None` when the mesh is empty, the viewport is degenerate,
        or no triangle is hit (user clicked empty background around the
        kart).
        """
        if viewport_width <= 0 or viewport_height <= 0:
            return None

        tris = self._as_triangles(positions)
        if tris.size == 0:
            return None

        ray_origin, ray_dir = self._build_ray(
            camera, viewport_x, viewport_y, viewport_width, viewport_height,
        )

        best: RayHit | None = None
        for i, tri in enumerate(tris):
            hit = self._intersect(ray_origin, ray_dir, tri[0], tri[1], tri[2])
            if hit is None:
                continue

            t, b0, b1, b2 = hit
            if best is None or t < best.distance:
                best = RayHit(
                    triangle_index=i,
                    barycentric=(b0, b1, b2),
                    distance=t,
                )

        return best

    def _as_triangles(self, positions: np.ndarray) -> np.ndarray:
        """Reshape a flat position buffer to an `(N, 3, 3)` triangle array."""
        arr = np.asarray(positions, dtype=np.float64)

        if arr.ndim == 1:
            count = arr.shape[0] // 9
            if count == 0:
                return np.zeros((0, 3, 3), dtype=np.float64)

            return arr[: count * 9].reshape(count, 3, 3)

        if arr.ndim == 2 and arr.shape[1] == 3:
            count = arr.shape[0] // 3
            if count == 0:
                return np.zeros((0, 3, 3), dtype=np.float64)

            return arr[: count * 3].reshape(count, 3, 3)

        if arr.ndim == 3 and arr.shape[1:] == (3, 3):
            return arr

        raise ValueError(
            f"positions must be shape (N*3, 3), (N*9,), or (N, 3, 3); got {arr.shape}"
        )

    def _build_ray(
        self,
        camera: OrbitCamera,
        viewport_x: float,
        viewport_y: float,
        viewport_width: int,
        viewport_height: int,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Un-project a viewport pixel to a world-space ray (origin, unit dir).

        Viewport Y is measured top-down (Qt convention); NDC Y flips that.
        """
        ndc_x = (2.0 * viewport_x / viewport_width) - 1.0
        ndc_y = 1.0 - (2.0 * viewport_y / viewport_height)

        aspect = viewport_width / viewport_height
        view = camera.view_matrix().astype(np.float64)
        proj = camera.projection_matrix(aspect).astype(np.float64)
        inv = np.linalg.inv(proj @ view)

        near_clip = np.array([ndc_x, ndc_y, -1.0, 1.0], dtype=np.float64)
        far_clip = np.array([ndc_x, ndc_y, 1.0, 1.0], dtype=np.float64)

        near_world = inv @ near_clip
        far_world = inv @ far_clip
        near_world = near_world[:3] / near_world[3]
        far_world = far_world[:3] / far_world[3]

        ray_dir = far_world - near_world
        norm = np.linalg.norm(ray_dir)
        if norm < self.PARALLEL_EPSILON:
            # Shouldn't happen for a well-formed camera, but fall back to a
            # harmless ray so the caller still gets a None-hit instead of a
            # crash.
            return near_world, np.array([0.0, 0.0, -1.0])

        return near_world, ray_dir / norm

    def _intersect(
        self,
        origin: np.ndarray,
        direction: np.ndarray,
        v0: np.ndarray,
        v1: np.ndarray,
        v2: np.ndarray,
    ) -> tuple[float, float, float, float] | None:
        """Möller–Trumbore ray/triangle. Returns `(t, w0, w1, w2)` or None.

        Accepts front AND back faces — the viewer renders with
        `GL_CULL_FACE` off because CTR meshes frequently have double-sided
        draws, so the picker has to agree: a click on a back-facing
        triangle is still a legitimate pick.
        """
        edge1 = v1 - v0
        edge2 = v2 - v0
        h = np.cross(direction, edge2)
        a = float(np.dot(edge1, h))

        if abs(a) < self.PARALLEL_EPSILON:
            return None

        f = 1.0 / a
        s = origin - v0
        u = f * float(np.dot(s, h))
        if u < 0.0 or u > 1.0:
            return None

        q = np.cross(s, edge1)
        v = f * float(np.dot(direction, q))
        if v < 0.0 or u + v > 1.0:
            return None

        t = f * float(np.dot(edge2, q))
        if t <= self.PARALLEL_EPSILON:
            return None

        return t, 1.0 - u - v, u, v
