# Release checklist

Primary distribution: **PyPI** (`pip install adbnik`). This repository stays **source-only** (no checked-in `.exe` / `.zip`).

Before tagging:

- `pyproject.toml` version
- `adbnik/__init__.py` (`__version__` and `APP_TITLE` if needed)
- `CHANGELOG.md`
- Site `install.html` / `index.html` if copy references a specific version (usually not required)
