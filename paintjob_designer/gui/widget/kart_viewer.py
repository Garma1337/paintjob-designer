# coding: utf-8

import ctypes
from pathlib import Path

import numpy as np
from OpenGL import GL
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QSurfaceFormat
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from paintjob_designer.models import AssembledMesh, TextureLayout
from paintjob_designer.render.atlas_uv_mapper import AtlasUvMapper
from paintjob_designer.render.orbit_camera import OrbitCamera
from paintjob_designer.render.ray_picker import RayTrianglePicker

# Shaders live as standalone `.vert` / `.frag` files under `shaders/` — kept
# them out of this module so editors can highlight GLSL properly and the
# code here stays readable. Loaded at import time: the strings never change
# between runs and file I/O during `initializeGL` was wasted work.
#
# No V-flip in the fragment shader: the atlas buffer already stores row 0 at
# the top, and GL's texture sampler returns that row at `v = 0`.
_SHADERS_DIR = Path(__file__).parent / "shaders"
_VERTEX_SHADER = (_SHADERS_DIR / "kart.vert").read_text(encoding="utf-8")
_FRAGMENT_SHADER = (_SHADERS_DIR / "kart.frag").read_text(encoding="utf-8")


class KartViewer(QOpenGLWidget):
    """Textured 3D preview of the current kart mesh."""

    gl_init_failed = Signal(str)
    # Emitted on Alt+Click with:
    #   tex_layout_index  1-based index into the mesh's texture_layouts (0 = an
    #                     untextured draw, no slot/CLUT to pick from)
    #   byte_u, byte_v    interpolated byte-space UV (0..255) at the hit point
    # The main window maps the TextureLayout's CLUT coords to a paintjob slot
    # and samples the atlas at (u, v) to find the exact color_index.
    eyedropper_picked = Signal(int, float, float)

    _ZOOM_STEP = 1.15

    def __init__(
        self,
        uv_mapper: AtlasUvMapper,
        ray_picker: RayTrianglePicker,
        parent=None,
    ) -> None:
        fmt = QSurfaceFormat()
        fmt.setVersion(3, 3)
        fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
        fmt.setDepthBufferSize(24)
        fmt.setSamples(4)

        super().__init__(parent)
        self.setFormat(fmt)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._uv_mapper = uv_mapper
        self._ray_picker = ray_picker
        self._camera = OrbitCamera()

        self._viewport_w = 1
        self._viewport_h = 1
        self._last_mouse_pos = None

        # GL resources (created in initializeGL).
        self._program = 0
        self._vao = 0
        self._vbo_pos = 0
        self._vbo_uv = 0
        self._vbo_normal = 0
        self._vbo_highlight = 0
        self._vbo_color = 0
        self._texture = 0
        self._uniform_mvp = -1
        self._uniform_atlas = -1
        self._uniform_has_focus = -1
        self._triangle_count = 0
        self._initialized = False

        # Pending uploads. Applied during the next paintGL.
        # Tuple of (positions, uvs, normals, colors) for the mesh.
        self._pending_mesh: tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray] | None = None
        self._pending_atlas: tuple[bytes, int, int] | None = None
        self._pending_atlas_region: tuple[bytes, int, int, int, int, int, int] | None = None
        self._pending_highlight: np.ndarray | None = None

        # UVs and per-vertex Gouraud colors from the last `set_mesh` call, kept
        # around so `set_frame_positions` can build new pending meshes even after
        # `paintGL` has consumed the previous one (it clears `_pending_mesh` on
        # upload). Both are mesh-intrinsic: animation frames only move vertices,
        # so these stay the same across the whole clip.
        self._base_uvs: np.ndarray | None = None
        self._base_colors: np.ndarray | None = None

        # Most-recent world-space positions + byte-space UVs for ray-picking
        # (eyedropper). Updated on every `set_mesh` / `set_frame_positions`
        # so picking uses the same geometry the user is looking at.
        self._pick_positions: np.ndarray | None = None
        self._pick_uvs: np.ndarray | None = None
        self._pick_texture_layout_indices: list[int] | None = None

        # Whether any slot is currently focused. The fragment shader reads this
        # as `u_has_focus`; when 0, all triangles render normally regardless of
        # the per-vertex highlight attribute.
        self._has_focus = False

    def clear(self) -> None:
        """Drop the current mesh + atlas so the viewer renders empty.

        Used when the user de-selects everything (no character previewed).
        Equivalent to calling `set_mesh` with a zero-triangle assembly,
        but spelled out so callers don't need to construct a dummy mesh.
        """
        self._pending_mesh = (
            np.zeros((0, 3), dtype=np.float32),
            np.zeros((0, 2), dtype=np.float32),
            np.zeros((0, 3), dtype=np.float32),
            np.zeros((0, 3), dtype=np.float32),
        )
        self._base_uvs = None
        self._base_colors = None
        self._pick_positions = None
        self._pick_uvs = None
        self._pick_texture_layout_indices = None
        self._pending_highlight = np.zeros((0,), dtype=np.float32)
        self._has_focus = False
        self.update()

    def set_mesh(
        self,
        assembled: AssembledMesh,
        texture_layouts: list[TextureLayout],
    ) -> None:
        if assembled.triangle_count == 0:
            self._pending_mesh = (
                np.zeros((0, 3), dtype=np.float32),
                np.zeros((0, 2), dtype=np.float32),
                np.zeros((0, 3), dtype=np.float32),
                np.zeros((0, 3), dtype=np.float32),
            )
            self._base_uvs = None
            self._base_colors = None
            self._pick_positions = None
            self._pick_uvs = None
            self._pick_texture_layout_indices = None
            self._pending_highlight = np.zeros((0,), dtype=np.float32)
        else:
            positions = np.asarray(assembled.positions, dtype=np.float32)
            uvs = np.asarray(
                self._uv_mapper.map(assembled, texture_layouts),
                dtype=np.float32,
            )
            normals = self.compute_flat_normals(positions)
            colors = np.asarray(assembled.gouraud_colors, dtype=np.float32)
            if len(colors) != len(positions):
                # Fall back to white if the assembler didn't emit colors
                # (older pipelines or empty gouraud tables) — keeps shader happy
                # without changing appearance for textured faces.
                colors = np.ones((len(positions), 3), dtype=np.float32)

            self._pending_mesh = (positions, uvs, normals, colors)
            self._base_uvs = uvs
            self._base_colors = colors
            # Eyedropper picking needs the raw world positions + byte-space
            # UVs per vertex, not the atlas-mapped UVs stored in `_base_uvs`.
            # Stored aligned with `texture_layout_indices` (one per triangle).
            self._pick_positions = positions.copy()
            self._pick_uvs = np.asarray(assembled.uvs, dtype=np.float32)
            self._pick_texture_layout_indices = list(assembled.texture_layout_indices)
            # Default highlight = everything-highlighted; paired with
            # `_has_focus=False` the shader will render normally.
            self._pending_highlight = np.ones(len(positions), dtype=np.float32)
            self._has_focus = False
            self._camera.fit_to_bounds(positions)

        self.update()

    def set_highlighted_triangles(self, triangle_indices: list[int] | None) -> None:
        """Focus the render on a subset of triangles by dimming the rest."""
        if self._base_uvs is None:
            return

        total_vertices = len(self._base_uvs)
        highlight = np.zeros(total_vertices, dtype=np.float32)

        if not triangle_indices:
            # No focus → set everything to 1.0 so `_has_focus=False` renders
            # normally and any residual attribute values from before don't
            # leak if the flag is toggled.
            highlight[:] = 1.0
            self._has_focus = False
        else:
            for tri_idx in triangle_indices:
                base = tri_idx * 3
                if 0 <= base <= total_vertices - 3:
                    highlight[base:base + 3] = 1.0

            self._has_focus = True

        self._pending_highlight = highlight
        self.update()

    @staticmethod
    def compute_flat_normals(positions: np.ndarray) -> np.ndarray:
        """Per-triangle normals (cross of two edges), replicated across the 3
        vertices of each triangle so flat shading lands without an index buffer.
        """
        triangles = positions.reshape(-1, 3, 3)
        edge_a = triangles[:, 1] - triangles[:, 0]
        edge_b = triangles[:, 2] - triangles[:, 0]
        face_normals = np.cross(edge_a, edge_b)

        lengths = np.linalg.norm(face_normals, axis=1, keepdims=True)
        # Guard against degenerate triangles (zero-area faces produce NaN
        # after the divide). Treat them as "face up" so they still shade.
        safe = np.where(lengths > 1e-8, lengths, 1.0)
        face_normals = face_normals / safe
        face_normals = np.where(
            lengths > 1e-8, face_normals, np.array([0.0, 1.0, 0.0], dtype=np.float32),
        )

        # Repeat each face normal across its three vertices.
        return np.repeat(face_normals, 3, axis=0).astype(np.float32)

    def set_atlas(self, rgba: bytes | bytearray, width: int, height: int) -> None:
        self._pending_atlas = (bytes(rgba), width, height)
        # A full re-upload supersedes any pending region upload — no point
        # shipping a sub-rect of the old atlas if the whole thing is about to
        # be overwritten anyway.
        self._pending_atlas_region = None
        self.update()

    def set_atlas_region(
        self,
        rgba: bytes | bytearray,
        atlas_width: int,
        atlas_height: int,
        x: int, y: int, w: int, h: int,
    ) -> None:
        """Upload only a rectangle of the atlas (glTexSubImage2D path)."""
        if self._pending_atlas is not None:
            # A full re-upload is already queued; it'll write the region too.
            return

        if self._texture == 0:
            return

        self._pending_atlas_region = (bytes(rgba), atlas_width, atlas_height, x, y, w, h)
        self.update()

    def set_frame_positions(
        self,
        positions: np.ndarray,
    ) -> None:
        """Upload a new positions buffer (and a fresh set of flat normals) for
        the current mesh without touching UVs or refitting the camera.
        """
        if self._base_uvs is None:
            return

        uvs = self._base_uvs
        colors = (
            self._base_colors
            if self._base_colors is not None
            else np.ones((len(uvs), 3), dtype=np.float32)
        )

        if positions.size == 0 or len(positions) != len(uvs):
            # Animation frame's vertex count differs from the base mesh —
            # leave the last valid frame on screen rather than crashing.
            return

        normals = self.compute_flat_normals(positions)
        pick_positions = positions.astype(np.float32)
        self._pending_mesh = (pick_positions, uvs, normals, colors)
        # Pick buffer follows the animation frame so the eyedropper hits
        # whatever geometry the user actually sees.
        self._pick_positions = pick_positions.copy()
        self.update()

    def reset_camera(self) -> None:
        self._camera.reset()
        self.update()

    def initializeGL(self) -> None:
        # Wrap the whole bring-up in a try/except: shader compile/link can
        # fail on older drivers, and `glGenBuffers` etc. raise if the context
        # didn't come up at the 3.3 core profile we asked for. Tell the host
        # window so it can swap us for a placeholder.
        try:
            GL.glClearColor(0.15, 0.16, 0.18, 1.0)
            GL.glEnable(GL.GL_DEPTH_TEST)
            # Backface culling stays off: PSX faces are commonly double-sided and
            # the assembler's winding varies with flip_normal + batch-reverse, so
            # culling would swallow roughly half the kart.
            GL.glDisable(GL.GL_CULL_FACE)

            self._program = self._build_shader_program()
            self._uniform_mvp = GL.glGetUniformLocation(self._program, "u_mvp")
            self._uniform_atlas = GL.glGetUniformLocation(self._program, "u_atlas")
            self._uniform_has_focus = GL.glGetUniformLocation(self._program, "u_has_focus")

            self._vao = GL.glGenVertexArrays(1)
            self._vbo_pos = GL.glGenBuffers(1)
            self._vbo_uv = GL.glGenBuffers(1)
            self._vbo_normal = GL.glGenBuffers(1)
            self._vbo_highlight = GL.glGenBuffers(1)
            self._vbo_color = GL.glGenBuffers(1)
            self._texture = GL.glGenTextures(1)

            self._configure_vao()
            self._configure_texture_defaults()

            self._initialized = True
        except Exception as exc:
            self._initialized = False
            self.gl_init_failed.emit(str(exc))

    def resizeGL(self, w: int, h: int) -> None:
        self._viewport_w = max(1, w)
        self._viewport_h = max(1, h)
        GL.glViewport(0, 0, self._viewport_w, self._viewport_h)

    def paintGL(self) -> None:
        if not self._initialized:
            # Post-failure path: host window should have swapped us out, but
            # if it hasn't yet (signal delivery isn't instant) just clear to
            # the background so we don't issue GL calls on broken state.
            try:
                GL.glClear(GL.GL_COLOR_BUFFER_BIT)
            except Exception:
                pass

            return

        if self._pending_mesh is not None:
            self._upload_mesh(*self._pending_mesh)
            self._pending_mesh = None

        if self._pending_highlight is not None:
            self._upload_highlight(self._pending_highlight)
            self._pending_highlight = None

        if self._pending_atlas is not None:
            self._upload_atlas(*self._pending_atlas)
            self._pending_atlas = None

        if self._pending_atlas_region is not None:
            self._upload_atlas_region(*self._pending_atlas_region)
            self._pending_atlas_region = None

        GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)

        if self._triangle_count == 0:
            return

        GL.glUseProgram(self._program)

        aspect = self._viewport_w / self._viewport_h
        mvp = self._camera.projection_matrix(aspect) @ self._camera.view_matrix()
        GL.glUniformMatrix4fv(self._uniform_mvp, 1, GL.GL_TRUE, mvp.astype(np.float32))
        GL.glUniform1i(self._uniform_has_focus, 1 if self._has_focus else 0)

        GL.glActiveTexture(GL.GL_TEXTURE0)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self._texture)
        GL.glUniform1i(self._uniform_atlas, 0)

        GL.glBindVertexArray(self._vao)
        GL.glDrawArrays(GL.GL_TRIANGLES, 0, self._triangle_count * 3)
        GL.glBindVertexArray(0)
        GL.glUseProgram(0)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._last_mouse_pos = event.position()
        elif event.button() == Qt.MouseButton.RightButton:
            # Right-click = eyedropper pick. Left-drag stays dedicated to
            # orbit, so artists can rotate and pick without switching tools.
            self._handle_eyedropper_pick(event)

    def mouseMoveEvent(self, event) -> None:
        if self._last_mouse_pos is None:
            return

        delta = event.position() - self._last_mouse_pos
        self._last_mouse_pos = event.position()

        self._camera.rotate(d_yaw=-delta.x() * 0.01, d_pitch=delta.y() * 0.01)
        self.update()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._last_mouse_pos = None

    def wheelEvent(self, event) -> None:
        factor = 1.0 / self._ZOOM_STEP if event.angleDelta().y() > 0 else self._ZOOM_STEP
        if self._camera.zoom(factor):
            self.update()

    def _handle_eyedropper_pick(self, event) -> None:
        """Ray-pick the triangle under the cursor and emit `eyedropper_picked`."""
        if (
            self._pick_positions is None
            or self._pick_uvs is None
            or self._pick_texture_layout_indices is None
        ):
            return

        pos = event.position()
        hit = self._ray_picker.pick(
            self._pick_positions,
            self._camera,
            pos.x(),
            pos.y(),
            self._viewport_w,
            self._viewport_h,
        )

        if hit is None:
            return

        base = hit.triangle_index * 3
        if base + 2 >= len(self._pick_uvs):
            return

        tex_layout_index = self._pick_texture_layout_indices[hit.triangle_index]
        if tex_layout_index == 0:
            # Untextured face (Gouraud-shaded only); no CLUT to pick from.
            # Silently ignore — artist clicked a face that isn't paintjobable.
            return

        w0, w1, w2 = hit.barycentric
        uv0 = self._pick_uvs[base]
        uv1 = self._pick_uvs[base + 1]
        uv2 = self._pick_uvs[base + 2]
        u = float(w0 * uv0[0] + w1 * uv1[0] + w2 * uv2[0])
        v = float(w0 * uv0[1] + w1 * uv1[1] + w2 * uv2[1])

        self.eyedropper_picked.emit(tex_layout_index, u, v)

    def _build_shader_program(self) -> int:
        vert = self._compile(GL.GL_VERTEX_SHADER, _VERTEX_SHADER)
        frag = self._compile(GL.GL_FRAGMENT_SHADER, _FRAGMENT_SHADER)

        program = GL.glCreateProgram()
        GL.glAttachShader(program, vert)
        GL.glAttachShader(program, frag)
        GL.glLinkProgram(program)

        if GL.glGetProgramiv(program, GL.GL_LINK_STATUS) != GL.GL_TRUE:
            log = GL.glGetProgramInfoLog(program).decode("utf-8", errors="replace")
            raise RuntimeError(f"Shader link failed: {log}")

        GL.glDeleteShader(vert)
        GL.glDeleteShader(frag)
        return program

    def _compile(self, stage: int, source: str) -> int:
        shader = GL.glCreateShader(stage)
        GL.glShaderSource(shader, source)
        GL.glCompileShader(shader)

        if GL.glGetShaderiv(shader, GL.GL_COMPILE_STATUS) != GL.GL_TRUE:
            log = GL.glGetShaderInfoLog(shader).decode("utf-8", errors="replace")
            raise RuntimeError(f"Shader compile failed: {log}")

        return shader

    def _configure_vao(self) -> None:
        GL.glBindVertexArray(self._vao)

        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self._vbo_pos)
        GL.glVertexAttribPointer(0, 3, GL.GL_FLOAT, GL.GL_FALSE, 0, ctypes.c_void_p(0))
        GL.glEnableVertexAttribArray(0)

        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self._vbo_uv)
        GL.glVertexAttribPointer(1, 2, GL.GL_FLOAT, GL.GL_FALSE, 0, ctypes.c_void_p(0))
        GL.glEnableVertexAttribArray(1)

        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self._vbo_normal)
        GL.glVertexAttribPointer(2, 3, GL.GL_FLOAT, GL.GL_FALSE, 0, ctypes.c_void_p(0))
        GL.glEnableVertexAttribArray(2)

        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self._vbo_highlight)
        GL.glVertexAttribPointer(3, 1, GL.GL_FLOAT, GL.GL_FALSE, 0, ctypes.c_void_p(0))
        GL.glEnableVertexAttribArray(3)

        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self._vbo_color)
        GL.glVertexAttribPointer(4, 3, GL.GL_FLOAT, GL.GL_FALSE, 0, ctypes.c_void_p(0))
        GL.glEnableVertexAttribArray(4)

        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, 0)
        GL.glBindVertexArray(0)

    def _configure_texture_defaults(self) -> None:
        GL.glBindTexture(GL.GL_TEXTURE_2D, self._texture)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_NEAREST)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_NEAREST)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)
        GL.glBindTexture(GL.GL_TEXTURE_2D, 0)

    def _upload_mesh(
        self,
        positions: np.ndarray,
        uvs: np.ndarray,
        normals: np.ndarray,
        colors: np.ndarray,
    ) -> None:
        self._triangle_count = len(positions) // 3

        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self._vbo_pos)
        GL.glBufferData(GL.GL_ARRAY_BUFFER, positions.nbytes, positions, GL.GL_STATIC_DRAW)

        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self._vbo_uv)
        GL.glBufferData(GL.GL_ARRAY_BUFFER, uvs.nbytes, uvs, GL.GL_STATIC_DRAW)

        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self._vbo_normal)
        GL.glBufferData(GL.GL_ARRAY_BUFFER, normals.nbytes, normals, GL.GL_STATIC_DRAW)

        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self._vbo_color)
        GL.glBufferData(GL.GL_ARRAY_BUFFER, colors.nbytes, colors, GL.GL_STATIC_DRAW)

        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, 0)

    def _upload_highlight(self, highlight: np.ndarray) -> None:
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self._vbo_highlight)
        GL.glBufferData(GL.GL_ARRAY_BUFFER, highlight.nbytes, highlight, GL.GL_DYNAMIC_DRAW)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, 0)

    def _upload_atlas(self, rgba: bytes, width: int, height: int) -> None:
        GL.glBindTexture(GL.GL_TEXTURE_2D, self._texture)
        GL.glPixelStorei(GL.GL_UNPACK_ALIGNMENT, 1)
        GL.glTexImage2D(
            GL.GL_TEXTURE_2D, 0, GL.GL_RGBA,
            width, height, 0,
            GL.GL_RGBA, GL.GL_UNSIGNED_BYTE, rgba,
        )
        GL.glBindTexture(GL.GL_TEXTURE_2D, 0)

    def _upload_atlas_region(
        self,
        rgba: bytes,
        atlas_width: int,
        atlas_height: int,
        x: int, y: int, w: int, h: int,
    ) -> None:
        # Clip to the atlas bounds so bad input from the caller can't issue
        # an out-of-range glTexSubImage2D (which crashes rather than errors).
        x = max(0, min(x, atlas_width))
        y = max(0, min(y, atlas_height))
        w = max(0, min(w, atlas_width - x))
        h = max(0, min(h, atlas_height - y))

        if w == 0 or h == 0:
            return

        # Slice out a contiguous copy of the dirty rectangle — simpler than
        # setting GL_UNPACK_ROW_LENGTH and works reliably with PyOpenGL.
        arr = np.frombuffer(rgba, dtype=np.uint8).reshape(atlas_height, atlas_width, 4)
        sub = np.ascontiguousarray(arr[y:y + h, x:x + w])

        GL.glBindTexture(GL.GL_TEXTURE_2D, self._texture)
        GL.glPixelStorei(GL.GL_UNPACK_ALIGNMENT, 1)
        GL.glTexSubImage2D(
            GL.GL_TEXTURE_2D, 0,
            x, y, w, h,
            GL.GL_RGBA, GL.GL_UNSIGNED_BYTE, sub,
        )
        GL.glBindTexture(GL.GL_TEXTURE_2D, 0)


class NullKartViewer:
    """Drop-in stand-in for `KartViewer` after a GL init failure.

    Absorbs every method the host calls (set_mesh, set_atlas, set_atlas_region,
    set_highlighted_triangles, reset_camera, set_frame_positions, ...) as
    silent no-ops so the rest of the editor doesn't have to gate on
    "is 3D available?" at every call site.
    """

    def __getattr__(self, _name):
        def _noop(*_args, **_kwargs):
            return None

        return _noop
