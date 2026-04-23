# coding: utf-8

from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QInputDialog, QMessageBox, QWidget


class MessageDialog:
    """Modal info / warn / error / confirm popups (QMessageBox wrapper)."""

    def confirm_destructive(
        self,
        parent: QWidget | None,
        title: str,
        message: str,
    ) -> bool:
        answer = QMessageBox.question(
            parent, title, message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        return answer == QMessageBox.StandardButton.Yes

    def info(self, parent: QWidget | None, title: str, message: str) -> None:
        QMessageBox.information(parent, title, message)

    def warn(self, parent: QWidget | None, title: str, message: str) -> None:
        QMessageBox.warning(parent, title, message)

    def error(self, parent: QWidget | None, title: str, message: str) -> None:
        QMessageBox.critical(parent, title, message)


class FilePicker:
    """File / directory picker dialogs (QFileDialog wrapper)."""

    def pick_directory(
        self,
        parent: QWidget | None,
        title: str,
        default_path: str | Path | None = None,
    ) -> Path | None:
        chosen = QFileDialog.getExistingDirectory(
            parent, title, str(default_path or Path.home()),
        )
        return Path(chosen) if chosen else None

    def pick_save_path(
        self,
        parent: QWidget | None,
        title: str,
        default_path: str | Path,
        filter_str: str,
    ) -> Path | None:
        path_str, _ = QFileDialog.getSaveFileName(
            parent, title, str(default_path), filter_str,
        )

        return Path(path_str) if path_str else None

    def pick_open_path(
        self,
        parent: QWidget | None,
        title: str,
        default_dir: str | Path | None,
        filter_str: str,
    ) -> Path | None:
        path_str, _ = QFileDialog.getOpenFileName(
            parent, title, str(default_dir or Path.home()), filter_str,
        )

        return Path(path_str) if path_str else None

    def pick_open_paths(
        self,
        parent: QWidget | None,
        title: str,
        default_dir: str | Path | None,
        filter_str: str,
    ) -> list[Path]:
        paths, _ = QFileDialog.getOpenFileNames(
            parent, title, str(default_dir or Path.home()), filter_str,
        )
        return [Path(p) for p in paths]


class InputPrompt:
    """Single-value text / item prompts (QInputDialog wrapper).

    Returns `None` when the user cancels — callers gate on `is None` so
    the cancel path reads as one early-return instead of `if not ok`.
    """

    def get_text(
        self,
        parent: QWidget | None,
        title: str,
        label: str,
        default: str = "",
    ) -> str | None:
        text, ok = QInputDialog.getText(parent, title, label, text=default)
        return text if ok else None

    def get_item(
        self,
        parent: QWidget | None,
        title: str,
        label: str,
        items: list[str],
        current_index: int = 0,
    ) -> str | None:
        chosen, ok = QInputDialog.getItem(
            parent, title, label, items, current_index, editable=False,
        )

        return chosen if ok else None
