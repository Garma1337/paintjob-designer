# coding: utf-8

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QColorDialog, QWidget

from paintjob_designer.color.converter import ColorConverter
from paintjob_designer.models import PsxColor, Rgb888


class PsxColorPicker:
    """Opens a standard color dialog and snaps the result to the PSX 15-bit grid."""

    def __init__(self, color_converter: ColorConverter) -> None:
        self._colors = color_converter

    def pick(self, initial: PsxColor, parent: QWidget | None = None) -> PsxColor | None:
        rgb = self._colors.psx_to_rgb(initial)
        initial_alpha = 0 if initial.is_transparent else 255

        # Build a QColorDialog explicitly instead of the static `getColor` —
        # the native Windows colour picker is cramped and can't be resized, so
        # we opt out of it and give the Qt dialog a bigger default footprint.
        dialog = QColorDialog(QColor(rgb.r, rgb.g, rgb.b, initial_alpha), parent)
        dialog.setWindowTitle("Pick CLUT color")
        dialog.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog, True)
        dialog.setOption(QColorDialog.ColorDialogOption.ShowAlphaChannel, True)
        dialog.resize(1100, 640)

        if dialog.exec() != QColorDialog.DialogCode.Accepted:
            return None

        chosen = dialog.currentColor()
        if not chosen.isValid():
            return None

        # Alpha is binary on PSX: half-opacity isn't representable, so any
        # picked alpha below 128 collapses to the transparent sentinel.
        if chosen.alpha() < 128:
            return PsxColor(value=0)

        picked = Rgb888(r=chosen.red(), g=chosen.green(), b=chosen.blue())
        return self._colors.rgb_to_psx(picked, stp=initial.stp)
