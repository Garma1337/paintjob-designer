# coding: utf-8

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QFrame


_TRANSPARENCY_BORDER_COLOR = QColor(0xE0, 0x84, 0x1E)


class ColorSwatch(QFrame):
    """Small fixed-size clickable tile displaying one CLUT color.

    Emits `clicked()` on a left-button press. The owning `SlotEditor` wires that
    up knowing which (slot_name, color_index) this swatch belongs to, so the
    swatch itself stays dumb.

    Transparent colors (PSX value 0x0000 convention) are drawn as a black tile
    with a single white diagonal so the user can tell them from a genuinely
    black pixel. Callers may also mark a swatch as an "index-zero" transparency
    slot via `mark_as_transparency_index` — it gets a thicker warm border and a
    tooltip so users notice the PSX convention before they edit away the
    transparency.
    """

    clicked = Signal()
    right_clicked = Signal()

    _SIZE = 22

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedSize(self._SIZE, self._SIZE)
        self.setFrameShape(QFrame.Shape.Panel)
        self.setFrameShadow(QFrame.Shadow.Sunken)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._color = QColor(0, 0, 0, 0)
        self._is_transparency_index = False

    def mark_as_transparency_index(self) -> None:
        """Tag this swatch as the PSX index-0 transparency slot.

        Visually distinguishes it (warm 2-pixel border) and adds a tooltip so
        the user understands that replacing this color will make the whole
        slot opaque in-game.
        """
        self._is_transparency_index = True
        self.setToolTip(
            "Index 0 is the PSX transparency sentinel. Setting a non-black "
            "color here will make this slot opaque in-game."
        )
        self.update()

    def set_color(self, r: int, g: int, b: int, a: int = 255) -> None:
        self._color = QColor(r, g, b, a)
        self.update()

    def set_transparent(self) -> None:
        self._color = QColor(0, 0, 0, 0)
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        inner = self.rect().adjusted(2, 2, -2, -2)

        if self._color.alpha() == 0:
            painter.fillRect(inner, Qt.GlobalColor.black)
            pen = QPen(Qt.GlobalColor.white)
            pen.setWidth(1)
            painter.setPen(pen)
            painter.drawLine(inner.topLeft(), inner.bottomRight())
        else:
            painter.fillRect(inner, self._color)

        if self._is_transparency_index:
            border = QPen(_TRANSPARENCY_BORDER_COLOR)
            border.setWidth(2)
            painter.setPen(border)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(inner.adjusted(0, 0, -1, -1))

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        elif event.button() == Qt.MouseButton.RightButton:
            # Right-click opens a "Transform colors..." context menu handled by
            # the owning SlotEditor; the swatch itself stays dumb about it.
            self.right_clicked.emit()

        super().mousePressEvent(event)
