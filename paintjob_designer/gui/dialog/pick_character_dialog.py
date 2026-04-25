# coding: utf-8

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from paintjob_designer.models import CharacterProfile, KartType


class PickCharacterDialog(QDialog):
    """Modal character picker for the New Paintjob / New Skin flow."""

    def __init__(
        self,
        characters: list[CharacterProfile],
        title: str = "Select base character",
        kart_type_filter: KartType | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(360)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Pick the character whose VRAM the new asset is seeded from. "
            "This becomes the asset's base — Reset reverts edits to this "
            "character's CLUTs.",
        ))

        form = QFormLayout()
        self._combo = QComboBox()
        for character in characters:
            if (
                kart_type_filter is not None
                and character.kart_type != kart_type_filter
            ):
                continue

            self._combo.addItem(
                character.display_name or character.id, character.id,
            )

        form.addRow("Character:", self._combo)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._buttons = buttons
        # No characters made it through the filter — disable Ok so the
        # user can't accept an empty selection.
        if self._combo.count() == 0:
            buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)

    def selected_character_id(self) -> str | None:
        if self._combo.count() == 0:
            return None

        return self._combo.currentData()
