# DeviceDeck (PyQt5)

Desktop workspace for Android debugging: ADB file transfer, multi-session terminal, and USB screen forwarding.

| | |
|--|--|
| **PyPI package name** | `devicedeck` |
| **Run after install** | `devicedeck` (also in `Scripts` on Windows) |
| **Website** | [nvnkennedy.github.io/Device_Deck](https://nvnkennedy.github.io/Device_Deck/) |
| **PyPI** | [pypi.org/project/devicedeck](https://pypi.org/project/devicedeck/) |

## Prerequisites

- Python 3.9+
- **ADB** and a **USB display-forwarding** tool on `PATH`, or paths in **File → Preferences**
- **`ssh` on PATH** if you use SSH terminal sessions
- **Serial/COM** hardware if you use serial tabs (pyserial is a dependency)

## Install (recommended)

From [PyPI](https://pypi.org/project/devicedeck/):

```bash
python -m pip install --upgrade pip
python -m pip install devicedeck
```

Then:

```bash
devicedeck
```

Same as: `python -m devicedeck`

This repository is **source-only** on GitHub — users install the **published package** with pip, not by downloading an `.exe` from the repo.

## Install from a git clone (development)

```bash
git clone https://github.com/nvnkennedy/Device_Deck.git
cd Device_Deck
pip install -e ".[dev]"
```

Editable install with tests:

```bash
pip install -e ".[dev]"
```

Or install **directly from GitHub**:

```bash
pip install "git+https://github.com/nvnkennedy/Device_Deck.git"
```

`main.py` is a thin launcher for local development only.

## Publishing to PyPI

See **[docs/PYPI_PUBLISH.md](docs/PYPI_PUBLISH.md)** (build wheel/sdist, API token, optional GitHub Actions).

## Website (GitHub Pages)

Static site under `site/` — **Install** instructions for end users. Deployed by `.github/workflows/pages.yml` when you push changes under `site/`.

## Windows standalone executable (optional, maintainers only)

For machines **without** Python, you can build a **PyInstaller** folder or installer **locally** — outputs are **not** committed to this repo.

```powershell
pip install -e ".[build]"
powershell -ExecutionPolicy Bypass -File scripts\build_windows_exe.ps1
```

See `DeviceDeck.spec`. ADB and display-forwarding tools are **not** bundled.

## Project layout

- `pyproject.toml` — metadata, `[project.scripts]` → `devicedeck` command
- `devicedeck/` — application code
- `site/` — GitHub Pages (home + install + PyPI links)
- `scripts/` — `build_windows_exe.ps1`, `export_app_icon.py`
- `tests/` — pytest
- `DeviceDeck.spec` — PyInstaller (optional)

## Build wheel / sdist

```bash
pip install build
python -m build
```

Artifacts: `dist/devicedeck-*.whl` and `dist/*.tar.gz`.

## Testing

```bash
python -m pytest tests/ -q
```

## Notes

- Settings: `~/.devicedeck.json`
- License: MIT — see [LICENSE](LICENSE)
