# coding: utf-8

from typing import Callable

from PySide6.QtCore import QPoint, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QListWidget,
    QPushButton,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QVBoxLayout,
    QWidget,
)


class LibraryRowDelegate(QStyledItemDelegate):
    """Two-line row: primary label on top, muted secondary line below."""

    SECONDARY_ROLE = Qt.ItemDataRole.UserRole + 1

    _PADDING_X = 6
    _PADDING_Y = 3
    _LINE_GAP = 2
    _SECONDARY_ALPHA = 140

    def paint(self, painter, option, index) -> None:
        painter.save()

        widget = option.widget
        style = widget.style() if widget else QApplication.style()

        background_opt = QStyleOptionViewItem(option)
        background_opt.text = ""
        style.drawControl(
            QStyle.ControlElement.CE_ItemViewItem, background_opt, painter, widget,
        )

        primary = index.data(Qt.ItemDataRole.DisplayRole) or ""
        secondary = index.data(self.SECONDARY_ROLE) or ""

        primary_color, muted_color = self.text_colors(option, self._SECONDARY_ALPHA)
        primary_font = option.font
        secondary_font = self.secondary_font(option.font)
        fm_primary = QFontMetrics(primary_font)

        text_rect = option.rect.adjusted(
            self._PADDING_X, self._PADDING_Y, -self._PADDING_X, -self._PADDING_Y,
        )

        painter.setFont(primary_font)
        painter.setPen(primary_color)
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
            primary,
        )

        if secondary:
            secondary_rect = text_rect.adjusted(
                0, fm_primary.height() + self._LINE_GAP, 0, 0,
            )
            painter.setFont(secondary_font)
            painter.setPen(muted_color)
            painter.drawText(
                secondary_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                secondary,
            )

        painter.restore()

    def sizeHint(self, option, index) -> QSize:
        secondary = index.data(self.SECONDARY_ROLE) or ""
        primary_h = QFontMetrics(option.font).height()
        total = self._PADDING_Y * 2 + primary_h

        if secondary:
            total += self._LINE_GAP + QFontMetrics(self.secondary_font(option.font)).height()

        return QSize(option.rect.width(), total)

    @staticmethod
    def secondary_font(base: QFont) -> QFont:
        font = QFont(base)
        size = base.pointSizeF()

        if size > 0:
            font.setPointSizeF(max(size - 1, 7.0))

        return font

    @staticmethod
    def text_colors(option, muted_alpha: int) -> tuple[QColor, QColor]:
        if option.state & QStyle.StateFlag.State_Selected:
            foreground = option.palette.color(QPalette.ColorRole.HighlightedText)
            background = option.palette.color(QPalette.ColorRole.Highlight)
        else:
            foreground = option.palette.color(QPalette.ColorRole.Text)
            background = option.palette.color(QPalette.ColorRole.Base)

        backgroundis_dark = LibraryRowDelegate.is_dark(background)
        if LibraryRowDelegate.is_dark(foreground) == backgroundis_dark:
            primary = QColor("#eaeaea") if backgroundis_dark else QColor("#202020")
        else:
            primary = foreground

        muted = QColor(primary)
        muted.setAlpha(muted_alpha)
        return primary, muted

    @staticmethod
    def is_dark(color: QColor) -> bool:
        luminance = (color.red() * 299 + color.green() * 587 + color.blue() * 114) / 1000
        return luminance < 128


