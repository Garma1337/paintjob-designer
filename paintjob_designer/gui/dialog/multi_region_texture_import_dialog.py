# coding: utf-8

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from paintjob_designer.gui.util.dialogs import FilePicker


class MultiRegionTextureImportDialog(QDialog):
    """Per-region PNG picker for multi-region slot texture imports.

    One row per region. The user picks a PNG for each; OK is enabled
    once every row has a path. Returns an ordered list of paths matching
    the region order so the caller can feed them straight into
    `MultiRegionTextureImporter`.
    """

    def __init__(
        self,
        parent: QWidget | None,
        *,
        slot_name: str,
        region_specs: list[tuple[int, int]],
        files: FilePicker,
        default_dir: str | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Import textures for {slot_name}")
        self.setMinimumWidth(420)

        self._files = files
        self._default_dir = default_dir
        self._region_specs = list(region_specs)
        self._paths: list[Path | None] = [None] * len(region_specs)
        self._labels: list[QLabel] = []

        layout = QVBoxLayout(self)

        intro = QLabel(
            f"'{slot_name}' spans {len(region_specs)} VRAM regions. Pick one "
            "PNG per region — they'll share a single 16-color palette so "
            "colors don't drift at the seams.",
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #aaa;")
        layout.addWidget(intro)

        form = QFormLayout()
        for i, (w, h) in enumerate(region_specs):
            row_widget = QWidget()
            row_layout = QVBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(2)

            chosen_label = QLabel("(no file picked)")
            chosen_label.setStyleSheet("color: #888;")
            self._labels.append(chosen_label)

            pick_button = QPushButton("Pick PNG...")
            pick_button.clicked.connect(self._make_picker(i))

            row_layout.addWidget(chosen_label)
            row_layout.addWidget(pick_button)

            form.addRow(f"Region {i + 1} ({w}×{h}):", row_widget)

        layout.addLayout(form)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
        )
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)

        self._refresh_ok_enabled()

    def chosen_paths(self) -> list[Path]:
        """Return the user's per-region picks. Caller checks `exec()` first."""
        return [p for p in self._paths if p is not None]

    def _make_picker(self, region_index: int):
        def handler():
            path = self._files.pick_open_path(
                self,
                f"Pick PNG for region {region_index + 1}",
                self._default_dir,
                "PNG images (*.png);;All files (*)",
            )

            if path is None:
                return

            self._paths[region_index] = Path(path)
            self._labels[region_index].setText(Path(path).name)
            self._labels[region_index].setStyleSheet("")
            self._refresh_ok_enabled()

        return handler

    def _refresh_ok_enabled(self) -> None:
        all_picked = all(p is not None for p in self._paths)
        self._buttons.button(
            QDialogButtonBox.StandardButton.Ok,
        ).setEnabled(all_picked)
