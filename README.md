# DeviceDeck (PyQt5)

Desktop workspace for Android debugging: ADB file transfer, multi-session **SSH**, **serial**, USB **screen** forwarding, and on-device files — in one app.

| | |
|--|--|
| **PyPI package** | **`adbsshdeck`** (ADB + SSH + workspace “deck”, including screen control) |
| **Run after install** | **`adbsshdeck`** (also in `Scripts` on Windows) |
| **Python import** | `devicedeck` (unchanged) |
| **Website** | [nvnkennedy.github.io/Device_Deck](https://nvnkennedy.github.io/Device_Deck/) |
| **PyPI** | [pypi.org/project/adbsshdeck](https://pypi.org/project/adbsshdeck/) |

The name **`devicedeck`** on PyPI was already taken; **`adbsshdeck`** is this project’s distribution name.

## Prerequisites

- Python 3.9+
- **ADB** and a **USB display-forwarding** tool on `PATH`, or paths in **File → Preferences**
- **`ssh` on PATH** if you use SSH terminal sessions
- **Serial/COM** hardware if you use serial tabs (pyserial is a dependency)

## Install (recommended)

From [PyPI](https://pypi.org/project/adbsshdeck/):

```bash
python -m pip install --upgrade pip
python -m pip install adbsshdeck
```

Then:

```bash
adbsshdeck
```

Same as: `python -m devicedeck` (import package is still `devicedeck`).

This repository is **source-only** on GitHub — users install the **published package** with pip.

## Install from a git clone (development)

```bash
git clone https://github.com/nvnkennedy/Device_Deck.git
cd Device_Deck
pip install -e ".[dev]"
```

Or:

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

- `pyproject.toml` — metadata; console entry **`adbsshdeck`**
- `devicedeck/` — application code (import name)
- `site/` — GitHub Pages (home + install + PyPI links)
- `scripts/` — `build_windows_exe.ps1`, `export_app_icon.py`
- `tests/` — pytest
- `DeviceDeck.spec` — PyInstaller (optional)

## Build wheel / sdist

```bash
pip install build
python -m build
```

Artifacts: `dist/adbsshdeck-*.whl` and `dist/*.tar.gz`.

## Testing

```bash
python -m pytest tests/ -q
```

## Notes

- Settings: `~/.devicedeck.json`
- License: MIT — see [LICENSE](LICENSE)
