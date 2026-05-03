# Adbnik

<p align="center">
  <img src="https://raw.githubusercontent.com/nvnkennedy/adbnik/main/branding/adbnik-256.png" width="128" height="128" alt="Adbnik" />
</p>

<p align="center">
  <strong>One desktop workspace for Android debugging, remote shells, and file operations.</strong>
</p>

**Adbnik** is a PyQt5 application that brings **ADB** workflows, **SSH** and **serial** terminals, **local ↔ remote file management** (Android device, SFTP, FTP), and **screen mirroring** launchers (e.g. scrcpy) into a single tabbed window. External tools—**adb**, **ssh**, **scrcpy**—are used from your system: install them separately and, if needed, set paths under **File → Preferences**.

**Platforms:** The same **PyPI** package installs on **Windows**, **Linux**, and **macOS** where PyQt5 runs. **Windows** is the primary, tested target: optional **Inno** installer from GitHub Releases, **`adbnik-setup`** for a desktop shortcut, optional **embedded scrcpy** in a tab, and local **CMD/PowerShell** terminal tabs. On **Linux** and **macOS**, use your system shells in the terminal area and run mirroring in a **separate** window—those Windows-only conveniences are not available there.

This repository holds **releases only**: license, changelog, documentation, the static site sources used for GitHub Pages, branding assets, and **Windows installers** under [`installers/`](installers/). Application source is maintained separately and is not published here. GitHub’s **language** bar on this branch reflects those static assets (for example HTML and CSS), not the **Python** implementation; the app itself is the **Python · PyQt5** package **`adbnik`** on [PyPI](https://pypi.org/project/adbnik/). Add **python**, **pyqt5**, **adb**, and related **Topics** under the repository **About** settings if you want them on the GitHub project page.

### About the name

**Adbnik** combines **ADB** (Android Debug Bridge) with **-nik**, a productive-form suffix familiar from words like ***technik*** (technician; someone who works with tools). It signals a utility focused on hands-on device work—not a generic “suite,” but a workstation built around real debugging and transfer tasks.

---

## Capabilities

| Area | Details |
|------|---------|
| **ADB** | Device selection, shell sessions, APK install flow, bookmarks, quick actions |
| **SSH** | Full-screen terminal via your system OpenSSH client |
| **Serial** | COM port and baud configuration in the UI |
| **Files** | Dual-pane explorer: local disk ↔ Android / SFTP / FTP |
| **Screen** | Start and manage mirroring using your chosen executable |

---

## User guide

Step-by-step documentation for the **Terminal**, **File Explorer**, and **Screen Control** tabs (menus, shortcuts, mirroring options), plus where to put **adb** / **scrcpy** on disk:

**https://nvnkennedy.github.io/adbnik/guide/index.html**

In the app: **Help → User guide** (F1) opens that URL; **Help** also lists the website, GitHub, and PyPI.

---

## Requirements

- **Python 3.9+** (64-bit recommended on Windows)
- **Android:** USB debugging enabled; **platform-tools** (`adb`) available to the same environment that runs Adbnik
- **SSH:** `ssh` on `PATH` (or wherever your shell resolves it)
- **Mirroring:** `scrcpy` or another tool—`PATH` or **Preferences**
- **Serial:** Port visible to the OS with the correct driver

---

## Installation

### pip (recommended)

Use the **same** Python interpreter for `pip` and for launching (avoids broken entry points on Windows):

```bat
py -m pip install --upgrade pip
py -m pip install adbnik
py -m adbnik
```

Pinned interpreter example:

```bat
"C:\Path\To\Python\python.exe" -m pip install adbnik
"C:\Path\To\Python\python.exe" -m adbnik
```

**Package index:** [pypi.org/project/adbnik](https://pypi.org/project/adbnik/) · **Files:** [pypi.org/project/adbnik/#files](https://pypi.org/project/adbnik/#files)

The **[PyPI project](https://pypi.org/project/adbnik/)** ships **wheels and an sdist** under the **Apache License 2.0** ([`LICENSE`](LICENSE), SPDX **`Apache-2.0`**). **Current stable** is **`6.0.0`** (see [`CHANGELOG.md`](CHANGELOG.md)); older lines are in [`CHANGELOG-legacy.md`](CHANGELOG-legacy.md)).

PyPI “Project links” (Windows installer, changelog, etc.) are defined in the published package metadata on PyPI.

### Windows installer (unsigned)

Release **`Adbnik-<version>-Setup-unsigned.exe`** and **`Adbnik-<version>-Windows-portable-unsigned.zip`** are in [`installers/`](installers/) for supported versions. The same files are on [GitHub Releases](https://github.com/nvnkennedy/adbnik/releases). See [`installers/README.md`](installers/README.md).

**SmartScreen / “Unknown publisher”:** the installer is not Authenticode-signed. Use **More info → Run anyway** when Windows prompts. That reflects **no code-signing certificate**, not an antivirus “malware” verdict.

If you prefer not to use an unsigned `.exe`, use **`pip`** above.

### Shortcut (Windows)

After `pip install`, run once:

```bat
adbnik-setup
```

Choose a folder for **`Adbnik.lnk`**. The shortcut uses **`python -m adbnik`** for the same interpreter you installed with.

```bat
adbnik-setup --folder "%USERPROFILE%\Desktop"
```

---

## First run

1. Start the app: `python -m adbnik` from the environment where the package is installed.
2. Under **File → Preferences**, set paths for **ADB** and **scrcpy** if they are not on `PATH`.
3. Use the main tabs for **Terminal**, **Files**, and **Screen** as needed.

Preferences are stored in **`.adbnik.json`** under your user profile. Legacy **`.devicedeck.json`** settings are migrated when you save preferences.

---

## Screenshots

<p align="center">
  <img src="https://raw.githubusercontent.com/nvnkennedy/adbnik/main/docs/screenshots/01-main-window.png" width="720" alt="Main window" /><br /><br />
  <img src="https://raw.githubusercontent.com/nvnkennedy/adbnik/main/docs/screenshots/02-terminal.png" width="720" alt="Terminal" /><br /><br />
  <img src="https://raw.githubusercontent.com/nvnkennedy/adbnik/main/docs/screenshots/03-file-explorer.png" width="720" alt="File explorer" /><br /><br />
  <img src="https://raw.githubusercontent.com/nvnkennedy/adbnik/main/docs/screenshots/04-screen-control.png" width="720" alt="Screen control" />
</p>

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'adbnik'`** — use the same `python.exe` for install and launch:

```bat
"C:\Path\To\Python\python.exe" -m pip install --force-reinstall adbnik
"C:\Path\To\Python\python.exe" -m adbnik
```

On Windows: `py -0p` lists interpreters.

---

## Resources

| | |
|--|--|
| **Site** | [nvnkennedy.github.io/adbnik](https://nvnkennedy.github.io/adbnik/) |
| **User guide** | [nvnkennedy.github.io/adbnik/guide/](https://nvnkennedy.github.io/adbnik/guide/index.html) |
| **Changelog** | [CHANGELOG.md](CHANGELOG.md) · [CHANGELOG-legacy.md](CHANGELOG-legacy.md) |
| **PyPI** | [pypi.org/project/adbnik](https://pypi.org/project/adbnik/) |
| **Releases** | [github.com/nvnkennedy/adbnik/releases](https://github.com/nvnkennedy/adbnik/releases) |

---

## Building from source

Source is not hosted in this repository. Install from **PyPI** or use the **Windows** builds above.

---

## License

**Apache License 2.0** — [`LICENSE`](LICENSE), [`NOTICE`](NOTICE). SPDX: `Apache-2.0`.
