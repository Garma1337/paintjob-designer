# coding: utf-8

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
    """Bulk transform applied to a Skin's gouraud vertex colors."""

    def __init__(
        self,
        colors: list[Rgb888],
        color_transformer: ColorTransformer,
        color_converter: ColorConverter,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Transform Vertex Colors")
        self.setMinimumWidth(420)

        self._colors = list(colors)
        self._transformer = color_transformer
        self._converter = color_converter
        self._result: dict[int, Rgb888] = {}

        layout = QVBoxLayout(self)

        intro = QLabel(
            "Apply one or more transforms to every gouraud vertex color "
            f"in this character's mesh ({len(self._colors)} colors). "
            "Enable a section to add it to the pipeline.",
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #aaa;")
        layout.addWidget(intro)

        self._sections: dict[object, _OperationSection] = {}
        for mode in _PIPELINE:
            section = _OperationSection(
                mode=mode,
                label=_MODE_LABELS[mode],
                color_converter=self._converter,
            )

            section.params_changed.connect(self._refresh_summary)
            layout.addWidget(section)
            self._sections[mode] = section

        self._summary_label = QLabel()
        self._summary_label.setStyleSheet("color: #aaa; padding: 4px 0;")
        layout.addWidget(self._summary_label)

        layout.addStretch(1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._buttons = buttons
        self._refresh_summary()

    def resulting_overrides(self) -> dict[int, Rgb888]:
        """Per-index Rgb888 deltas produced by the last Apply."""
        return self._result

    def _enabled_params(self) -> list:
        return [
            section.current_params()
            for mode in _PIPELINE
            for section in (self._sections[mode],)
            if section.is_enabled()
        ]

    def _compute_overrides(self) -> dict[int, Rgb888]:
        """Run every input color through the enabled pipeline."""
        params_list = self._enabled_params()
        if not params_list:
            return {}

        overrides: dict[int, Rgb888] = {}
        for index, color in enumerate(self._colors):
            psx = self._converter.rgb_to_psx(color)
            for params in params_list:
                psx = self._transformer.transform(psx, params)

            new_rgb = self._converter.psx_to_rgb(psx)
            if (new_rgb.r, new_rgb.g, new_rgb.b) == (color.r, color.g, color.b):
                continue

            overrides[index] = new_rgb

        return overrides

    def _refresh_summary(self) -> None:
        overrides = self._compute_overrides()
        total = len(self._colors)

        if not overrides:
            self._summary_label.setText(f"No changes (0 of {total} colors)")
            self._buttons.button(
                QDialogButtonBox.StandardButton.Ok,
            ).setEnabled(False)
        else:
            self._summary_label.setText(
                f"{len(overrides)} of {total} colors will change",
            )
            self._buttons.button(
                QDialogButtonBox.StandardButton.Ok,
            ).setEnabled(True)

    def _on_accept(self) -> None:
        self._result = self._compute_overrides()
        self.accept()
