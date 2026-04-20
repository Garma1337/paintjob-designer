# -*- mode: python ; coding: utf-8 -*-

KEEP_QT_MODULES = {
    "Core",
    "Gui",
    "Widgets",
    "OpenGL",
    "OpenGLWidgets",
    "DBus",
}

PYSIDE6_PYTHON_EXCLUDES = [
    "PySide6.QtAsyncio",
    "PySide6.QtConcurrent",
    "PySide6.QtDesigner",
    "PySide6.QtHelp",
    "PySide6.QtNetwork",
    "PySide6.QtPrintSupport",
    "PySide6.QtQml",
    "PySide6.QtQmlCore",
    "PySide6.QtQmlWorkerScript",
    "PySide6.QtQuick",
    "PySide6.QtQuickControls2",
    "PySide6.QtQuickTest",
    "PySide6.QtQuickWidgets",
    "PySide6.QtSql",
    "PySide6.QtStateMachine",
    "PySide6.QtSvg",
    "PySide6.QtSvgWidgets",
    "PySide6.QtTest",
    "PySide6.QtUiTools",
    "PySide6.QtXml",
]

MISC_EXCLUDES = [
    "tkinter",
    "unittest",
    "test",
    "tests",
    "pytest",
    "setuptools",
    "pip",
    "doctest",
    "pdb",
]


def _path_modules(dest: str) -> set[str]:
    lowered = dest.replace("\\", "/").lower()
    found: set[str] = set()

    for part in lowered.split("/"):
        for prefix in ("qt6", "qt"):
            if part.startswith(prefix):
                stripped = part[len(prefix):]

                for suffix in (".dll", ".so", ".dylib", ".qm", ".pak"):
                    idx = stripped.find(suffix)
                    if idx != -1:
                        stripped = stripped[:idx]
                        break
                
                if stripped:
                    found.add(stripped)

    return found


def _is_excluded(dest: str) -> bool:
    modules = _path_modules(dest)
    if not modules:
        return False

    keep_lower = {m.lower() for m in KEEP_QT_MODULES}
    return all(m not in keep_lower for m in modules)


a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("config/profiles", "config/profiles"),
        ("paintjob_designer/gui/widget/shaders", "paintjob_designer/gui/widget/shaders"),
        ("app.ico", "."),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=PYSIDE6_PYTHON_EXCLUDES + MISC_EXCLUDES,
    noarchive=False,
    optimize=2,
)

_before_binaries = len(a.binaries)
_before_datas = len(a.datas)

a.binaries = [b for b in a.binaries if not _is_excluded(b[0])]
a.datas = [d for d in a.datas if not _is_excluded(d[0])]

print(
    f"[paintjob_designer.spec] Dropped "
    f"{_before_binaries - len(a.binaries)} binaries and "
    f"{_before_datas - len(a.datas)} data files "
    f"for excluded Qt modules."
)


pyz = PYZ(a.pure)


exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PaintjobDesigner",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon="app.ico",
    disable_windowed_traceback=False,
)


coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="PaintjobDesigner",
)
