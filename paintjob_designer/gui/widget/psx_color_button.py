# coding: utf-8

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QColorDialog, QPushButton, QWidget

from paintjob_designer.color.converter import ColorConverter
from paintjob_designer.models import PsxColor, Rgb888


class PsxColorButton(QPushButton):
    """Push-button that shows a PSX color and opens `QColorDialog` on click.

    Extracted from the Transform Colors + Gradient Fill dialogs — both had a
    near-identical private `_ColorButton`, which is exactly the kind of
    drift-prone duplication that's easy to let grow quietly.

    The stylesheet is scoped to the button's object name so it doesn't
    cascade into the dialog's other QPushButtons (Apply / Cancel / Preview).
    """

    color_picked = Signal(PsxColor)

    _SIZE = (120, 28)
    _OBJECT_NAME = "psxColorButton"

    def __init__(
        self,
        color_converter: ColorConverter,
        initial: PsxColor,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName(self._OBJECT_NAME)
        self._converter = color_converter
        self._color = initial
        self.setFixedSize(*self._SIZE)
        self.clicked.connect(self._open_picker)
        self._refresh()

    def color(self) -> PsxColor:
        return self._color

    def set_color(self, color: PsxColor) -> None:
        self._color = color
        self._refresh()

    def _refresh(self) -> None:
        rgb = self._converter.psx_to_rgb(self._color)
        self.setText(self._converter.psx_to_u16_hex(self._color))
        # Light-on-dark or dark-on-light depending on perceived brightness
        # so the hex label stays readable across the picker's whole range.
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
