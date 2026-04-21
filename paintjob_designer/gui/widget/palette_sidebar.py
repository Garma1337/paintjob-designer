# coding: utf-8

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFontMetrics, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QVBoxLayout,
    QWidget, QMenu,
)

from paintjob_designer.color.converter import ColorConverter
from paintjob_designer.models import Palette


class _PaletteRowDelegate(QStyledItemDelegate):
    """Two-line row: palette name on top, color chip strip below.

    Using a delegate keeps drag-reorders cheap and stops attached
    widgets from drifting out of sync with the underlying model — same
    rationale as the paintjob sidebar's delegate.
    """

    PALETTE_ROLE = Qt.ItemDataRole.UserRole + 1

    _PADDING_X = 6
    _PADDING_Y = 4
    _LINE_GAP = 3
    _CHIP_SIZE = 12
    _CHIP_GAP = 2
    _PLACEHOLDER_ALPHA = 140

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

        name = index.data(Qt.ItemDataRole.DisplayRole) or ""
        palette = index.data(self.PALETTE_ROLE)

        primary_color, muted_color = _PaletteRowDelegate.text_colors(
            option, self._PLACEHOLDER_ALPHA,
        )

        rect = option.rect
        text_rect = rect.adjusted(
            self._PADDING_X, self._PADDING_Y, -self._PADDING_X, -self._PADDING_Y,
        )

        primary_font = option.font
        fm_primary = QFontMetrics(primary_font)

        painter.setFont(primary_font)
        painter.setPen(primary_color)
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
            name or "(unnamed palette)",
        )

        chips_y = text_rect.top() + fm_primary.height() + self._LINE_GAP
        if palette is not None and palette.colors:
            x = text_rect.left()
            for color in palette.colors:
                rgb = self._converter.psx_to_rgb(color)
                painter.fillRect(
                    QRect(x, chips_y, self._CHIP_SIZE, self._CHIP_SIZE),
                    QColor(rgb.r, rgb.g, rgb.b),
                )
                painter.setPen(QColor(0, 0, 0, 60))
                painter.drawRect(
                    QRect(x, chips_y, self._CHIP_SIZE - 1, self._CHIP_SIZE - 1),
                )
                x += self._CHIP_SIZE + self._CHIP_GAP
        else:
            painter.setFont(primary_font)
            painter.setPen(muted_color)
            painter.drawText(
                QRect(text_rect.left(), chips_y, text_rect.width(), self._CHIP_SIZE),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                "(empty — click Save from Slot or Edit to fill)",
            )

        painter.restore()

    def sizeHint(self, option, index) -> QSize:
        primary_h = QFontMetrics(option.font).height()
        total = self._PADDING_Y * 2 + primary_h + self._LINE_GAP + self._CHIP_SIZE
        return QSize(option.rect.width(), total)

    @staticmethod
    def text_colors(option, muted_alpha: int) -> tuple[QColor, QColor]:
        if option.state & QStyle.StateFlag.State_Selected:
            foreground = option.palette.color(QPalette.ColorRole.HighlightedText)
            background = option.palette.color(QPalette.ColorRole.Highlight)
        else:
            foreground = option.palette.color(QPalette.ColorRole.Text)
            background = option.palette.color(QPalette.ColorRole.Base)

        background_is_dark = _PaletteRowDelegate.is_dark(background)
        if _PaletteRowDelegate.is_dark(foreground) == background_is_dark:
            primary = QColor("#eaeaea") if background_is_dark else QColor("#202020")
        else:
            primary = foreground

        muted = QColor(primary)
        muted.setAlpha(muted_alpha)
        return primary, muted

    @staticmethod
    def is_dark(color: QColor) -> bool:
        luminance = (color.red() * 299 + color.green() * 587 + color.blue() * 114) / 1000
        return luminance < 128


