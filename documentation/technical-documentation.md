[<- Back](./README.md)

# Environment Setup

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1   # Windows PowerShell
source .venv/bin/activate    # Linux/macOS

pip install -r requirements.txt
```

# Release Artifacts

The GitHub Actions workflow in `.github/workflows/release.yml` is manually triggered and produces three `.7z` archives:

- `PaintjobDesigner-windows-portable.7z` — standalone PyInstaller one-dir bundle for Windows. No Python install required. Built on a Windows runner via `pyinstaller PaintjobDesigner.spec`.
- `PaintjobDesigner-windows-source.7z` — repo sources + `run.bat`. Requires a system Python. On first run, `run.bat` creates a local `.venv`, installs `requirements.txt` into it, and then launches `main.py` through the venv interpreter.
- `PaintjobDesigner-linux-source.7z` — repo sources + `run.sh`. POSIX equivalent of the Windows source package.

Only the portable Windows build uses PyInstaller; the two source packages are produced from a single Ubuntu job that copies the repo tree, strips the wrong-platform launcher, and invokes `7z`. This is what keeps build time + artifact size down compared to shipping a PyInstaller bundle for every platform.

## Building the portable installer locally

```bash
pyinstaller PaintjobDesigner.spec
```

The spec file lives at the repo root; it handles icon, data-file bundling, and the PySide6 submodule exclusions that keep the bundle small. Output lands in `dist/PaintjobDesigner/`.

# Running Tests

```bash
pytest
```

All headless — no GL context or ISO needed. Controller tests pull in a session-scoped `qapp` fixture from `tests/conftest.py` so the Qt-widget side compiles, but no event loop runs.

# Regenerating Schemas

When you change a model in `paintjob_designer/models/`, regenerate the committed JSON schemas so consumer tools see the new shape:

```bash
python tools/dump_schema.py
```

This writes `schema/paintjobs_library_schema.json` and `schema/skins_library_schema.json`. The matching tests in `tests/paintjob/test_schema.py` and `tests/skin/test_schema.py` will fail in CI if you forget.
