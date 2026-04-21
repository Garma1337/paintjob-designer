# coding: utf-8

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QFontMetrics, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QVBoxLayout,
    QWidget,
)

from paintjob_designer.color.converter import ColorConverter
from paintjob_designer.models import Palette, PsxColor


class _MappingRowDelegate(QStyledItemDelegate):
    """Row showing `slot[NN] ← palette color (#xxxx)` with a chip.

    Position in the list IS the target slot color index — drag to reorder
    to remap. The leading index label updates as rows move because the row
    redraws on every model change.
    """

    COLOR_ROLE = Qt.ItemDataRole.UserRole + 1

    _PADDING_X = 8
    _PADDING_Y = 4
    _CHIP_SIZE = 18
    _CHIP_GAP = 10

    def __init__(self, color_converter: ColorConverter, parent=None) -> None:
        super().__init__(parent)
        self._converter = color_converter

    def paint(self, painter, option, index) -> None:
        painter.save()

        widget = option.widget
        style = widget.style() if widget else QApplication.style()

        background_opt = QStyleOptionViewItem(option)
        background_opt.text = ""
        style.drawControl(
            QStyle.ControlElement.CE_ItemViewItem, background_opt, painter, widget,
        )

        color = index.data(self.COLOR_ROLE)

        fg = option.palette.color(QPalette.ColorRole.Text)
        if option.state & QStyle.StateFlag.State_Selected:
            fg = option.palette.color(QPalette.ColorRole.HighlightedText)

        rect = option.rect
        text_rect = rect.adjusted(
            self._PADDING_X, self._PADDING_Y, -self._PADDING_X, -self._PADDING_Y,
        )

        fm = QFontMetrics(option.font)
        row_position = index.row()

        label = f"slot[{row_position:02d}]  ←"
        painter.setFont(option.font)
        painter.setPen(fg)
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            label,
        )

        label_w = fm.horizontalAdvance(label)
        chip_x = text_rect.left() + label_w + self._CHIP_GAP
        chip_y = text_rect.top() + (text_rect.height() - self._CHIP_SIZE) // 2

        if color is not None:
            rgb = self._converter.psx_to_rgb(color)
            painter.fillRect(
                QRect(chip_x, chip_y, self._CHIP_SIZE, self._CHIP_SIZE),
                QColor(rgb.r, rgb.g, rgb.b),
            )
            painter.setPen(QColor(0, 0, 0, 80))
            painter.drawRect(
                QRect(chip_x, chip_y, self._CHIP_SIZE - 1, self._CHIP_SIZE - 1),
            )

            hex_text = self._converter.psx_to_u16_hex(color)
            hex_rect = QRect(
                chip_x + self._CHIP_SIZE + self._CHIP_GAP, text_rect.top(),
                text_rect.right() - (chip_x + self._CHIP_SIZE + self._CHIP_GAP),
                text_rect.height(),
            )
            painter.setPen(fg)
            painter.drawText(
                hex_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                hex_text,
            )

        painter.restore()

    def sizeHint(self, option, index) -> QSize:
        h = max(self._CHIP_SIZE, QFontMetrics(option.font).height()) + self._PADDING_Y * 2
        return QSize(option.rect.width(), h)


class PaletteApplyDialog(QDialog):
    """Reorderable mapping of a palette's entries onto a slot's color indices.

    Position in the list IS the target slot color index: the entry at row 0
    overwrites slot color 0, row 1 overwrites slot color 1, and so on. The
    user drags rows to change the mapping. Any slot colors past the palette's
    length are left untouched.
    """

    def __init__(
        self,
        palette: Palette,
        paintjob_name: str,
        slot_name: str,
        color_converter: ColorConverter,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Apply palette")
        self._converter = color_converter

        layout = QVBoxLayout(self)

        header = QLabel(
            f"Applying '<b>{palette.name or '(unnamed)'}</b>' to "
            f"paintjob '<b>{paintjob_name or '(unnamed)'}</b>', "
            f"slot '<b>{slot_name}</b>'.<br>"
            f"Drag entries to change which palette color lands on each slot index. "
            f"Trailing slot colors are left untouched."
        )
        header.setWordWrap(True)
        layout.addWidget(header)

        self._list = QListWidget()
        self._list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self._list.setItemDelegate(_MappingRowDelegate(self._converter, self._list))
        # Row moves need a redraw of *all* rows since the left-column
        # slot index comes from the row position, not from item data.
        self._list.model().rowsMoved.connect(
            lambda *_: self._list.viewport().update(),
        )

        for color in palette.colors:
            item = QListWidgetItem()
            item.setData(
                _MappingRowDelegate.COLOR_ROLE, PsxColor(value=color.value),
            )
            self._list.addItem(item)
        layout.addWidget(self._list, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.resize(420, 520)

    def ordered_colors(self) -> list[PsxColor]:
        """Return palette colors in their current (possibly reordered) list order."""
        result: list[PsxColor] = []
        for row in range(self._list.count()):
            item = self._list.item(row)
            color = item.data(_MappingRowDelegate.COLOR_ROLE)
            if color is not None:
                result.append(color)
        return result
