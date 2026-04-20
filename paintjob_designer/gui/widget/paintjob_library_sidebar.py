# coding: utf-8

from PySide6.QtCore import QPoint, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPalette
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
    QWidget,
)

from paintjob_designer.models import PaintjobLibrary


class _PaintjobRowDelegate(QStyledItemDelegate):
    """Two-line row: primary label on top, muted author line below.

    Using a delegate (not `setItemWidget`) so drag-reorders preserve the
    rendering — item data moves with the item, attached widgets don't.
    """

    AUTHOR_ROLE = Qt.ItemDataRole.UserRole + 1

    _PADDING_X = 6
    _PADDING_Y = 3
    _LINE_GAP = 2
    _AUTHOR_ALPHA = 140

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
        author = index.data(self.AUTHOR_ROLE) or ""

        primary_color, muted_color = self.text_colors(option, self._AUTHOR_ALPHA)

        primary_font = option.font
        author_font = self.author_font(option.font)

        fm_primary = QFontMetrics(primary_font)

        rect = option.rect
        text_rect = rect.adjusted(
            self._PADDING_X, self._PADDING_Y, -self._PADDING_X, -self._PADDING_Y,
        )

        painter.setFont(primary_font)
        painter.setPen(primary_color)
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
            primary,
        )

        if author:
            author_rect = text_rect.adjusted(
                0, fm_primary.height() + self._LINE_GAP, 0, 0,
            )
            painter.setFont(author_font)
            painter.setPen(muted_color)
            painter.drawText(
                author_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                author,
            )

        painter.restore()

    def sizeHint(self, option, index) -> QSize:
        author = index.data(self.AUTHOR_ROLE) or ""

        primary_h = QFontMetrics(option.font).height()
        total = self._PADDING_Y * 2 + primary_h

        if author:
            total += self._LINE_GAP + QFontMetrics(self.author_font(option.font)).height()

        return QSize(option.rect.width(), total)

    @staticmethod
    def author_font(base: QFont) -> QFont:
        font = QFont(base)
        size = base.pointSizeF()

        if size > 0:
            font.setPointSizeF(max(size - 1, 7.0))

        return font

    @staticmethod
    def text_colors(option, muted_alpha: int) -> tuple[QColor, QColor]:
        """Pick primary + muted text colors that actually contrast with the row background.

        Windows' native style keeps `QPalette.Text` at the light-theme
        black even when the app paints on a dark background, so reading
        the palette directly leaves the label invisible in dark mode.
        We fall back to an explicit high-contrast color whenever the
        palette's Text and Base roles sit on the same side of the
        luminance midpoint (a reliable signal that the palette hasn't
        caught up with the system theme).
        """
        if option.state & QStyle.StateFlag.State_Selected:
            foreground = option.palette.color(QPalette.ColorRole.HighlightedText)
            background = option.palette.color(QPalette.ColorRole.Highlight)
        else:
            foreground = option.palette.color(QPalette.ColorRole.Text)
            background = option.palette.color(QPalette.ColorRole.Base)

        background_is_dark = _PaintjobRowDelegate.is_dark(background)
        if _PaintjobRowDelegate.is_dark(foreground) == background_is_dark:
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


