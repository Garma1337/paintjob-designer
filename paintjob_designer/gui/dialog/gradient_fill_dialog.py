# coding: utf-8

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from paintjob_designer.color.converter import ColorConverter
from paintjob_designer.color.gradient import (
    GradientGenerator,
    GradientSpace,
)
from paintjob_designer.gui.widget.psx_color_button import PsxColorButton
from paintjob_designer.models import PsxColor, SlotColors


class GradientFillDialog(QDialog):
    """Fill a contiguous range of a slot's 16 CLUT entries with a gradient.

    Inputs are the slot's current colors, the slot name (for labeling), and
    a color converter. On Accept the dialog exposes
    `resulting_replacements()` — a list of `(color_index, new_color)` pairs
    the caller can pack into a `BulkTransformCommand`. Only indices the
    range actually covers are returned, and only entries whose value
    differs from the current color (so a no-op gradient doesn't pollute
    the undo stack).
    """

    def __init__(
        self,
        slot_name: str,
        current_colors: list[PsxColor],
        color_converter: ColorConverter,
        gradient_generator: GradientGenerator,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Gradient Fill")
        self.resize(520, 380)

        self._slot_name = slot_name
        self._current_colors = list(current_colors)
        self._converter = color_converter
        self._generator = gradient_generator

        self._result: list[tuple[int, PsxColor]] = []

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(
            f"Fill a range of slot <b>{slot_name}</b>'s 16 colors with a gradient "
            f"between two endpoints.",
        ))

        form = QFormLayout()

        # Default endpoints: index 0's color (often transparent on PSX) is a
        # bad default, so start from the slot's first non-sentinel entry and
        # the last entry.
        default_start = _first_non_sentinel(current_colors)
        default_end = current_colors[-1] if current_colors else PsxColor(value=0x8000)

        self._start_button = PsxColorButton(self._converter, default_start)
        self._start_button.color_picked.connect(lambda _: self._refresh_preview())
        form.addRow("Start color:", self._start_button)

        self._end_button = PsxColorButton(self._converter, default_end)
        self._end_button.color_picked.connect(lambda _: self._refresh_preview())
        form.addRow("End color:", self._end_button)

        self._from_spin = QSpinBox()
        self._from_spin.setRange(0, SlotColors.SIZE - 1)
        self._from_spin.setValue(1)  # skip PSX transparency sentinel by default
        self._from_spin.valueChanged.connect(self._on_range_changed)
        form.addRow("From index:", self._from_spin)

        self._to_spin = QSpinBox()
        self._to_spin.setRange(0, SlotColors.SIZE - 1)
        self._to_spin.setValue(SlotColors.SIZE - 1)
        self._to_spin.valueChanged.connect(self._on_range_changed)
        form.addRow("To index:", self._to_spin)

        self._space_combo = QComboBox()
        self._space_combo.addItem("RGB (linear per channel)", GradientSpace.RGB)
        self._space_combo.addItem("HSV (short arc on hue wheel)", GradientSpace.HSV)
        self._space_combo.currentIndexChanged.connect(self._refresh_preview)
        form.addRow("Color space:", self._space_combo)

        layout.addLayout(form)

        layout.addWidget(QLabel("Preview:"))
        self._preview = _GradientPreview(self._converter)
        layout.addWidget(self._preview)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Apply
            | QDialogButtonBox.StandardButton.Cancel,
        )
        self._apply_button = buttons.button(QDialogButtonBox.StandardButton.Apply)
        self._apply_button.clicked.connect(self._on_apply)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._refresh_preview()

    def resulting_replacements(self) -> list[tuple[int, PsxColor]]:
        """List of `(color_index, new_color)` the caller should apply.

        Empty when the dialog was cancelled or when the computed gradient
        matches the current slot colors exactly (so Apply is a no-op).
        """
        return list(self._result)

    def _on_range_changed(self) -> None:
        # Keep `from <= to`. Fudge the counterpart spin so the user can drag
        # either bound past the other without the preview going blank.
        if self._from_spin.value() > self._to_spin.value():
            sender = self.sender()
            if sender is self._from_spin:
                self._to_spin.setValue(self._from_spin.value())
            else:
                self._from_spin.setValue(self._to_spin.value())

        self._refresh_preview()

    def _compute_gradient(self) -> list[PsxColor]:
        from_idx = self._from_spin.value()
        to_idx = self._to_spin.value()
        count = to_idx - from_idx + 1

        if count <= 0:
            return []

        return self._generator.generate(
            start=self._start_button.color(),
            end=self._end_button.color(),
            count=count,
            space=self._space_combo.currentData(),
        )

    def _refresh_preview(self) -> None:
        gradient = self._compute_gradient()
        from_idx = self._from_spin.value()

        # Lay out a full 16-swatch strip so the preview always matches the
        # slot's physical layout; indices outside the range stay as they are
        # today, indices inside the range show their prospective gradient color.
        strip: list[PsxColor] = list(self._current_colors)
        for i, color in enumerate(gradient):
            target = from_idx + i
            if 0 <= target < len(strip):
                strip[target] = color

        self._preview.show_strip(
            strip,
            highlight_range=(from_idx, from_idx + len(gradient) - 1) if gradient else None,
        )

    def _on_apply(self) -> None:
        gradient = self._compute_gradient()
        from_idx = self._from_spin.value()

        replacements: list[tuple[int, PsxColor]] = []
        for i, color in enumerate(gradient):
            target = from_idx + i
            if 0 <= target < len(self._current_colors):
                if color.value != self._current_colors[target].value:
                    replacements.append((target, color))

        self._result = replacements
        self.accept()


