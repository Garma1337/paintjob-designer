# coding: utf-8

from dataclasses import dataclass
from enum import Enum

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSlider,
    QStackedWidget,
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
from paintjob_designer.models import PsxColor, Rgb888, SlotRegions


@dataclass
class TransformCandidate:
    """One color in the paintjob the dialog is allowed to rewrite.

    `current_color` is the effective color (paintjob override if present, else
    the VRAM default) — preview math runs against it, and the `old_color` on
    the emitted `BulkColorEdit` is this value so undo restores the effective
    color rather than the raw paintjob entry (which may not have existed).
    """

    character_id: str
    slot: SlotRegions
    color_index: int
    current_color: PsxColor


class TransformScope(Enum):
    THIS_SLOT = "this_slot"
    ENTIRE_KART = "entire_kart"


_MODE_LABELS: list[tuple[TransformMode, str]] = [
    (TransformMode.REPLACE_MATCHES, "Replace matching color"),
    (TransformMode.SHIFT_HUE, "Shift hue"),
    (TransformMode.SHIFT_BRIGHTNESS, "Shift brightness"),
    (TransformMode.SHIFT_SATURATION, "Shift saturation"),
    (TransformMode.RGB_DELTA, "RGB delta"),
]


class TransformColorsDialog(QDialog):
    """Bulk color-transform dialog.

    Caller passes two candidate lists (one per scope) plus the current scope
    name for context, along with the transformer and a color converter. The
    dialog owns the controls and preview; on Accept it hands back the list of
    `BulkColorEdit` values the caller should push as a single undo entry.

    The dialog does not mutate the paintjob itself — that keeps Cancel trivial
    (no rollback needed) and lets the caller decide how to plumb the edits
    into the atlas / 3D viewer refresh path.
    """

    _PREVIEW_SWATCH_SIZE = 20
    _PREVIEW_MAX_ROWS = 128

    # Explicit user-triggered preview — only fires when the Preview button is
    # clicked, not on every slider tick. The main window uses this to push
    # the transform into the paintjob + 3D view so the user can see what
    # Apply would commit without actually committing it (Cancel rolls back).
    preview_requested = Signal(list)

    def __init__(
        self,
        slot_candidates: list[TransformCandidate],
        kart_candidates: list[TransformCandidate],
        color_transformer: ColorTransformer,
        color_converter: ColorConverter,
        initial_scope: TransformScope = TransformScope.THIS_SLOT,
        initial_match_color: PsxColor | None = None,
        initial_slot_label: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Transform Colors")
        self.resize(680, 560)

        self._slot_candidates = slot_candidates
        self._kart_candidates = kart_candidates
        self._transformer = color_transformer
        self._converter = color_converter
        self._initial_slot_label = initial_slot_label

        self._result_edits: list[BulkColorEdit] = []

        layout = QVBoxLayout(self)

        form = QFormLayout()

        self._scope_combo = QComboBox()
        self._scope_combo.addItem(
            f"Just this slot ({initial_slot_label})" if initial_slot_label else "Just this slot",
            TransformScope.THIS_SLOT,
        )

        self._scope_combo.addItem("Entire kart", TransformScope.ENTIRE_KART)
        if initial_scope == TransformScope.ENTIRE_KART:
            self._scope_combo.setCurrentIndex(1)

        if not slot_candidates:
            # No slot context to transform within — force kart scope and lock.
            self._scope_combo.setCurrentIndex(1)
            self._scope_combo.model().item(0).setEnabled(False)

        form.addRow("Scope:", self._scope_combo)

        self._mode_combo = QComboBox()
        for mode, label in _MODE_LABELS:
            self._mode_combo.addItem(label, mode)

        form.addRow("Operation:", self._mode_combo)

        layout.addLayout(form)

        self._controls = _ControlsStack(self._converter, initial_match_color)
        layout.addWidget(self._controls)

        self._summary_label = QLabel()
        self._summary_label.setStyleSheet("color: #aaa; padding: 4px 0;")
        layout.addWidget(self._summary_label)

        self._preview = _PreviewStrip(self._converter)
        scroller = QScrollArea()
        scroller.setWidgetResizable(True)
        scroller.setWidget(self._preview)
        scroller.setMinimumHeight(180)
        layout.addWidget(scroller, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Apply
            | QDialogButtonBox.StandardButton.Cancel,
        )

        self._apply_button = buttons.button(QDialogButtonBox.StandardButton.Apply)
        self._apply_button.clicked.connect(self._on_apply)

        # Preview button sits next to Cancel so the user can push the current
        # transform into the 3D view without committing. Added via addButton
        # on the ActionRole so it doesn't accept-or-reject the dialog.
        self._preview_button = buttons.addButton(
            "Preview", QDialogButtonBox.ButtonRole.ActionRole,
        )
        self._preview_button.clicked.connect(self._on_preview)

        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # Wire control signals after all widgets exist so the first refresh
        # sees a populated stacked widget. All changes refresh immediately —
        # the preview is only the internal swatch strip, not a 3D render, so
        # there's no per-tick cost worth debouncing.
        self._scope_combo.currentIndexChanged.connect(self._refresh_preview)
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        self._controls.params_changed.connect(self._refresh_preview)

        self._on_mode_changed()

    def resulting_edits(self) -> list[BulkColorEdit]:
        """Edits captured by the last Accept — empty if the dialog was cancelled."""
        return list(self._result_edits)

    def _on_mode_changed(self) -> None:
        mode = self._mode_combo.currentData()
        self._controls.set_mode(mode)
        self._refresh_preview()

    def _current_candidates(self) -> list[TransformCandidate]:
        scope = self._scope_combo.currentData()
        if scope == TransformScope.ENTIRE_KART:
            return self._kart_candidates

        return self._slot_candidates

    def _current_params(self) -> TransformParams:
        return self._controls.current_params(self._mode_combo.currentData())

    def _refresh_preview(self) -> None:
        edits = self._compute_edits()

        self._preview.show_edits(edits[: self._PREVIEW_MAX_ROWS])

        total_candidates = len(self._current_candidates())
        if not edits:
            self._summary_label.setText(
                f"No changes (0 of {total_candidates} colors match)"
            )
        else:
            truncated = len(edits) > self._PREVIEW_MAX_ROWS
            trunc_note = (
                f" (showing first {self._PREVIEW_MAX_ROWS})" if truncated else ""
            )
            self._summary_label.setText(
                f"{len(edits)} of {total_candidates} colors will change{trunc_note}"
            )

        self._apply_button.setEnabled(bool(edits))
        self._preview_button.setEnabled(bool(edits))

    def _compute_edits(self) -> list[BulkColorEdit]:
        params = self._current_params()
        edits: list[BulkColorEdit] = []

        for cand in self._current_candidates():
            new_color = self._transformer.transform(cand.current_color, params)
            if new_color.value != cand.current_color.value:
                edits.append(BulkColorEdit(
                    character_id=cand.character_id,
                    slot=cand.slot,
                    color_index=cand.color_index,
                    old_color=cand.current_color,
                    new_color=new_color,
                ))

        return edits

    def _on_apply(self) -> None:
        self._result_edits = self._compute_edits()
        self.accept()

    def _on_preview(self) -> None:
        self.preview_requested.emit(self._compute_edits())


class _ControlsStack(QWidget):
    """Mode-specific controls — one page per `TransformMode`.

    Emits `params_changed` when any control changes so the dialog can recompute
    its preview without peeking inside this widget.
    """

    params_changed = Signal()

    def __init__(
        self,
        color_converter: ColorConverter,
        initial_match_color: PsxColor | None,
    ) -> None:
        super().__init__()
        self._converter = color_converter

        self._stack = QStackedWidget()
        self._pages: dict[TransformMode, QWidget] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._stack)

        self._build_replace_page(initial_match_color)
        self._build_hue_page()
        self._build_brightness_page()
        self._build_saturation_page()
        self._build_rgb_delta_page()

    def set_mode(self, mode: TransformMode) -> None:
        page = self._pages.get(mode)
        if page is not None:
            self._stack.setCurrentWidget(page)

    def current_params(self, mode: TransformMode) -> TransformParams:
        if mode == TransformMode.REPLACE_MATCHES:
            return TransformParams(
                mode=mode,
                match_color=self._replace_match,
                replace_with=self._replace_target,
            )

        if mode == TransformMode.SHIFT_HUE:
            return TransformParams(
                mode=mode,
                hue_shift_degrees=float(self._hue_slider.value()),
            )

        if mode == TransformMode.SHIFT_BRIGHTNESS:
            return TransformParams(
                mode=mode,
                brightness_shift=self._brightness_slider.value() / 100.0,
            )

        if mode == TransformMode.SHIFT_SATURATION:
            return TransformParams(
                mode=mode,
                saturation_shift=self._saturation_slider.value() / 100.0,
            )

        if mode == TransformMode.RGB_DELTA:
            return TransformParams(
                mode=mode,
                rgb_delta_r=self._rgb_r_slider.value(),
                rgb_delta_g=self._rgb_g_slider.value(),
                rgb_delta_b=self._rgb_b_slider.value(),
            )

        return TransformParams(mode=mode)

    def _build_replace_page(self, initial_match_color: PsxColor | None) -> None:
        page = QWidget()
        layout = QFormLayout(page)

        self._replace_match = initial_match_color or PsxColor(value=0x8000)
        self._replace_target = initial_match_color or PsxColor(value=0x8000)

        self._match_button = _ColorButton(self._converter, self._replace_match)
        self._match_button.color_picked.connect(self._on_match_picked)
        layout.addRow("Match:", self._match_button)

        self._target_button = _ColorButton(self._converter, self._replace_target)
        self._target_button.color_picked.connect(self._on_target_picked)
        layout.addRow("Replace with:", self._target_button)

        hint = QLabel(
            "Every color whose u16 equals the 'Match' value will be replaced "
            "with the 'Replace with' value. The stp (transparency) bit is part "
            "of the match, so transparent-index-0 entries are never touched."
        )

        hint.setWordWrap(True)
        hint.setStyleSheet("color: #888;")
        layout.addRow(hint)

        self._stack.addWidget(page)
        self._pages[TransformMode.REPLACE_MATCHES] = page

    def _on_match_picked(self, color: PsxColor) -> None:
        self._replace_match = color
        self.params_changed.emit()

    def _on_target_picked(self, color: PsxColor) -> None:
        self._replace_target = color
        self.params_changed.emit()

    def _build_hue_page(self) -> None:
        page = QWidget()
        layout = QFormLayout(page)

        self._hue_slider = _make_slider(-180, 180, 0)
        self._hue_value = QLabel("0°")
        self._hue_slider.valueChanged.connect(
            lambda v: self._hue_value.setText(f"{v:+d}°"),
        )
        self._hue_slider.valueChanged.connect(self.params_changed)
        layout.addRow("Hue shift:", _slider_with_label(self._hue_slider, self._hue_value))

        self._stack.addWidget(page)
        self._pages[TransformMode.SHIFT_HUE] = page

    def _build_brightness_page(self) -> None:
        page = QWidget()
        layout = QFormLayout(page)

        # Slider range is ±100 so the user feels 1% steps; we divide by 100 in
        # `current_params` to land on a [-1, 1] float the transformer wants.
        self._brightness_slider = _make_slider(-100, 100, 0)
        self._brightness_value = QLabel("0%")
        self._brightness_slider.valueChanged.connect(
            lambda v: self._brightness_value.setText(f"{v:+d}%"),
        )
        self._brightness_slider.valueChanged.connect(self.params_changed)
        layout.addRow(
            "Brightness shift:",
            _slider_with_label(self._brightness_slider, self._brightness_value),
        )

        self._stack.addWidget(page)
        self._pages[TransformMode.SHIFT_BRIGHTNESS] = page

    def _build_saturation_page(self) -> None:
        page = QWidget()
        layout = QFormLayout(page)

        self._saturation_slider = _make_slider(-100, 100, 0)
        self._saturation_value = QLabel("0%")
        self._saturation_slider.valueChanged.connect(
            lambda v: self._saturation_value.setText(f"{v:+d}%"),
        )
        self._saturation_slider.valueChanged.connect(self.params_changed)
        layout.addRow(
            "Saturation shift:",
            _slider_with_label(self._saturation_slider, self._saturation_value),
        )

        self._stack.addWidget(page)
        self._pages[TransformMode.SHIFT_SATURATION] = page

    def _build_rgb_delta_page(self) -> None:
        page = QWidget()
        layout = QFormLayout(page)

        self._rgb_r_slider = _make_slider(-255, 255, 0)
        self._rgb_r_value = QLabel("0")
        self._rgb_r_slider.valueChanged.connect(
            lambda v: self._rgb_r_value.setText(f"{v:+d}"),
        )
        self._rgb_r_slider.valueChanged.connect(self.params_changed)
        layout.addRow("Red:", _slider_with_label(self._rgb_r_slider, self._rgb_r_value))

        self._rgb_g_slider = _make_slider(-255, 255, 0)
        self._rgb_g_value = QLabel("0")
        self._rgb_g_slider.valueChanged.connect(
            lambda v: self._rgb_g_value.setText(f"{v:+d}"),
        )
        self._rgb_g_slider.valueChanged.connect(self.params_changed)
        layout.addRow("Green:", _slider_with_label(self._rgb_g_slider, self._rgb_g_value))

        self._rgb_b_slider = _make_slider(-255, 255, 0)
        self._rgb_b_value = QLabel("0")
        self._rgb_b_slider.valueChanged.connect(
            lambda v: self._rgb_b_value.setText(f"{v:+d}"),
        )
        self._rgb_b_slider.valueChanged.connect(self.params_changed)
        layout.addRow("Blue:", _slider_with_label(self._rgb_b_slider, self._rgb_b_value))

        self._stack.addWidget(page)
        self._pages[TransformMode.RGB_DELTA] = page


