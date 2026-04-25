# coding: utf-8

from typing import Callable

import numpy as np
from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QWidget,
)

from paintjob_designer.ctr.vertex_assembler import VertexAssembler


class AnimationController(QObject):
    """Owns the animation panel widget + per-frame playback."""

    DEFAULT_FPS = 30

    def __init__(
        self,
        vertex_assembler: VertexAssembler,
        bundle_provider: Callable[[], object | None],
        on_positions: Callable[[np.ndarray], None],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._vertex_assembler = vertex_assembler
        self._bundle_provider = bundle_provider
        self._on_positions = on_positions

        self._timer = QTimer(self)
        self._timer.setInterval(int(1000 / self.DEFAULT_FPS))
        self._timer.timeout.connect(self._on_tick)

        self._anim_index: int = -1
        self._frame_index: int = 0

        self._panel = self._build_panel()

    @property
    def panel(self) -> QWidget:
        return self._panel

    def reload(self) -> None:
        """Re-read available animations from the current bundle and reset
        the panel to the static-pose entry."""
        self._timer.stop()
        self._play_button.setText("Play")
        self._anim_index = -1
        self._frame_index = 0
        self._frame_label.setText("—")

        self._combo.blockSignals(True)
        self._combo.clear()
        self._combo.addItem("(static pose)")

        bundle = self._bundle_provider()
        anims = bundle.mesh.anims if bundle is not None else []
        for anim in anims:
            label = anim.name or f"anim {self._combo.count()}"
            self._combo.addItem(f"{label} ({len(anim.frames)} frames)")

        self._combo.setCurrentIndex(0)
        self._combo.blockSignals(False)

        self._set_controls_enabled(bool(anims))

    def _build_panel(self) -> QWidget:
        group = QGroupBox("Animation")
        layout = QFormLayout(group)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        self._combo = QComboBox()
        self._combo.currentIndexChanged.connect(self._on_clip_selected)
        layout.addRow("Clip:", self._combo)

        play_row = QWidget()
        play_layout = QHBoxLayout(play_row)
        play_layout.setContentsMargins(0, 0, 0, 0)
        play_layout.setSpacing(6)
        self._play_button = QPushButton("Play")
        self._play_button.clicked.connect(self._on_play_clicked)
        play_layout.addWidget(self._play_button)
        self._frame_label = QLabel("—")
        self._frame_label.setMinimumWidth(60)
        play_layout.addWidget(self._frame_label, 1)
        layout.addRow("Frame:", play_row)

        self._fps_spin = QSpinBox()
        self._fps_spin.setRange(1, 60)
        self._fps_spin.setValue(self.DEFAULT_FPS)
        self._fps_spin.setToolTip(
            "Playback speed in frames/second. PS1 animations don't carry an "
            "intended frame rate so this is just a preview control.",
        )
        self._fps_spin.valueChanged.connect(self._on_fps_changed)
        layout.addRow("FPS:", self._fps_spin)

        self._loop_check = QCheckBox("Loop")
        self._loop_check.setToolTip(
            "When unchecked, playback stops on the last frame instead of "
            "wrapping back to the start.",
        )
        layout.addRow("", self._loop_check)

        self._set_controls_enabled(False)
        return group

    def _set_controls_enabled(self, enabled: bool) -> None:
        self._combo.setEnabled(enabled)
        self._play_button.setEnabled(enabled)

    def _on_fps_changed(self, fps: int) -> None:
        self._timer.setInterval(max(1, int(1000 / max(1, fps))))

    def _on_clip_selected(self, combo_index: int) -> None:
        # Combo index 0 is the static pose; anim indices are shifted by 1.
        self._timer.stop()
        self._play_button.setText("Play")
        self._frame_index = 0

        if combo_index <= 0:
            self._anim_index = -1
            self._frame_label.setText("—")
            self._render_static_pose()
            return

        self._anim_index = combo_index - 1
        self._update_frame_label()
        self._render_current_frame()

    def _on_play_clicked(self) -> None:
        if self._anim_index < 0:
            return

        if self._timer.isActive():
            self._timer.stop()
            self._play_button.setText("Play")
        else:
            # Rewind if a non-looping clip parked on its last frame.
            frames = self._current_frames()

            if frames and self._frame_index >= len(frames) - 1:
                self._frame_index = 0
                self._update_frame_label()
                self._render_current_frame()

            self._timer.start()
            self._play_button.setText("Pause")

    def _on_tick(self) -> None:
        frames = self._current_frames()
        if not frames:
            self._timer.stop()
            return

        next_index = self._frame_index + 1
        if next_index >= len(frames):
            if self._loop_check.isChecked():
                next_index = 0
            else:
                self._timer.stop()
                self._play_button.setText("Play")
                return

        self._frame_index = next_index
        self._update_frame_label()
        self._render_current_frame()

    def _current_frames(self) -> list:
        bundle = self._bundle_provider()
        if bundle is None or self._anim_index < 0:
            return []

        anims = bundle.mesh.anims
        if self._anim_index >= len(anims):
            return []

        return anims[self._anim_index].frames

    def _update_frame_label(self) -> None:
        frames = self._current_frames()
        if not frames:
            self._frame_label.setText("—")
            return

        self._frame_label.setText(f"{self._frame_index + 1}/{len(frames)}")

    def _render_static_pose(self) -> None:
        bundle = self._bundle_provider()
        if bundle is None:
            return

        assembled = self._vertex_assembler.assemble(bundle.mesh)
        self._on_positions(np.asarray(assembled.positions, dtype=np.float32))

    def _render_current_frame(self) -> None:
        bundle = self._bundle_provider()
        frames = self._current_frames()
        if bundle is None or not frames:
            return

        frame = frames[self._frame_index]
        assembled = self._vertex_assembler.assemble(bundle.mesh, frame=frame)
        self._on_positions(np.asarray(assembled.positions, dtype=np.float32))