class _GradientPreview(QFrame):
    """Draws the 16-swatch strip with the in-range indices tinted / framed.

    Indices inside the gradient range get their prospective color; indices
    outside show the current paintjob color (so the user can see the
    seam between what's changing and what stays). An orange frame marks
    the range itself.
    """

    def __init__(self, color_converter: ColorConverter) -> None:
        super().__init__()
        self._converter = color_converter
        self._strip: list[PsxColor] = []
        self._range: tuple[int, int] | None = None
        self.setMinimumHeight(64)

    def show_strip(
        self,
        colors: list[PsxColor],
        highlight_range: tuple[int, int] | None,
    ) -> None:
        self._strip = list(colors)
        self._range = highlight_range
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if not self._strip:
            return

        painter = QPainter(self)

        # Compute swatch size to fill width. Small internal margin so the
        # range-outline doesn't clip.
        margin = 8
        gap = 3
        total_gap = gap * (len(self._strip) - 1)
        w = max(10, (self.width() - margin * 2 - total_gap) // len(self._strip))
        h = min(40, self.height() - margin * 2 - 18)
        y = margin

        for i, color in enumerate(self._strip):
            x = margin + i * (w + gap)
            self._paint_swatch(painter, x, y, w, h, color)
            painter.setPen(QPen(QColor("#aaa")))
            painter.drawText(x, y + h + 14, f"{i}")

        if self._range is not None:
            lo, hi = self._range
            if 0 <= lo <= hi < len(self._strip):
                x0 = margin + lo * (w + gap) - 2
                x1 = margin + hi * (w + gap) + w + 2
                painter.setPen(QPen(QColor(0xE0, 0x84, 0x1E), 2))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(x0, y - 2, x1 - x0, h + 4)

    def _paint_swatch(
        self, painter: QPainter, x: int, y: int, w: int, h: int, color: PsxColor,
    ) -> None:
        if color.value == 0:
            painter.fillRect(x, y, w, h, QColor(0, 0, 0))
            painter.setPen(QPen(QColor("#fff")))
            painter.drawLine(x, y, x + w - 1, y + h - 1)
        else:
            rgb = self._converter.psx_to_rgb(color)
            painter.fillRect(x, y, w, h, QColor(rgb.r, rgb.g, rgb.b))

        painter.setPen(QPen(QColor("#222")))
        painter.drawRect(x, y, w - 1, h - 1)


def _first_non_sentinel(colors: list[PsxColor]) -> PsxColor:
    for c in colors:
        if c.value != 0:
            return c

    return PsxColor(value=0x8000)