class _ColorButton(QPushButton):
    """Push-button that shows a PSX color and opens a QColorDialog on click."""

    color_picked = Signal(PsxColor)

    _SIZE = (120, 28)
    _OBJECT_NAME = "transformColorButton"

    def __init__(self, color_converter: ColorConverter, initial: PsxColor) -> None:
        super().__init__()
        # Scoped objectName so the stylesheet only targets this button —
        # without it, the generic `QPushButton` selector cascades to the
        # dialog's Apply/Cancel buttons and they end up colored too.
        self.setObjectName(self._OBJECT_NAME)
        self._converter = color_converter
        self._color = initial
        self.setFixedSize(*self._SIZE)
        self.clicked.connect(self._open_picker)
        self._refresh()

    def set_color(self, color: PsxColor) -> None:
        self._color = color
        self._refresh()

    def _refresh(self) -> None:
        rgb = self._converter.psx_to_rgb(self._color)
        self.setText(self._converter.psx_to_u16_hex(self._color))
        # Light-on-dark or dark-on-light depending on perceived brightness so
        # the hex label stays readable across the picker's whole range.
        lum = (rgb.r * 299 + rgb.g * 587 + rgb.b * 114) // 1000
        fg = "#000" if lum > 140 else "#fff"
        self.setStyleSheet(
            f"QPushButton#{self._OBJECT_NAME} {{ "
            f"background-color: rgb({rgb.r},{rgb.g},{rgb.b}); "
            f"color: {fg}; border: 1px solid #222; }}"
        )

    def _open_picker(self) -> None:
        current = self._converter.psx_to_rgb(self._color)
        initial_q = QColor(current.r, current.g, current.b)
        chosen = QColorDialog.getColor(
            initial_q,
            self,
            "Pick color",
            QColorDialog.ColorDialogOption.DontUseNativeDialog,
        )

        if not chosen.isValid():
            return

        psx = self._converter.rgb_to_psx(
            Rgb888(r=chosen.red(), g=chosen.green(), b=chosen.blue()),
            stp=self._color.stp,
        )
        self.set_color(psx)
        self.color_picked.emit(psx)


