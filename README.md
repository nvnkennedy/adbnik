# DeviceDeck (PyQt5)

Desktop workspace for Android debugging: ADB file transfer, multi-session terminal, and scrcpy screen control.

**PyPI package name:** `devicedeck`  
**Python import package:** `devicedeck`

## Prerequisites

- Python 3.9+
- **ADB** and **scrcpy** on `PATH`, or full paths in **File → Preferences**
- **OpenSSH client** (`ssh` on `PATH`) only if you use SSH terminal sessions
- **pyserial** only if you use serial/COM terminal sessions

## Install as a package

From a clone of this repository (recommended for development):

```bash
cd devicedeck
pip install .
```

Editable install with test dependencies:

```bash
pip install -e ".[dev]"
```

Install **from GitHub** without cloning first (replace `USER`/`REPO`):

```bash
pip install "git+https://github.com/USER/REPO.git#subdirectory=devicedeck"
```

If the repository root **is** this project (only `devicedeck/` at top level), omit `#subdirectory=...`.

After installation, launch from anywhere:

```bash
devicedeck
```

Equivalent ways to run:

```bash
python -m devicedeck
python main.py
```

(`main.py` is a thin launcher kept for convenience when working inside the repo.)

## Windows standalone executable (no Python on the target PC)

The app is packaged with [PyInstaller](https://pyinstaller.org/) into a folder that contains `DeviceDeck.exe` and supporting DLLs. **Distribute the whole `dist/DeviceDeck` folder** (zip it), not only the `.exe`. Users unpack and double‑click `DeviceDeck.exe`.

**Build on a Windows machine** (same architecture you want to support, e.g. 64‑bit):

```powershell
cd path\to\device_deck
pip install -e ".[build]"
pyinstaller DeviceDeck.spec
```

Or run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_windows_exe.ps1
```

Output: `dist\DeviceDeck\DeviceDeck.exe`.
The helper script auto-generates `assets\devicedeck.ico` and embeds it into the EXE.

ADB, scrcpy, and OpenSSH are **not** bundled; users still install those separately or set full paths under **File → Preferences**, same as the Python install.

### Production release model

This repository is source-first. Installer binaries are kept **outside** the source tree and published as GitHub Release assets.

For this local setup, release files are in:

- `E:\Naveen_Python_coding\projects\device_deck_release_downloads\DeviceDeck_Setup_0.1.0.exe`
- `E:\Naveen_Python_coding\projects\device_deck_release_downloads\DeviceDeck_Portable_0.1.0.zip`

Website/public landing pages are maintained under `site/` and deployed with GitHub Pages via `.github/workflows/pages.yml`.

## Project layout

- `pyproject.toml` — package metadata and the `devicedeck` console script
- `main.py` — optional local entrypoint
- `DeviceDeck.spec` — PyInstaller recipe for `dist/DeviceDeck/DeviceDeck.exe`
- `site/` — static website (Home, Download, Docs, Changelog)
- `scripts/` — helper scripts (`build_windows_exe.ps1`, `export_app_icon.py`)
- `devicedeck/` — application code
- `tests/` — pytest suite

## Build a wheel / sdist (for releases)

```bash
pip install build
python -m build
```

Artifacts appear under `dist/` (`devicedeck-0.1.0-py3-none-any.whl` and `.tar.gz`).

## Push this folder to GitHub

From `devicedeck` (this project root):

```bash
git init
git add .
git commit -m "Initial commit: DeviceDeck"
git branch -M main
git remote add origin https://github.com/YOUR_USER/YOUR_REPO.git
git push -u origin main
```

Replace `YOUR_USER/YOUR_REPO` with your account and repository name. If the repo already exists and uses another default branch, adjust `main` accordingly. If this project is only a folder inside an existing git repository, commit and push from that repository’s root instead of running `git init` here.

After pushing:

- Update `site/config.js` with your real `owner` and `repo`.
- Enable GitHub Pages in repository settings (Source: GitHub Actions).
- Tag releases as `vX.Y.Z` to trigger `.github/workflows/release.yml`.

After the first push, uncomment and fill in `[project.urls]` in `pyproject.toml` so PyPI and `pip` show the correct links.

## Publishing to PyPI (optional)

1. Add `[project.urls]` in `pyproject.toml` with your GitHub repo (see commented block in that file).
2. Bump `version` in `pyproject.toml` and `devicedeck/__init__.py` (`__version__`).
3. Use [Twine](https://twine.readthedocs.io/) to upload `dist/*` to [PyPI](https://pypi.org/) (create an API token first).

## Testing without SSH or serial hardware

1. **Automated checks**

   ```bash
   python -m pytest tests/ -q
   ```

2. **Terminal tab — local shells**  
   Open **CMD** or **PowerShell** sessions. No SSH, serial, or phone required.

3. **ADB + File Explorer + Screen Control**  
   Use an **Android emulator (AVD)** or a USB device with debugging until `adb devices` shows `device`, then use **ADB shell**, **File Explorer**, and **Screen Control**.

4. **SSH / serial** — optional when you have a server or hardware.

## Notes

- Settings file: `~/.devicedeck.json`. If you previously used `~/.adb_explorer_pro.json`, it is read once and replaced on the next save. Unknown JSON keys are ignored for forward compatibility.
- On **Windows**, the taskbar icon uses a fixed **App User Model ID** so it does not show the generic Python icon.
- Embedded scrcpy on Windows may affect touch; the default is a separate mirror window.

## License

MIT — see [LICENSE](LICENSE).
