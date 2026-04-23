# coding: utf-8

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from paintjob_designer.color.converter import ColorConverter
from paintjob_designer.constants import CLUT_PALETTE_SIZE
from paintjob_designer.gui.widget.psx_color_button import PsxColorButton
from paintjob_designer.models import Palette, PsxColor

_MAX_COLORS = CLUT_PALETTE_SIZE


class PaletteEditDialog(QDialog):
    """Name + ordered color list editor for one `Palette`."""

    def __init__(
        self,
        palette: Palette,
        color_converter: ColorConverter,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit palette")
        self._converter = color_converter

        self._name_edit = QLineEdit(palette.name)
        self._name_edit.setPlaceholderText("e.g. Sunset — warm oranges")
        self._colors: list[PsxColor] = [
            PsxColor(value=c.value) for c in palette.colors
        ]

        layout = QVBoxLayout(self)

        form = QFormLayout()
        form.addRow("Name:", self._name_edit)
        layout.addLayout(form)

        layout.addWidget(QLabel(
            "Colors (drag order determines slot mapping on apply; "
            f"max {_MAX_COLORS}):"
        ))

        self._colors_container = QWidget()
        self._colors_layout = QVBoxLayout(self._colors_container)
        self._colors_layout.setContentsMargins(0, 0, 0, 0)
        self._colors_layout.setSpacing(4)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._colors_container)
        scroll.setMinimumHeight(260)
        layout.addWidget(scroll, 1)

        add_row = QHBoxLayout()
        self._add_button = QPushButton("Add color")
        self._add_button.clicked.connect(self._on_add_clicked)
        add_row.addWidget(self._add_button)
        add_row.addStretch()
        layout.addLayout(add_row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._rebuild_color_rows()
        self.resize(480, 540)

    def resulting_palette(self) -> Palette:
        return Palette(
            name=self._name_edit.text().strip(),
            colors=[PsxColor(value=c.value) for c in self._colors],
        )

    def _on_accept(self) -> None:
        if not self._colors:
            QMessageBox.warning(
                self, "Palette is empty",
                "Add at least one color — an empty palette has no colors to apply.",
            )

            return

        self.accept()

    def _on_add_clicked(self) -> None:
        if len(self._colors) >= _MAX_COLORS:
            return

        self._colors.append(PsxColor(value=0x7FFF))  # white, stp=0
        self._rebuild_color_rows()

    def _rebuild_color_rows(self) -> None:
        # Clear existing rows
        while self._colors_layout.count():
            child = self._colors_layout.takeAt(0)
            widget = child.widget()
            if widget is not None:
                widget.deleteLater()

        for i, color in enumerate(self._colors):
            self._colors_layout.addWidget(self._build_color_row(i, color))

        self._colors_layout.addStretch()
        self._add_button.setEnabled(len(self._colors) < _MAX_COLORS)

    def _build_color_row(self, index: int, color: PsxColor) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        index_label = QLabel(f"[{index:02d}]")
        index_label.setMinimumWidth(36)
        layout.addWidget(index_label)

        button = PsxColorButton(self._converter, color, parent=row)
        button.color_picked.connect(lambda c, i=index: self._on_color_picked(i, c))
        layout.addWidget(button)

        up = QPushButton("▲")
        up.setFixedWidth(28)
        up.setEnabled(index > 0)
        up.clicked.connect(lambda _=False, i=index: self._on_move_up(i))
        layout.addWidget(up)

        down = QPushButton("▼")
        down.setFixedWidth(28)
        down.setEnabled(index < len(self._colors) - 1)
        down.clicked.connect(lambda _=False, i=index: self._on_move_down(i))
        layout.addWidget(down)

        remove = QPushButton("✕")
        remove.setFixedWidth(28)
        remove.setToolTip("Remove this color")
        remove.clicked.connect(lambda _=False, i=index: self._on_remove(i))
        layout.addWidget(remove)

        layout.addStretch()
        return row

    def _on_color_picked(self, index: int, color: PsxColor) -> None:
        if 0 <= index < len(self._colors):
            self._colors[index] = color

    def _on_move_up(self, index: int) -> None:
        if index <= 0 or index >= len(self._colors):
            return

        self._colors[index - 1], self._colors[index] = (
            self._colors[index], self._colors[index - 1],
        )
        self._rebuild_color_rows()

    def _on_move_down(self, index: int) -> None:
        if index < 0 or index >= len(self._colors) - 1:
            return

        self._colors[index], self._colors[index + 1] = (
            self._colors[index + 1], self._colors[index],
        )
        self._rebuild_color_rows()

    def _on_remove(self, index: int) -> None:
        if 0 <= index < len(self._colors):
            self._colors.pop(index)
            self._rebuild_color_rows()