class _PreviewStrip(QFrame):
    """Renders a grid of before → after swatches for the changed colors.

    Two swatches per row (old, new) plus a hex label so the user can spot
    exact PSX values. Plain QFrame with a custom `paintEvent` instead of a
    grid of widgets — redrawing 128 rows of widgets is laggier than drawing
    them ourselves in one pass.
    """

    def __init__(self, color_converter: ColorConverter) -> None:
        super().__init__()
        self._converter = color_converter
        self._rows: list[tuple[PsxColor, PsxColor]] = []
        self.setMinimumHeight(80)

    def show_edits(self, edits: list[BulkColorEdit]) -> None:
        self._rows = [(e.old_color, e.new_color) for e in edits]
        self._update_layout()
        self.update()

    def _update_layout(self) -> None:
        # Dynamically resize the widget height so the QScrollArea gives us
        # vertical scrolling for dense change sets instead of clipping.
        row_height = 24
        padding = 8
        self.setMinimumHeight(max(80, padding * 2 + row_height * len(self._rows)))

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if not self._rows:
            painter = QPainter(self)
            painter.setPen(QPen(QColor("#888")))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No colors will change with the current settings.")
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        swatch = 20
        gap = 6
        x0 = 8
        y = 8

        for old, new in self._rows:
            self._paint_swatch(painter, x0, y, swatch, old)
            painter.setPen(QPen(QColor("#888")))
            painter.drawText(
                x0 + swatch + gap, y + swatch - 4, "→",
            )
            self._paint_swatch(painter, x0 + swatch + gap + 14, y, swatch, new)

            hex_text = (
                f"{self._converter.psx_to_u16_hex(old)}  →  "
                f"{self._converter.psx_to_u16_hex(new)}"
            )
            painter.setPen(QPen(QColor("#ccc")))
            painter.drawText(
                x0 + (swatch + gap) * 2 + 14, y + swatch - 4, hex_text,
            )

            y += swatch + 4

    def _paint_swatch(
        self, painter: QPainter, x: int, y: int, size: int, color: PsxColor,
    ) -> None:
        if color.value == 0:
            painter.fillRect(x, y, size, size, QColor(0, 0, 0))
            painter.setPen(QPen(QColor("#fff")))
            painter.drawLine(x, y, x + size - 1, y + size - 1)
        else:
            rgb = self._converter.psx_to_rgb(color)
            painter.fillRect(x, y, size, size, QColor(rgb.r, rgb.g, rgb.b))

        painter.setPen(QPen(QColor("#222")))
        painter.drawRect(x, y, size - 1, size - 1)


def _make_slider(minimum: int, maximum: int, value: int) -> QSlider:
    slider = QSlider(Qt.Orientation.Horizontal)
    slider.setRange(minimum, maximum)
    slider.setValue(value)
    slider.setTickPosition(QSlider.TickPosition.NoTicks)
    return slider


def _slider_with_label(slider: QSlider, label: QLabel) -> QWidget:
    wrap = QWidget()
    layout = QHBoxLayout(wrap)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(slider, 1)
    label.setMinimumWidth(48)
    label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    layout.addWidget(label)
    return wrap