class LibrarySidebar(QWidget):
    """Shared list + button-row scaffolding for the paintjob / skin sidebars.

    Subclasses populate items via `set_library` (their own typed method)
    and add type-specific buttons via `_add_extra_buttons`. Selection
    emits via `item_selected(int)` (re-fired after a dedup against the
    last emitted index so repeat-clicks don't churn).
    """

    item_selected = Signal(int)
    new_requested = Signal()
    delete_requested = Signal(int)
    export_requested = Signal()
    transform_requested = Signal(int)
    context_requested = Signal(int, QPoint)

    def __init__(
        self,
        new_tooltip: str,
        delete_tooltip: str,
        transform_tooltip: str,
        export_tooltip: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._last_emitted_index: int = -1
        # Default resolver is identity; main_window installs a profile-
        # backed one once a profile loads so labels show display names
        # instead of raw character ids.
        self._character_resolver: Callable[[str], str] = lambda cid: cid or ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._list = QListWidget()
        self._list.setItemDelegate(LibraryRowDelegate(self._list))
        self._list.currentRowChanged.connect(self._on_row_changed)
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(
            self._on_context_menu_requested,
        )
        layout.addWidget(self._list, 1)

        self._button_row = QHBoxLayout()
        self._button_row.setContentsMargins(0, 0, 0, 0)

        self._new_button = self._add_button(
            "New", new_tooltip, self.new_requested,
        )
        self._delete_button = self._add_button(
            "Delete", delete_tooltip, self._on_delete_clicked,
        )
        self._transform_button = self._add_button(
            "Transform...", transform_tooltip, self._on_transform_clicked,
        )
        self._add_extra_buttons()
        self._export_button = self._add_button(
            "Export...", export_tooltip, self.export_requested,
        )

        self._button_row.addStretch()
        layout.addLayout(self._button_row)

        self._refresh_button_state()

    def set_character_resolver(self, resolver: Callable[[str], str]) -> None:
        """Install a `character_id -> display_name` resolver so subclasses
        can render character names instead of raw ids in row labels."""
        self._character_resolver = resolver

    def set_selected_index(self, index: int | None) -> None:
        """Programmatic selection — does not fire `item_selected`."""
        self._list.blockSignals(True)
        if index is None:
            self._list.setCurrentRow(-1)
            self._last_emitted_index = -1
        else:
            self._list.setCurrentRow(index)
            self._last_emitted_index = index

        self._list.blockSignals(False)
        self._refresh_button_state()

    def _apply_selection_after_rebuild(
        self, index: int | None, total_count: int,
    ) -> None:
        """Restore the list selection after `set_library` rebuilds the rows.

        When the new index matches the previously-selected row (e.g. a
        rename or author edit didn't actually move the selection), the
        signal is suppressed so consumers don't treat it as a fresh
        selection and run expensive side effects.
        """
        valid = index is not None and 0 <= index < total_count
        if not valid:
            self._last_emitted_index = -1
            self._list.setCurrentRow(-1)
            return

        if index == self._last_emitted_index:
            self._list.blockSignals(True)
            self._list.setCurrentRow(index)
            self._list.blockSignals(False)
        else:
            self._last_emitted_index = -1
            self._list.setCurrentRow(index)

    def _add_extra_buttons(self) -> None:
        """Override to insert type-specific buttons between Delete and Export."""

    def _selection_dependent_buttons(self) -> list[QPushButton]:
        """Override to return any extra buttons that should disable when
        no row is selected. The Delete button is always managed by the
        base, so subclasses only list the additional ones."""
        return []

    def _add_button(
        self, label: str, tooltip: str, slot: Callable | Signal,
    ) -> QPushButton:
        btn = QPushButton(label)
        btn.setToolTip(tooltip)
        btn.clicked.connect(slot)
        self._button_row.addWidget(btn)
        return btn

    def _on_row_changed(self, row: int) -> None:
        if row == self._last_emitted_index:
            return

        self._last_emitted_index = row
        self._refresh_button_state()

        if row >= 0:
            self.item_selected.emit(row)

    def _on_delete_clicked(self) -> None:
        row = self._list.currentRow()
        if row >= 0:
            self.delete_requested.emit(row)

    def _on_transform_clicked(self) -> None:
        row = self._list.currentRow()
        if row >= 0:
            self.transform_requested.emit(row)

    def _on_context_menu_requested(self, local_pos: QPoint) -> None:
        item = self._list.itemAt(local_pos)
        if item is None:
            return
        self.context_requested.emit(
            self._list.row(item),
            self._list.viewport().mapToGlobal(local_pos),
        )

    def _refresh_button_state(self) -> None:
        has_selection = self._list.currentRow() >= 0
        self._transform_button.setEnabled(has_selection)
        self._delete_button.setEnabled(has_selection)

        for btn in self._selection_dependent_buttons():
            btn.setEnabled(has_selection)
