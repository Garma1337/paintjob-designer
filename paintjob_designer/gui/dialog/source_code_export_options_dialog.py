# coding: utf-8

from dataclasses import dataclass

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
)


@dataclass
class SourceCodeExportOptions:
    identifier: str
    paint_index: int


class SourceCodeExportOptionsDialog(QDialog):
    """Prompts for the per-slot variable-name suffix and `PAINT<N>` index used
    by a source-code export.

    The defaults are pre-filled by the caller — for a character export that's
    the character id and its 1-based position in the profile; for a standalone
    export the caller can pass whatever makes sense (paintjob name + 1).
    """

    def __init__(
        self,
        default_identifier: str,
        default_paint_index: int,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Source Code Export")
        self.resize(360, 140)

        layout = QVBoxLayout(self)

        form = QFormLayout()
        self._identifier_edit = QLineEdit(default_identifier)
        self._identifier_edit.setPlaceholderText("e.g. crash, lime_racer")
        form.addRow("Identifier:", self._identifier_edit)

        self._paint_index_spin = QSpinBox()
        self._paint_index_spin.setRange(1, 99)
        self._paint_index_spin.setValue(default_paint_index)
        form.addRow("PAINT&lt;N&gt; index:", self._paint_index_spin)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
        )

        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def options(self) -> SourceCodeExportOptions:
        return SourceCodeExportOptions(
            identifier=self._identifier_edit.text().strip(),
            paint_index=self._paint_index_spin.value(),
        )
