# coding: utf-8

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from paintjob_designer.models import (
    CharacterProfile,
    PaintjobLibrary,
    SkinLibrary,
)


class PreviewSidebar(QWidget):
    """Sidebar tab for viewing a paintjob + skin combined on a character."""

    NONE_LABEL = "(none)"

    composition_changed = Signal(str, int, int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._characters: list[CharacterProfile] = []
        self._paintjob_library: PaintjobLibrary = PaintjobLibrary()
        self._skin_library: SkinLibrary = SkinLibrary()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        intro = QLabel(
            "Preview a paintjob and a skin combined on a character. "
            "Editing is disabled here — switch to the Paintjobs or Skins "
            "tab to make changes.",
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #aaa;")
        layout.addWidget(intro)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)

        self._character_combo = QComboBox()
        self._character_combo.currentIndexChanged.connect(
            self._on_character_changed,
        )
        form.addRow("Character:", self._character_combo)

        self._paintjob_combo = QComboBox()
        self._paintjob_combo.currentIndexChanged.connect(self._emit_change)
        form.addRow("Paintjob:", self._paintjob_combo)

        self._skin_combo = QComboBox()
        self._skin_combo.currentIndexChanged.connect(self._emit_change)
        form.addRow("Skin:", self._skin_combo)

        layout.addLayout(form)
        layout.addStretch(1)

    def set_sources(
        self,
        characters: list[CharacterProfile],
        paintjob_library: PaintjobLibrary,
        skin_library: SkinLibrary,
    ) -> None:
        """Replace the available characters / paintjobs / skins."""
        previous_character_id = self.current_character_id()

        self._characters = list(characters)
        self._paintjob_library = paintjob_library
        self._skin_library = skin_library

        self._character_combo.blockSignals(True)
        self._character_combo.clear()

        for character in self._characters:
            self._character_combo.addItem(
                character.display_name or character.id, character.id,
            )

        self._character_combo.blockSignals(False)

        target_index = 0
        if previous_character_id is not None:
            for i in range(self._character_combo.count()):
                if self._character_combo.itemData(i) == previous_character_id:
                    target_index = i
                    break

        if self._character_combo.count() == 0:
            self._refresh_for_character()
            return

        self._character_combo.blockSignals(True)
        self._character_combo.setCurrentIndex(target_index)
        self._character_combo.blockSignals(False)
        self._on_character_changed(target_index)

    def current_character_id(self) -> str | None:
        if self._character_combo.count() == 0:
            return None

        return self._character_combo.currentData()

    def current_paintjob_index(self) -> int:
        return self._paintjob_combo.currentData() if self._paintjob_combo.count() else -1

    def current_skin_index(self) -> int:
        return self._skin_combo.currentData() if self._skin_combo.count() else -1

    def _on_character_changed(self, _index: int) -> None:
        self._refresh_for_character()
        self._emit_change()

    def _refresh_for_character(self) -> None:
        """Repopulate paintjob + skin combos for the active character."""
        character = self._current_character_profile()

        self._paintjob_combo.blockSignals(True)
        self._paintjob_combo.clear()
        self._paintjob_combo.addItem(self.NONE_LABEL, -1)

        if character is not None:
            for i, paintjob in enumerate(self._paintjob_library.paintjobs):
                if paintjob.kart_type != character.kart_type:
                    continue

                label = paintjob.name.strip() or f"Paintjob {i + 1}"
                self._paintjob_combo.addItem(label, i)

        self._paintjob_combo.setCurrentIndex(0)
        self._paintjob_combo.blockSignals(False)

        self._skin_combo.blockSignals(True)
        self._skin_combo.clear()
        self._skin_combo.addItem(self.NONE_LABEL, -1)

        if character is not None:
            for i, skin in enumerate(self._skin_library.skins):
                if skin.character_id != character.id:
                    continue

                label = skin.name.strip() or f"Skin {i + 1}"
                self._skin_combo.addItem(label, i)

        self._skin_combo.setCurrentIndex(0)
        self._skin_combo.blockSignals(False)

    def _current_character_profile(self) -> CharacterProfile | None:
        character_id = self.current_character_id()
        if character_id is None:
            return None

        return next(
            (c for c in self._characters if c.id == character_id), None,
        )

    def _emit_change(self) -> None:
        character_id = self.current_character_id() or ""
        paintjob_index = self.current_paintjob_index()
        skin_index = self.current_skin_index()
        self.composition_changed.emit(
            character_id, int(paintjob_index), int(skin_index),
        )
