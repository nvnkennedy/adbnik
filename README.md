# Adbnik

<p align="center">
  <img src="https://raw.githubusercontent.com/nvnkennedy/adbnik/main/branding/adbnik-256.png" width="128" height="128" alt="Adbnik" />
</p>

<p align="center">
  <strong>One desktop workspace for Android debugging, remote shells, and file operations.</strong>
</p>

**Adbnik** is a PyQt5 application that brings **ADB** workflows, **SSH** and **serial** terminals, **local ↔ remote file management** (Android device, SFTP, FTP), and **screen mirroring** launchers (e.g. scrcpy) into a single tabbed window. External tools—**adb**, **ssh**, **scrcpy**—are used from your system: install them separately and, if needed, set paths under **File → Preferences**.

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

## Requirements

- **Python 3.9+** (64-bit recommended on Windows)
- **Android:** USB debugging enabled; **platform-tools** (`adb`) available to the same environment that runs Adbnik
- **SSH:** `ssh` on `PATH` (or wherever your shell resolves it)
- **Mirroring:** `scrcpy` or another tool—`PATH` or **Preferences**
- **Serial:** Port visible to the OS with the correct driver

---

## Installation

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

**Package index:** [pypi.org/project/adbnik](https://pypi.org/project/adbnik/)

### Shortcut (Windows)

`pip` cannot place shortcuts or ask for a folder. After installing, run **once** on Windows:

```bat
adbnik-setup
```

A folder dialog opens (starting on your Desktop); choose where to put **`Adbnik.lnk`**. The shortcut uses **this Python** (`python -m adbnik`) and the same **app icon** as the window. Icon files are cached under `%LOCALAPPDATA%\Adbnik\`.

Non-interactive example (e.g. script or batch file):

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
| **Product site** | [nvnkennedy.github.io/adbnik](https://nvnkennedy.github.io/adbnik/) — overview and links |
| **Source code** | [github.com/nvnkennedy/adbnik](https://github.com/nvnkennedy/adbnik) |
| **Releases** | [GitHub Releases](https://github.com/nvnkennedy/adbnik/releases) |

---

## Building from source

```bat
git clone https://github.com/nvnkennedy/adbnik.git
cd adbnik
py -m venv .venv
.venv\Scripts\activate
py -m pip install -e ".[dev]"
py -m pytest tests -q
py -m adbnik
```

---

## License

MIT — see [LICENSE](LICENSE).