class PaintjobLibrarySidebar(QWidget):
    """Scrollable list of paintjobs in the session library.

    Each row shows a paintjob's display name plus, when present, a muted
    author line below. Rows can be reordered via drag-and-drop (the
    in-game paintjob index = list position, so order matters for
    PAINTALL.BIN exports).

    Emits:
        - `paintjob_selected(index)` on row change.
        - `paintjob_context_requested(index, global_pos)` on right-click.
        - `new_paintjob_requested()` / `delete_paintjob_requested(index)`
          when the toolbar buttons are clicked.
        - `paintjobs_reordered(from_index, to_index)` after a drag.

    The sidebar is purely a view; the main window owns the library and
    relays model mutations back via `set_library` on each change.
    """

    paintjob_selected = Signal(int)
    paintjob_context_requested = Signal(int, QPoint)
    new_paintjob_requested = Signal()
    delete_paintjob_requested = Signal(int)
    paintjobs_reordered = Signal(int, int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self._last_emitted_index: int = -1
        self._suppress_reorder_signal = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._list = QListWidget()
        self._list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.setItemDelegate(_PaintjobRowDelegate(self._list))
        self._list.currentRowChanged.connect(self._on_row_changed)
        self._list.customContextMenuRequested.connect(self._on_context_menu_requested)
        # `model().rowsMoved` fires after Qt finishes a drag-reorder; we use
        # it to translate the view-level move into a library-level move on
        # the main window (which owns the canonical ordering).
        self._list.model().rowsMoved.connect(self._on_rows_moved)
        layout.addWidget(self._list, 1)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        self._new_button = QPushButton("New")
        self._new_button.setToolTip("Create a blank paintjob in the library.")
        self._new_button.clicked.connect(self.new_paintjob_requested)
        button_row.addWidget(self._new_button)

        self._delete_button = QPushButton("Delete")
        self._delete_button.setToolTip(
            "Remove the selected paintjob from the library.",
        )
        self._delete_button.clicked.connect(self._on_delete_clicked)
        button_row.addWidget(self._delete_button)

        button_row.addStretch()
        layout.addLayout(button_row)

        self._refresh_button_state()

    def set_library(
        self,
        library: PaintjobLibrary,
        selected_index: int | None = None,
    ) -> None:
        """Rebuild the list to match `library`.

        `selected_index` controls which row ends up highlighted after the
        refresh — pass `None` to keep no selection, which happens when the
        library is empty or the main window hasn't picked a paintjob yet.
        """
        # Suppress both the selection-changed and rows-moved signals while
        # we rebuild — otherwise clearing the list emits a spurious
        # `currentRowChanged(-1)` and repopulation would look like a drag.
        self._list.blockSignals(True)
        self._suppress_reorder_signal = True
        self._list.clear()

        for i, paintjob in enumerate(library.paintjobs):
            item = QListWidgetItem(self._primary_text_for(paintjob, i))
            author = paintjob.author.strip()
            
            if author:
                item.setData(_PaintjobRowDelegate.AUTHOR_ROLE, author)

            self._list.addItem(item)

        self._list.blockSignals(False)
        self._suppress_reorder_signal = False

        self._last_emitted_index = -1
        if selected_index is not None and 0 <= selected_index < library.count():
            self._list.setCurrentRow(selected_index)

        self._refresh_button_state()

    def set_selected_index(self, index: int | None) -> None:
        """Programmatically move the selection without firing `paintjob_selected`."""
        self._list.blockSignals(True)

        if index is None:
            self._list.setCurrentRow(-1)
            self._last_emitted_index = -1
        else:
            self._list.setCurrentRow(index)
            self._last_emitted_index = index

        self._list.blockSignals(False)
        self._refresh_button_state()

    def _primary_text_for(self, paintjob, index: int) -> str:
        """Row label: name + optional character hint + textured marker.

        Three pieces of information compete for the one-line label:
          - **Name** — author-given identifier, always shown when present.
          - **Character hint** — `base_character_id` (soft hint for the
            preview fallback; the paintjob applies to any character).
          - **Textured marker** — `" (textured)"` suffix when the paintjob
            carries imported pixels, so artists can tell at a glance which
            paintjobs ship custom textures in addition to CLUT swaps.
        """
        name = paintjob.name.strip()
        character = paintjob.base_character_id
        marker = " (textured)" if paintjob.has_any_pixels() else ""

        if name and character:
            return f"{name}  —  {character}{marker}"

        if name:
            return f"{name}{marker}"

        if character:
            return f"({character}){marker}"

        return f"Paintjob {index + 1}{marker}"

    def _on_row_changed(self, row: int) -> None:
        if row == self._last_emitted_index:
            return

        self._last_emitted_index = row
        self._refresh_button_state()

        if row >= 0:
            self.paintjob_selected.emit(row)

    def _on_context_menu_requested(self, local_pos: QPoint) -> None:
        item = self._list.itemAt(local_pos)
        if item is None:
            return

        self.paintjob_context_requested.emit(
            self._list.row(item),
            self._list.viewport().mapToGlobal(local_pos),
        )

    def _on_delete_clicked(self) -> None:
        row = self._list.currentRow()
        if row < 0:
            return

        self.delete_paintjob_requested.emit(row)

    def _on_rows_moved(self, _parent, start: int, end: int, _dst_parent, dest: int) -> None:
        """Translate Qt's view-model row move into a library reorder.

        Qt's `rowsMoved` reports `dest` on the pre-move list state and uses
        the convention that moving a single row from index `start` to a
        landing index `dest` where `dest > start` means "after removal
        from `start`, insert at `dest - 1`". We convert to the
        `PaintjobLibrary.move` semantics (destination interpreted on the
        post-removal list) here so the main window receives a clean
        `(from_index, to_index)` pair.
        """
        if self._suppress_reorder_signal or start != end:
            return

        from_index = start
        to_index = dest if dest < start else dest - 1
        self.paintjobs_reordered.emit(from_index, to_index)

    def _refresh_button_state(self) -> None:
        has_selection = self._list.currentRow() >= 0
        self._delete_button.setEnabled(has_selection)
