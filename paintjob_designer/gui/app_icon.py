# coding: utf-8

import sys
from pathlib import Path

from PySide6.QtGui import QIcon


class AppIcon:
    """Loads the application icon from the bundled `assets/icon.ico`.

    Handles the dev-checkout vs PyInstaller-frozen path split in one
    place: in a source tree the file lives at `<repo>/assets/icon.ico`,
    in a frozen build PyInstaller extracts bundled data under
    `sys._MEIPASS`. Both resolve to the same logical asset.

    Kept as a class (rather than a free function) so call sites can
    inject a test double or swap in a different asset without reaching
    for monkeypatch at import time.
    """

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
