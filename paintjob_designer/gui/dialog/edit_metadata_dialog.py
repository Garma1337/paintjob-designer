# coding: utf-8

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from paintjob_designer.models import MetadataEdit


_UNBOUND_LABEL = "(none — unbound)"


class EditMetadataDialog(QDialog):
    """Single dialog for editing an asset's display name + author, plus an
    optional base-character dropdown for paintjobs."""

    def __init__(
        self,
        parent: QWidget | None,
        *,
        title: str,
        name: str,
        author: str,
        base_character_options: list[str] | None = None,
        base_character_current: str | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(360)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._name_edit = QLineEdit(name)
        form.addRow("Name:", self._name_edit)

        self._author_edit = QLineEdit(author)
        form.addRow("Author:", self._author_edit)

        self._base_combo: QComboBox | None = None
        if base_character_options is not None:
            self._base_combo = QComboBox()
            self._base_combo.addItem(_UNBOUND_LABEL, None)
            for character_id in base_character_options:
                self._base_combo.addItem(character_id, character_id)

            target = base_character_current
            for i in range(self._base_combo.count()):
                if self._base_combo.itemData(i) == target:
                    self._base_combo.setCurrentIndex(i)
                    break

            form.addRow("Base character:", self._base_combo)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def exec_get(self) -> MetadataEdit | None:
        """Block on the dialog. Returns the edited values, or `None` when cancelled."""
        if self.exec() != QDialog.DialogCode.Accepted:
            return None

        return MetadataEdit(
            name=self._name_edit.text().strip(),
            author=self._author_edit.text().strip(),
            base_character_id=(
                self._base_combo.currentData()
                if self._base_combo is not None else None
            ),
        )
