# coding: utf-8

from dataclasses import dataclass
from enum import Enum

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from paintjob_designer.color.converter import ColorConverter
from paintjob_designer.color.transform import (
    ColorTransformer,
    TransformMode,
    TransformParams,
)
from paintjob_designer.gui.command.bulk_transform_command import BulkColorEdit
from paintjob_designer.gui.widget.psx_color_button import PsxColorButton
from paintjob_designer.models import Paintjob, PsxColor, SlotRegions


@dataclass
class TransformCandidate:
    """One color the panel is allowed to rewrite, plus the asset that owns it."""

    asset: object  # Paintjob or Skin — the panel just passes it through
    slot: SlotRegions
    color_index: int
    current_color: PsxColor


class TransformScope(Enum):
    THIS_SLOT = "this_slot"
    KART_SLOTS = "kart_slots"
    SKIN_SLOTS = "skin_slots"


# Pipeline order for composition. Selective ops (replace-matches,
# replace-hue) run before the bulk ops so their output is what the bulk
# rotations see — e.g. replace-hue swaps a green band to red, then a
# later "shift hue" rotates the whole palette with the swap already
# baked in. Order is fixed so artists get predictable results — no
# per-op reordering UI.
_PIPELINE: tuple[TransformMode, ...] = (
    TransformMode.REPLACE_MATCHES,
    TransformMode.REPLACE_HUE,
    TransformMode.SHIFT_HUE,
    TransformMode.SHIFT_SATURATION,
    TransformMode.SHIFT_BRIGHTNESS,
    TransformMode.RGB_DELTA,
)

_MODE_LABELS: dict[TransformMode, str] = {
    TransformMode.REPLACE_MATCHES: "Replace matching color",
    TransformMode.REPLACE_HUE: "Replace hue",
    TransformMode.SHIFT_HUE: "Shift hue",
    TransformMode.SHIFT_SATURATION: "Shift saturation",
    TransformMode.SHIFT_BRIGHTNESS: "Shift brightness",
    TransformMode.RGB_DELTA: "RGB delta",
}


