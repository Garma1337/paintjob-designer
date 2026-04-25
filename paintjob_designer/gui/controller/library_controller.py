# coding: utf-8

from typing import Generic, TypeVar

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QWidget

from paintjob_designer.gui.util.dialogs import MessageDialog

TItem = TypeVar("TItem")
TLibrary = TypeVar("TLibrary")


class LibraryController(QObject, Generic[TItem, TLibrary]):
    """Base for the paintjob / skin / palette controllers."""

    selection_changed = Signal(object)
    library_changed = Signal()
    mutated = Signal()
    library_reset = Signal()

    def __init__(
        self,
        message: MessageDialog,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._message = message
        self._parent_widget = parent
        self._library: TLibrary = self._make_empty_library()
        self._current: TItem | None = None

    def _make_empty_library(self) -> TLibrary:
        raise NotImplementedError

    def _items(self) -> list[TItem]:
        raise NotImplementedError

    def _item_label(self, item: TItem, index: int) -> str:
        raise NotImplementedError

    def _item_kind(self) -> str:
        raise NotImplementedError

    def _refresh_sidebar(self, selected_index: int | None) -> None:
        raise NotImplementedError

    def _remove_at(self, index: int) -> TItem:
        raise NotImplementedError

    @property
    def library(self) -> TLibrary:
        return self._library

    @property
    def current(self) -> TItem | None:
        return self._current

    def replace_library(self, library: TLibrary) -> None:
        self._library = library
        self._current = None
        self._refresh_sidebar(None)
        self.library_reset.emit()
        self.library_changed.emit()
        self.selection_changed.emit(None)

    def show_initial_selection(self) -> None:
        items = self._items()
        initial = 0 if items else None
        self._refresh_sidebar(initial)

    def delete(self, index: int) -> None:
        items = self._items()
        if not (0 <= index < len(items)):
            return

        item = items[index]
        if not self._message.confirm_destructive(
            self._parent_widget, f"Delete {self._item_kind()}",
            f"Delete '{self._item_label(item, index)}'? This can't be undone.",
        ):
            return

        removed = self._remove_at(index)
        if self._current is removed:
            self._current = None

        items = self._items()
        next_selection = None
        if items:
            next_selection = min(index, len(items) - 1)
            self._current = items[next_selection]

        self._refresh_sidebar(next_selection)
        self.library_changed.emit()
        self.mutated.emit()
        self.selection_changed.emit(self._current)

    def select_index(self, index: int) -> None:
        items = self._items()
        if not (0 <= index < len(items)):
            return

        self._set_sidebar_selection(index)
        self._current = items[index]

    def _on_sidebar_selected(self, index: int) -> None:
        items = self._items()
        if not (0 <= index < len(items)):
            self._current = None
        else:
            self._current = items[index]

        self.selection_changed.emit(self._current)

    def _after_mutation(self) -> None:
        self.library_changed.emit()
        self.mutated.emit()

    def _set_sidebar_selection(self, index: int) -> None:
        """Subclasses with a per-sidebar set_selected_index override this
        when their sidebar exposes one."""
        self._refresh_sidebar(index)