class PaletteSidebar(QWidget):
    """List of saved color palettes with New / Save-from-slot / Edit / Delete.

    Purely a view — the main window owns the palette library and pushes state
    back via `set_palettes` on each change.

    Emits:
        - `palette_selected(index)` when the current row changes.
        - `new_palette_requested()` / `save_from_slot_requested()` /
          `delete_palette_requested(index)` / `edit_palette_requested(index)` /
          `rename_palette_requested(index)` for the corresponding toolbar /
          context-menu actions.
    """

    palette_selected = Signal(int)
    new_palette_requested = Signal()
    save_from_slot_requested = Signal()
    delete_palette_requested = Signal(int)
    edit_palette_requested = Signal(int)
    rename_palette_requested = Signal(int)

    def __init__(
        self,
        color_converter: ColorConverter,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._converter = color_converter

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._list = QListWidget()
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.setItemDelegate(_PaletteRowDelegate(self._converter, self._list))
        self._list.currentRowChanged.connect(self._on_row_changed)
        self._list.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._list.customContextMenuRequested.connect(self._on_context_menu_requested)
        layout.addWidget(self._list, 1)

        button_row_1 = QHBoxLayout()
        button_row_1.setContentsMargins(0, 0, 0, 0)
        self._new_button = QPushButton("New")
        self._new_button.setToolTip("Create an empty palette — edit it to add colors.")
        self._new_button.clicked.connect(self.new_palette_requested)
        button_row_1.addWidget(self._new_button)

        self._save_slot_button = QPushButton("From Slot")
        self._save_slot_button.setToolTip(
            "Save the currently-focused slot's 16 colors as a new palette.",
        )
        self._save_slot_button.clicked.connect(self.save_from_slot_requested)
        button_row_1.addWidget(self._save_slot_button)

        button_row_1.addStretch()
        layout.addLayout(button_row_1)

        button_row_2 = QHBoxLayout()
        button_row_2.setContentsMargins(0, 0, 0, 0)
        self._edit_button = QPushButton("Edit")
        self._edit_button.setToolTip(
            "Rename and edit the colors of the selected palette.",
        )
        self._edit_button.clicked.connect(self._on_edit_clicked)
        button_row_2.addWidget(self._edit_button)

        self._delete_button = QPushButton("Delete")
        self._delete_button.setToolTip("Remove the selected palette from the library.")
        self._delete_button.clicked.connect(self._on_delete_clicked)
        button_row_2.addWidget(self._delete_button)

        button_row_2.addStretch()
        layout.addLayout(button_row_2)

        self._refresh_button_state()

    def set_palettes(
        self,
        palettes: list[Palette],
        selected_index: int | None = None,
    ) -> None:
        """Rebuild the list to match `palettes`; preserve / set selection."""
        self._list.blockSignals(True)
        self._list.clear()

        for palette in palettes:
            item = QListWidgetItem(palette.name)
            item.setData(_PaletteRowDelegate.PALETTE_ROLE, palette)
            self._list.addItem(item)

        self._list.blockSignals(False)

        if (
            selected_index is not None
            and 0 <= selected_index < len(palettes)
        ):
            self._list.setCurrentRow(selected_index)

        self._refresh_button_state()

    def current_index(self) -> int:
        return self._list.currentRow()

    def _on_row_changed(self, row: int) -> None:
        self._refresh_button_state()
        if row >= 0:
            self.palette_selected.emit(row)

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        row = self._list.row(item)
        if row >= 0:
            self.edit_palette_requested.emit(row)

    def _on_context_menu_requested(self, local_pos: QPoint) -> None:
        item = self._list.itemAt(local_pos)
        if item is None:
            return

        row = self._list.row(item)
        global_pos = self._list.viewport().mapToGlobal(local_pos)

        menu = QMenu(self)
        menu.addAction("Rename...", lambda: self.rename_palette_requested.emit(row))
        menu.addAction("Edit...", lambda: self.edit_palette_requested.emit(row))
        menu.addSeparator()
        menu.addAction("Delete", lambda: self.delete_palette_requested.emit(row))
        menu.exec(global_pos)

    def _on_edit_clicked(self) -> None:
        row = self._list.currentRow()
        if row >= 0:
            self.edit_palette_requested.emit(row)

    def _on_delete_clicked(self) -> None:
        row = self._list.currentRow()
        if row >= 0:
            self.delete_palette_requested.emit(row)

    def _refresh_button_state(self) -> None:
        has_selection = self._list.currentRow() >= 0
        self._edit_button.setEnabled(has_selection)
        self._delete_button.setEnabled(has_selection)
