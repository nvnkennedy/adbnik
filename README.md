# Adbnik

<p align="center">
  <img src="https://raw.githubusercontent.com/nvnkennedy/adbnik/naveen/branding/adbnik-256.png" width="128" height="128" alt="Adbnik" />
</p>

<p align="center">
  <strong>One desktop workspace for Android debugging, remote shells, and file operations.</strong>
</p>

**Adbnik** is a PyQt5 application that brings **ADB** workflows, **SSH** and **serial** terminals, **local ↔ remote file management** (Android device, SFTP, FTP), and **screen mirroring** launchers (e.g. scrcpy) into a single tabbed window. External tools—**adb**, **ssh**, **scrcpy**—are used from your system: install them separately and, if needed, set paths under **File → Preferences**.

**Platforms:** The same **PyPI** package installs on **Windows**, **Linux**, and **macOS** where PyQt5 runs. **Windows** is the primary, tested target: optional **Inno** installer from GitHub Releases, **`adbnik-setup`** for a desktop shortcut, optional **embedded scrcpy** in a tab, and local **CMD/PowerShell** terminal tabs. On **Linux** and **macOS**, use your system shells in the terminal area and run mirroring in a **separate** window—those Windows-only conveniences are not available there.

Development and releases use this **public** repository **[github.com/nvnkennedy/adbnik](https://github.com/nvnkennedy/adbnik)**. Work happens on **`naveen`** (full application tree). Branch **`main`** holds a trimmed snapshot for **GitHub Pages**, **installers**, and top-level **changelog** files (see [`BRANCHING.md`](https://github.com/nvnkennedy/adbnik/blob/naveen/BRANCHING.md)). **PyPI** uploads run from **`naveen`** via the **Publish to PyPI** workflow (manual dispatch or when you publish a **GitHub Release**).

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

**https://nvnkennedy.github.io/adbnik/guide/index.html** (styled pages—Terminal, Explorer, Screen—same site as the project home).

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

The **[PyPI project](https://pypi.org/project/adbnik/)** ships **wheels and an sdist** for `pip install` under the **Apache License 2.0** ([`LICENSE`](LICENSE), SPDX **`Apache-2.0`**). **Current stable** is **`6.1.3`** (see [`CHANGELOG.md`](CHANGELOG.md)); earlier releases are documented there and in [`CHANGELOG-legacy.md`](CHANGELOG-legacy.md)).

[`pyproject.toml`](https://github.com/nvnkennedy/adbnik/blob/naveen/pyproject.toml) on **`naveen`** defines package metadata and PyPI project links. Windows installers are built from **`naveen`** (CI on version tags or local `packaging/windows/build.ps1`), published to [GitHub Releases](https://github.com/nvnkennedy/adbnik/releases), and the same **`Adbnik-*`** files are copied into **`installers/`** on branch **`main`** when you ship that snapshot.

### Windows installer (optional, unsigned)

Unsigned **PyInstaller** + **Inno Setup** builds are attached to [GitHub Releases](https://github.com/nvnkennedy/adbnik/releases). The same files are stored under **`installers/`** on [github.com/nvnkennedy/adbnik](https://github.com/nvnkennedy/adbnik/tree/main/installers). See [`installers/README.md`](installers/README.md).

**Why Windows warns (“SmartScreen”, “Unknown publisher”, “Windows protected your PC”):** Microsoft flags **unknown / unsigned** executables by policy. That does **not** mean the installer was flagged as malware—it means there is **no publisher certificate** on the file.

**Run anyway:** On the SmartScreen dialog, choose **More info** (or **More details**), then **Run anyway**. If the browser blocked the download: open **Downloads**, right‑click the file → **Properties** → check **Unblock** if shown → **OK**, then run again.

If you prefer not to use an unsigned `.exe`, install with **`pip`** above (packages on PyPI are standard Python artifacts).

### Shortcut (Windows)

`pip` cannot place shortcuts or ask for a folder. After installing, run **once** on Windows:

```bat
adbnik-setup
```

A folder dialog opens (starting on your Desktop); choose where to put **`Adbnik.lnk`**. No extra console window is shown—only the dialogs. The shortcut uses **this Python** (`python -m adbnik`) and the same **app icon** as the window. Icon files are cached under `%LOCALAPPDATA%\Adbnik\`.

Non-interactive example (e.g. script or batch file, **with** console output):

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
  <img src="https://raw.githubusercontent.com/nvnkennedy/adbnik/naveen/docs/screenshots/01-main-window.png" width="720" alt="Main window" /><br /><br />
  <img src="https://raw.githubusercontent.com/nvnkennedy/adbnik/naveen/docs/screenshots/02-terminal.png" width="720" alt="Terminal" /><br /><br />
  <img src="https://raw.githubusercontent.com/nvnkennedy/adbnik/naveen/docs/screenshots/03-file-explorer.png" width="720" alt="File explorer" /><br /><br />
  <img src="https://raw.githubusercontent.com/nvnkennedy/adbnik/naveen/docs/screenshots/04-screen-control.png" width="720" alt="Screen control" />
</p>

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'adbnik'`** — Install and run with the same `python.exe`:

```bat
"C:\Path\To\Python\python.exe" -m pip install --force-reinstall adbnik
"C:\Path\To\Python\python.exe" -m adbnik
```

On Windows, list interpreters with `py -0p`.

---

## Resources

| | |
|--|--|
| **Product site** | [nvnkennedy.github.io/adbnik](https://nvnkennedy.github.io/adbnik/) |
| **User guide** | [nvnkennedy.github.io/adbnik/guide/](https://nvnkennedy.github.io/adbnik/guide/index.html) |
| **Changelog** | [CHANGELOG.md](CHANGELOG.md) · [CHANGELOG-legacy.md](CHANGELOG-legacy.md) |
| **Public repository** | [github.com/nvnkennedy/adbnik](https://github.com/nvnkennedy/adbnik) |
| **PyPI** | [pypi.org/project/adbnik](https://pypi.org/project/adbnik/) |
| **Releases** | [github.com/nvnkennedy/adbnik/releases](https://github.com/nvnkennedy/adbnik/releases) |

---

## Building from source

Clone this repository:

```bat
git clone https://github.com/nvnkennedy/adbnik.git
cd adbnik
git checkout naveen
py -m venv .venv
.venv\Scripts\activate
py -m pip install -e ".[dev]"
py -m pytest tests -q
py -m adbnik
```

Use HTTPS with a [personal access token](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens) if you do not use SSH keys.

---

## License

**Apache License 2.0** — see [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE). SPDX: `Apache-2.0`.
