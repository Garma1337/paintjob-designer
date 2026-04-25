# coding: utf-8

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from paintjob_designer.color.converter import ColorConverter
from paintjob_designer.color.transform import ColorTransformer
from paintjob_designer.gui.widget.transform_panel import (
    _MODE_LABELS,
    _PIPELINE,
    _OperationSection,
)
from paintjob_designer.models import Rgb888


class VertexTransformDialog(QDialog):
    """Modeless panel for stacking transforms on a Skin's gouraud vertex
    colors. Mirrors `TransformColorsPanel`'s Apply / Close lifecycle.
    """

    # Signals carry `dict[int, Rgb888]` payloads. Declared as `object` because
    # PySide6 can't marshal `dict` through a typed signal.
    preview_changed = Signal(object)
    commit_requested = Signal(object)
    closing = Signal()

    def __init__(
        self,
        color_transformer: ColorTransformer,
        color_converter: ColorConverter,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Transform Vertex Colors")
        self.setModal(False)
        self.setMinimumWidth(420)

        self._transformer = color_transformer
        self._converter = color_converter
        self._colors: list[Rgb888] = []
        # When set, the pipeline only rewrites these indices — used to skip
        # vertex colors shared with textured triangles, since the shader's
        # `texture * vcolor * 2` modulation would tint the paintjob.
        self._transformable_indices: set[int] | None = None

        layout = QVBoxLayout(self)

        self._intro = QLabel()
        self._intro.setWordWrap(True)
        self._intro.setStyleSheet("color: #aaa;")
        layout.addWidget(self._intro)

        self._sections: dict[object, _OperationSection] = {}
        for mode in _PIPELINE:
            section = _OperationSection(
                mode=mode,
                label=_MODE_LABELS[mode],
                color_converter=self._converter,
            )

            section.params_changed.connect(self._on_params_changed)
            layout.addWidget(section)
            self._sections[mode] = section

        self._summary_label = QLabel()
        self._summary_label.setStyleSheet("color: #aaa; padding: 4px 0;")
        layout.addWidget(self._summary_label)

        layout.addStretch(1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self._commit_button = buttons.addButton(
            "Apply", QDialogButtonBox.ButtonRole.ApplyRole,
        )
        self._commit_button.clicked.connect(self._on_commit)
        buttons.rejected.connect(self.hide)
        layout.addWidget(buttons)

        self._buttons = buttons
        self._refresh_summary()

    def set_colors(
        self,
        colors: list[Rgb888],
        transformable_indices: set[int] | None = None,
    ) -> None:
        """Push a fresh baseline. Call on open and after each commit so the
        next preview starts from the freshly-baked state.
        """
        self._colors = list(colors)
        self._transformable_indices = (
            set(transformable_indices)
            if transformable_indices is not None else None
        )

        if self._transformable_indices is None:
            scope_hint = (
                f"{len(self._colors)} colors will be considered."
            )
        else:
            scope_hint = (
                f"{len(self._transformable_indices)} of {len(self._colors)} "
                "colors will be considered (the rest are tied to textured "
                "surfaces and would tint the paintjob if changed)."
            )

        self._intro.setText(
            "Apply one or more transforms to the gouraud vertex colors "
            f"in this character's mesh. {scope_hint} Enable a section to "
            "add it to the pipeline.",
        )
        self._refresh_summary()

    def commit_finished(self) -> None:
        """Reset sliders so the next Apply doesn't double-apply on top of
        the freshly-baked baseline."""
        for section in self._sections.values():
            section.reset_values()

        self._refresh_summary()

    def closeEvent(self, event) -> None:
        self.closing.emit()
        super().closeEvent(event)

    def hideEvent(self, event) -> None:
        # Catches both Close button and window X.
        self.closing.emit()
        super().hideEvent(event)

    def _enabled_params(self) -> list:
        return [
            self._sections[mode].current_params()
            for mode in _PIPELINE
            if self._sections[mode].is_enabled()
        ]

    def _compute_overrides(self) -> dict[int, Rgb888]:
        params_list = self._enabled_params()
        if not params_list or not self._colors:
            return {}

        overrides: dict[int, Rgb888] = {}
        for index, color in enumerate(self._colors):
            if (
                self._transformable_indices is not None
                and index not in self._transformable_indices
            ):
                continue

            psx = self._converter.rgb_to_psx(color)
            for params in params_list:
                psx = self._transformer.transform(psx, params)

            new_rgb = self._converter.psx_to_rgb(psx)
            if (new_rgb.r, new_rgb.g, new_rgb.b) == (color.r, color.g, color.b):
                continue

            overrides[index] = new_rgb

        return overrides

    def _on_params_changed(self) -> None:
        overrides = self._compute_overrides()
        self._refresh_summary(overrides)
        self.preview_changed.emit(overrides)

    def _on_commit(self) -> None:
        overrides = self._compute_overrides()
        if not overrides:
            return

        self.commit_requested.emit(overrides)

    def _refresh_summary(
        self, overrides: dict[int, Rgb888] | None = None,
    ) -> None:
        if overrides is None:
            overrides = self._compute_overrides()

        total = len(self._colors)
        if not overrides:
            self._summary_label.setText(f"No changes (0 of {total} colors)")
            self._commit_button.setEnabled(False)
        else:
            self._summary_label.setText(
                f"{len(overrides)} of {total} colors will change",
            )
            self._commit_button.setEnabled(True)
