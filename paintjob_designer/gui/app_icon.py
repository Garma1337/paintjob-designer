# coding: utf-8

import sys
from pathlib import Path

from PySide6.QtGui import QIcon


class AppIcon:
    """Loads the application icon from the bundled `assets/icon.ico`."""

    _FILENAME = "app.ico"

    def load(self) -> QIcon:
        return QIcon(str(self._resolve_path()))

    def _resolve_path(self) -> Path:
        base = getattr(sys, "_MEIPASS", None)
        if base is not None:
            return Path(base) / self._FILENAME

        # Source layout: this file is at
        # `<repo>/paintjob_designer/gui/app_icon.py`; the asset lives at
        # `<repo>/app.ico`.
        return (
            Path(__file__).resolve().parent.parent.parent / self._FILENAME
        )
