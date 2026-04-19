# Adbnik

<p align="center">
  <img src="https://raw.githubusercontent.com/nvnkennedy/adbnik/main/branding/adbnik-256.png" width="128" height="128" alt="Adbnik logo" />
</p>

**Adbnik** is a PyQt5 desktop app for Android and remote workflows: **ADB** shells and shortcuts, **SSH** terminals, **serial** consoles, **file transfer** (device, SFTP, FTP), and launching **screen mirroring** (e.g. scrcpy) from one tabbed window.

Third-party tools (**adb**, **ssh**, **scrcpy**) are **not** bundled—install them separately and point to them in **File → Preferences** if they are not on your `PATH`.

---

## Features

| Area | What you get |
|------|----------------|
| **ADB** | Device list, shell tabs, APK install flow, bookmarks, quick commands |
| **SSH** | Full-screen terminal using your system OpenSSH client |
| **Serial** | COM port + baud in the UI |
| **Files** | Local ↔ remote browser (Android / SFTP / FTP) |
| **Screen** | Start and manage mirroring with your chosen executable |

---

## Requirements

- **Python 3.9+** (64-bit recommended on Windows)
- **Android:** USB debugging; **platform-tools** (`adb`) available to that Python environment
- **SSH:** `ssh` on `PATH` (or configured the same way your shell finds it)
- **Mirroring:** `scrcpy` or another tool, on `PATH` or set in Preferences
- **Serial:** Port visible to the OS with a suitable driver

---

## Install

Use one Python interpreter for both **pip** and **launch** (avoids broken entry points on Windows):

```bat
py -m pip install --upgrade pip
py -m pip install adbnik
py -m adbnik
```

With a specific interpreter:

```bat
"C:\Path\To\Python\python.exe" -m pip install adbnik
"C:\Path\To\Python\python.exe" -m adbnik
```

---

## First launch

1. Run **`python -m adbnik`** from the environment where the package is installed.
2. Set **ADB** / **scrcpy** paths under **File → Preferences** if needed.
3. Open the **Terminal**, **Files**, or **Screen** areas from the main tabs.

Configuration is stored in a **`.adbnik.json`** file under your user profile. Older **`.devicedeck.json`** settings are migrated when you save preferences.

---

## Screenshots

<p align="center">
  <img src="https://raw.githubusercontent.com/nvnkennedy/adbnik/main/docs/screenshots/01-main-window.png" width="720" alt="Main window" /><br /><br />
  <img src="https://raw.githubusercontent.com/nvnkennedy/adbnik/main/docs/screenshots/02-terminal.png" width="720" alt="Terminal" /><br /><br />
  <img src="https://raw.githubusercontent.com/nvnkennedy/adbnik/main/docs/screenshots/03-file-explorer.png" width="720" alt="File explorer" /><br /><br />
  <img src="https://raw.githubusercontent.com/nvnkennedy/adbnik/main/docs/screenshots/04-screen-control.png" width="720" alt="Screen control" />
</p>

---

## Development

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

## Troubleshooting

**`ModuleNotFoundError: No module named 'adbnik'`** — Install with the same `python.exe` you use to run the app:

```bat
"C:\Path\To\Python\python.exe" -m pip install --force-reinstall adbnik
"C:\Path\To\Python\python.exe" -m adbnik
```

On Windows, list interpreters with **`py -0p`**.

---

## Links

| Resource | URL |
|----------|-----|
| Repository | https://github.com/nvnkennedy/adbnik |
| PyPI | https://pypi.org/project/adbnik/ |
| Site | https://nvnkennedy.github.io/adbnik/ |

---

## License

MIT — see [LICENSE](LICENSE).
