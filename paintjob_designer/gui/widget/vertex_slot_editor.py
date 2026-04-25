# coding: utf-8

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from paintjob_designer.models import Rgb888


_COLUMNS = 4
_BUTTON_W = 88
_BUTTON_H = 28


class VertexSlotEditor(QWidget):
    """Editor for per-gouraud-index color overrides on a Skin."""

    color_edited = Signal(int, Rgb888)
    transform_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self._colors: list[Rgb888] = []
        self._buttons: list[QPushButton] = []
        self._enabled = False
        self._empty_label = QLabel(
            "No character loaded — vertex slots appear here once a "
            "character is in preview.",
        )
        self._empty_label.setWordWrap(True)
        self._empty_label.setStyleSheet("color: #888; padding: 12px;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        self._transform_button = QPushButton("Transform...")
        self._transform_button.setToolTip(
            "Apply Hue / Saturation / Brightness / RGB transforms to "
            "every vertex color in the active skin.",
        )
        self._transform_button.clicked.connect(self.transform_requested)
        button_row.addWidget(self._transform_button)
        button_row.addStretch()
        layout.addLayout(button_row)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        self._content = QWidget()
        self._grid = QGridLayout(self._content)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(3)
        self._grid.addWidget(self._empty_label, 0, 0, 1, _COLUMNS)

        self._scroll.setWidget(self._content)
        layout.addWidget(self._scroll, 1)

        self._transform_button.setEnabled(False)

    def set_colors(self, colors: list[Rgb888]) -> None:
        """Rebuild the swatch grid for a new character's gouraud table."""
        self._clear_buttons()
        self._colors = list(colors)

        if not self._colors:
            self._empty_label.show()
            return

        self._empty_label.hide()

        for i, color in enumerate(self._colors):
            btn = QPushButton(f"v{i}")
            btn.setFixedSize(_BUTTON_W, _BUTTON_H)
            self.style_button(btn, color)
            btn.clicked.connect(lambda _checked=False, idx=i: self._open_picker(idx))
            self._grid.addWidget(btn, i // _COLUMNS, i % _COLUMNS)
            self._buttons.append(btn)

        self._sync_enabled()

    def update_color(self, index: int, color: Rgb888) -> None:
        """Refresh one swatch after an override write."""
        if 0 <= index < len(self._buttons):
            self._colors[index] = color
            self.style_button(self._buttons[index], color)

    def set_editable(self, editable: bool) -> None:
        """Enable / disable all swatches in lockstep."""
        self._enabled = editable
        self._sync_enabled()

    def _open_picker(self, index: int) -> None:
        if not self._enabled or index >= len(self._colors):
            return

        current = self._colors[index]
        chosen = QColorDialog.getColor(
            QColor(current.r, current.g, current.b),
            self,
            f"Pick color for v{index}",
            QColorDialog.ColorDialogOption.DontUseNativeDialog,
        )

        if not chosen.isValid():
            return

        new_color = Rgb888(r=chosen.red(), g=chosen.green(), b=chosen.blue())
        if (new_color.r, new_color.g, new_color.b) == (current.r, current.g, current.b):
            return

        self.update_color(index, new_color)
        self.color_edited.emit(index, new_color)

    def _clear_buttons(self) -> None:
        for btn in self._buttons:
            self._grid.removeWidget(btn)
            btn.deleteLater()

        self._buttons.clear()

    def _sync_enabled(self) -> None:
        for btn in self._buttons:
            btn.setEnabled(self._enabled)

        # Transform makes no sense without a target asset and a
        # populated color list — track the same enable signal as the
        # per-swatch buttons.
        self._transform_button.setEnabled(self._enabled and bool(self._colors))

    @staticmethod
    def style_button(btn: QPushButton, color: Rgb888) -> None:
        # Light-on-dark / dark-on-light label so the index stays readable
        # across the full color range.
        lum = (color.r * 299 + color.g * 587 + color.b * 114) // 1000
        fg = "#000" if lum > 140 else "#fff"

        btn.setStyleSheet(
            f"QPushButton {{ background-color: rgb({color.r},{color.g},{color.b}); "
            f"color: {fg}; border: 1px solid #222; }}"
        )
