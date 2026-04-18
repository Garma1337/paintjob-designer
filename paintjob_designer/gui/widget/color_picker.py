# coding: utf-8

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QColorDialog, QWidget

from paintjob_designer.color.converter import ColorConverter
from paintjob_designer.models import PsxColor, Rgb888


class PsxColorPicker:
    """Opens a standard color dialog and snaps the result to the PSX 15-bit grid.

    Thin wrapper around `QColorDialog` — picking free-form RGB is fine, but what
    goes back into the paintjob is the 5-5-5 quantized value since that's what
    the game will actually display.
    """

    def __init__(self, color_converter: ColorConverter) -> None:
        self._colors = color_converter

    def pick(self, initial: PsxColor, parent: QWidget | None = None) -> PsxColor | None:
        rgb = self._colors.psx_to_rgb(initial)

        # Build a QColorDialog explicitly instead of the static `getColor` —
        # the native Windows colour picker is cramped and can't be resized, so
        # we opt out of it and give the Qt dialog a bigger default footprint.
        dialog = QColorDialog(QColor(rgb.r, rgb.g, rgb.b), parent)
        dialog.setWindowTitle("Pick CLUT color")
        dialog.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog, True)
        dialog.resize(1100, 640)

        if dialog.exec() != QColorDialog.DialogCode.Accepted:
            return None

        chosen = dialog.currentColor()
        if not chosen.isValid():
            return None

        picked = Rgb888(r=chosen.red(), g=chosen.green(), b=chosen.blue())
        return self._colors.rgb_to_psx(picked, stp=initial.stp)
