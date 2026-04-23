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


class ProfilePickerDialog(QDialog):
    """Lets the user pick which target profile to author against."""

    def __init__(
        self,
        available: list[str],
        current: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Switch profile")
        self.setMinimumWidth(360)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "The profile decides which characters are listed and which slot "
            "CLUTs the exports target. Switching resets the current session "
            "— any unsaved color edits will be lost.",
        ))

        form = QFormLayout()
        self._combo = QComboBox()
        for profile_id in available:
            self._combo.addItem(profile_id)

        if current in available:
            self._combo.setCurrentText(current)

        form.addRow("Profile:", self._combo)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
        )

        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_profile_id(self) -> str:
        return self._combo.currentText()