class TransformColorsPanel(QDialog):
    """Modeless panel for stacking multiple bulk-color transforms."""

    # Pushed on every slider tick (live preview). Main window uses the
    # same snapshot / restore machinery as the old dialog to show the
    # in-flight transform without committing.
    preview_changed = Signal(list)

    # Emitted when the user clicks Apply with at least one enabled op.
    # Main window applies + pushes a BulkTransformCommand, then calls
    # `commit_finished` back on the panel so sliders reset.
    commit_requested = Signal(list)

    # Emitted when the panel is about to close (X / Close button). Main
    # window reverts any pending preview state and drops its snapshot.
    closing = Signal()

    def __init__(
        self,
        color_transformer: ColorTransformer,
        color_converter: ColorConverter,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Transform Colors")
        self.setModal(False)
        self.resize(420, 720)

        self._transformer = color_transformer
        self._converter = color_converter

        self._slot_candidates: list[TransformCandidate] = []
        self._kart_slot_candidates: list[TransformCandidate] = []
        self._skin_slot_candidates: list[TransformCandidate] = []
        self._slot_label: str = ""

        layout = QVBoxLayout(self)

        # Three scopes: the one currently-focused slot, every CLUT the
        # paintjob layer can edit (kart_slots), or every CLUT the skin
        # layer can edit (skin_slots). The host pushes one candidate
        # list per scope via `set_candidates`.
        scope_row = QFormLayout()
        self._scope_combo = QComboBox()
        self._scope_combo.addItem("Current slot", TransformScope.THIS_SLOT)
        self._scope_combo.addItem("All kart slots", TransformScope.KART_SLOTS)
        self._scope_combo.addItem("All skin slots", TransformScope.SKIN_SLOTS)
        self._scope_combo.setCurrentIndex(1)
        self._scope_combo.currentIndexChanged.connect(self._on_preview_changed)
        scope_row.addRow("Scope:", self._scope_combo)
        layout.addLayout(scope_row)

        self._sections: dict[TransformMode, _OperationSection] = {}
        for mode in _PIPELINE:
            section = _OperationSection(
                mode=mode,
                label=_MODE_LABELS[mode],
                color_converter=self._converter,
            )

            section.params_changed.connect(self._on_preview_changed)
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

        self._refresh_scope_options()
        self._refresh_summary()

    def set_candidates(
        self,
        slot_candidates: list[TransformCandidate],
        kart_slot_candidates: list[TransformCandidate],
        skin_slot_candidates: list[TransformCandidate],
        slot_label: str = "",
    ) -> None:
        """Push fresh candidate lists for each scope.

        Call on paintjob / preview-character / focused-slot changes. Empty
        lists are fine — the matching scope option just gets disabled.
        """
        self._slot_candidates = slot_candidates
        self._kart_slot_candidates = kart_slot_candidates
        self._skin_slot_candidates = skin_slot_candidates
        self._slot_label = slot_label

        self._refresh_scope_options()
        # Re-fire the preview so the 3D view reflects the new baseline
        # with any still-enabled sections applied.
        self._on_preview_changed()

    def select_slot_scope(self) -> None:
        """Force the scope combo to 'Current slot'."""
        if self._slot_candidates:
            self._scope_combo.setCurrentIndex(0)

    def commit_finished(self) -> None:
        """Main window calls this after a successful commit."""
        for section in self._sections.values():
            section.reset_values()

        self._refresh_summary()

    def closeEvent(self, event) -> None:
        # Emit before hiding so the main window can restore preview state.
        self.closing.emit()
        super().closeEvent(event)

    def hideEvent(self, event) -> None:
        # Catches `Close` button as well as the window X.
        self.closing.emit()
        super().hideEvent(event)

    def _on_preview_changed(self) -> None:
        edits = self._compute_edits()
        self._refresh_summary(edits)
        self.preview_changed.emit(edits)

    def _on_commit(self) -> None:
        edits = self._compute_edits()
        if not edits:
            return

        self.commit_requested.emit(edits)

    def _refresh_scope_options(self) -> None:
        """Enable / disable scope options based on which lists have items.

        Falls back to the next non-empty scope if the current pick became
        empty (e.g. character with no skin slots while SKIN_SLOTS was
        selected).
        """
        availability = {
            0: bool(self._slot_candidates),
            1: bool(self._kart_slot_candidates),
            2: bool(self._skin_slot_candidates),
        }
        for row, enabled in availability.items():
            self._scope_combo.model().item(row).setEnabled(enabled)

        slot_label = (
            f"Current slot ({self._slot_label})"
            if self._slot_label else "Current slot"
        )
        self._scope_combo.setItemText(0, slot_label)

        if not availability[self._scope_combo.currentIndex()]:
            for row, enabled in availability.items():
                if enabled:
                    self._scope_combo.setCurrentIndex(row)
                    break

    def _current_candidates(self) -> list[TransformCandidate]:
        scope = self._scope_combo.currentData()
        if scope == TransformScope.THIS_SLOT:
            return self._slot_candidates

        if scope == TransformScope.SKIN_SLOTS:
            return self._skin_slot_candidates

        return self._kart_slot_candidates

    def _compute_edits(self) -> list[BulkColorEdit]:
        """Apply every enabled section's transform as a pipeline on each candidate."""
        enabled_params = [
            section.current_params()
            for section in self._ordered_sections()
            if section.is_enabled()
        ]

        if not enabled_params:
            return []

        edits: list[BulkColorEdit] = []
        for cand in self._current_candidates():
            new_color = cand.current_color
            for params in enabled_params:
                new_color = self._transformer.transform(new_color, params)

            if new_color.value != cand.current_color.value:
                edits.append(BulkColorEdit(
                    asset=cand.asset,
                    slot=cand.slot,
                    color_index=cand.color_index,
                    old_color=cand.current_color,
                    new_color=new_color,
                ))

        return edits

    def _ordered_sections(self) -> list["_OperationSection"]:
        return [self._sections[mode] for mode in _PIPELINE]

    def _refresh_summary(self, edits: list[BulkColorEdit] | None = None) -> None:
        if edits is None:
            edits = self._compute_edits()

        total = len(self._current_candidates())
        if not edits:
            self._summary_label.setText(
                f"No changes (0 of {total} colors match)",
            )
            self._commit_button.setEnabled(False)
        else:
            self._summary_label.setText(
                f"{len(edits)} of {total} colors will change",
            )
            self._commit_button.setEnabled(True)


class _OperationSection(QGroupBox):
    """One collapsible op section in the panel."""

    params_changed = Signal()

    def __init__(
        self,
        mode: TransformMode,
        label: str,
        color_converter: ColorConverter,
    ) -> None:
        super().__init__(label)
        self._mode = mode
        self._converter = color_converter
        self.setCheckable(True)
        self.setChecked(False)
        self.toggled.connect(self.params_changed)

        layout = QFormLayout(self)

        if mode == TransformMode.REPLACE_MATCHES:
            self._build_replace(layout)
        elif mode == TransformMode.REPLACE_HUE:
            self._build_replace_hue(layout)
        elif mode == TransformMode.SHIFT_HUE:
            self._build_hue(layout)
        elif mode == TransformMode.SHIFT_SATURATION:
            self._build_saturation(layout)
        elif mode == TransformMode.SHIFT_BRIGHTNESS:
            self._build_brightness(layout)
        elif mode == TransformMode.RGB_DELTA:
            self._build_rgb_delta(layout)

    def is_enabled(self) -> bool:
        return self.isChecked()

    def current_params(self) -> TransformParams:
        if self._mode == TransformMode.REPLACE_MATCHES:
            return TransformParams(
                mode=self._mode,
                match_color=self._replace_match,
                replace_with=self._replace_target,
            )

        if self._mode == TransformMode.REPLACE_HUE:
            return TransformParams(
                mode=self._mode,
                source_color=self._hue_source,
                target_color=self._hue_target,
                hue_tolerance_degrees=float(self._hue_tolerance_slider.value()),
            )

        if self._mode == TransformMode.SHIFT_HUE:
            return TransformParams(
                mode=self._mode,
                hue_shift_degrees=float(self._hue_slider.value()),
            )

        if self._mode == TransformMode.SHIFT_SATURATION:
            return TransformParams(
                mode=self._mode,
                saturation_shift=self._saturation_slider.value() / 100.0,
            )

        if self._mode == TransformMode.SHIFT_BRIGHTNESS:
            return TransformParams(
                mode=self._mode,
                brightness_shift=self._brightness_slider.value() / 100.0,
            )

        if self._mode == TransformMode.RGB_DELTA:
            return TransformParams(
                mode=self._mode,
                rgb_delta_r=self._rgb_r_slider.value(),
                rgb_delta_g=self._rgb_g_slider.value(),
                rgb_delta_b=self._rgb_b_slider.value(),
            )

        return TransformParams(mode=self._mode)

    def reset_values(self) -> None:
        """Zero out slider values + leave the enable checkbox alone."""
        if self._mode == TransformMode.SHIFT_HUE:
            self._hue_slider.setValue(0)
        elif self._mode == TransformMode.SHIFT_SATURATION:
            self._saturation_slider.setValue(0)
        elif self._mode == TransformMode.SHIFT_BRIGHTNESS:
            self._brightness_slider.setValue(0)
        elif self._mode == TransformMode.RGB_DELTA:
            self._rgb_r_slider.setValue(0)
            self._rgb_g_slider.setValue(0)
            self._rgb_b_slider.setValue(0)
        # Replace-matches keeps its current match/target — they're not
        # sliders, and the checkbox handles on/off.

    def _build_replace(self, layout: QFormLayout) -> None:
        self._replace_match = PsxColor(value=0x8000)
        self._replace_target = PsxColor(value=0x8000)

        self._match_button = PsxColorButton(self._converter, self._replace_match)
        self._match_button.color_picked.connect(self._on_match_picked)
        layout.addRow("Match:", self._match_button)

        self._target_button = PsxColorButton(self._converter, self._replace_target)
        self._target_button.color_picked.connect(self._on_target_picked)
        layout.addRow("Replace with:", self._target_button)

        hint = QLabel(
            "Every color whose u16 equals Match is replaced with Replace. The "
            "stp bit is part of the match."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #888;")
        layout.addRow(hint)

    def _on_match_picked(self, color: PsxColor) -> None:
        self._replace_match = color
        self.params_changed.emit()

    def _on_target_picked(self, color: PsxColor) -> None:
        self._replace_target = color
        self.params_changed.emit()

    def _build_replace_hue(self, layout: QFormLayout) -> None:
        self._hue_source = PsxColor(value=0x8000)
        self._hue_target = PsxColor(value=0x8000)

        self._hue_source_button = PsxColorButton(self._converter, self._hue_source)
        self._hue_source_button.color_picked.connect(self._on_hue_source_picked)
        layout.addRow("From hue:", self._hue_source_button)

        self._hue_target_button = PsxColorButton(self._converter, self._hue_target)
        self._hue_target_button.color_picked.connect(self._on_hue_target_picked)
        layout.addRow("To hue:", self._hue_target_button)

        self._hue_tolerance_slider, self._hue_tolerance_value = self._slider(
            0, 180, "°",
        )
        self._hue_tolerance_slider.setValue(30)
        layout.addRow(
            "Tolerance:",
            self._wrap(self._hue_tolerance_slider, self._hue_tolerance_value),
        )

        hint = QLabel(
            "Rotates hues within ± Tolerance of the From hue by (To − From). "
            "Saturation and brightness are preserved, so gradients keep their "
            "shading. Near-gray pixels are skipped (no reliable hue)."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #888;")
        layout.addRow(hint)

    def _on_hue_source_picked(self, color: PsxColor) -> None:
        self._hue_source = color
        self.params_changed.emit()

    def _on_hue_target_picked(self, color: PsxColor) -> None:
        self._hue_target = color
        self.params_changed.emit()

    def _build_hue(self, layout: QFormLayout) -> None:
        self._hue_slider, self._hue_value = self._slider(-180, 180, "°")
        layout.addRow("Shift:", self._wrap(self._hue_slider, self._hue_value))

    def _build_saturation(self, layout: QFormLayout) -> None:
        self._saturation_slider, self._saturation_value = self._slider(
            -100, 100, "%",
        )
        layout.addRow(
            "Shift:", self._wrap(self._saturation_slider, self._saturation_value),
        )

    def _build_brightness(self, layout: QFormLayout) -> None:
        self._brightness_slider, self._brightness_value = self._slider(
            -100, 100, "%",
        )
        layout.addRow(
            "Shift:", self._wrap(self._brightness_slider, self._brightness_value),
        )

    def _build_rgb_delta(self, layout: QFormLayout) -> None:
        self._rgb_r_slider, self._rgb_r_value = self._slider(-255, 255, "")
        self._rgb_g_slider, self._rgb_g_value = self._slider(-255, 255, "")
        self._rgb_b_slider, self._rgb_b_value = self._slider(-255, 255, "")
        layout.addRow("Red:", self._wrap(self._rgb_r_slider, self._rgb_r_value))
        layout.addRow("Green:", self._wrap(self._rgb_g_slider, self._rgb_g_value))
        layout.addRow("Blue:", self._wrap(self._rgb_b_slider, self._rgb_b_value))

    def _slider(
        self, minimum: int, maximum: int, suffix: str,
    ) -> tuple[QSlider, QLabel]:
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(minimum, maximum)
        slider.setValue(0)
        slider.setTickPosition(QSlider.TickPosition.NoTicks)

        label = QLabel(f"0{suffix}")
        label.setMinimumWidth(52)
        label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        )

        slider.valueChanged.connect(lambda v: label.setText(f"{v:+d}{suffix}"))
        slider.valueChanged.connect(self.params_changed)
        return slider, label

    def _wrap(self, slider: QSlider, label: QLabel) -> QWidget:
        wrap = QWidget()
        layout = QHBoxLayout(wrap)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(slider, 1)
        layout.addWidget(label)
        return wrap
