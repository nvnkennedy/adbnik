# Adbnik

> **Branch `main`** holds the **minimal PyPI source tree** (package, tests, metadata).  
> **Installers, PyInstaller, GitHub Pages, and maintainer docs** live on branch **`naveen`**.

**Adbnik** is a **desktop control room** for Android and embedded work: **ADB shell** tabs, **SSH** sessions, **serial (COM)** consoles, **device and remote file** browsing, and **USB screen mirroring** (via scrcpy or another tool you install)—in **one window** with tabs and bookmarks.

It is **not** made by Google. It does **not** bundle ADB, OpenSSH, or scrcpy. Install those yourself (or use existing installs) and set paths under **File → Preferences** if they are not on your `PATH`.

---

## What you can do

| Goal | In Adbnik |
|------|------------|
| Shell, install, device commands | **ADB**: pick a device, open shell tabs, bookmarks and shortcuts. |
| Remote servers | **SSH** tabs using the `ssh` client on your **PATH**. |
| Boards / firmware logs over COM | **Serial**: port and baud in the same UI. |
| Files on phone or server | **File explorer** workflows (Android / remote). |
| Mirror the device screen on PC | **Screen**: launch your mirroring tool (e.g. scrcpy). |

---

## Before you install

- **Python 3.9+** (64-bit recommended on Windows).
- **Platform-tools (ADB)** on `PATH`, USB debugging on the device.
- **OpenSSH client** (`ssh`) on `PATH` for SSH tabs.
- **scrcpy** (or similar) for mirroring, on `PATH` or set in Preferences.
- **COM** hardware + driver for serial.

---

## Install

Use the **same Python** for `pip` and for running the app. On Windows this avoids broken `Scripts\adbnik.exe` installs.

**Recommended:**

```bat
py -m pip install --upgrade pip
py -m pip install adbnik
py -m adbnik
```

**If you use a specific Python (example: `C:\Python\python.exe`):**

```bat
C:\Python\python.exe -m pip install --upgrade pip
C:\Python\python.exe -m pip install adbnik
C:\Python\python.exe -m adbnik
```

Always prefer **`python -m adbnik`** if double-clicking **`adbnik.exe`** ever fails.

---

## First run

1. Start the app with **`py -m adbnik`** (or your `python -m adbnik`).
2. Set **ADB** / **scrcpy** paths in **File → Preferences** if not on `PATH`.
3. Open **ADB**, **SSH**, **Serial**, **Files**, or **Screen** from the UI.

Settings: **`%USERPROFILE%\.adbnik.json`**. An older **`.devicedeck.json`** is migrated when you save.

---

## Fix: `ModuleNotFoundError: No module named 'adbnik'`

The **`adbnik` package** is missing in the Python that runs your launcher (usually **mixed pip / mixed Python**).

```bat
C:\Python\python.exe -m pip uninstall adbnik -y
C:\Python\python.exe -m pip install --force-reinstall adbnik
C:\Python\python.exe -c "import adbnik; print(adbnik.__file__)"
C:\Python\python.exe -m adbnik
```

Use **`your\python.exe -m pip`** every time—not a different `pip` on `PATH`.

List interpreters: `py -0p`.

---

## Development

```bat
git clone https://github.com/nvnkennedy/adbnik.git
cd adbnik
git checkout main
py -m venv .venv
.venv\Scripts\activate
py -m pip install -e ".[dev]"
py -m pytest tests -q
py -m adbnik
```

Windows **.exe** builds, installers, and the project **website** are maintained on branch **`naveen`** (see that branch’s `scripts/`, `installer/`, and `site/`).

---

## Links

| | |
|--|--|
| **Repository** | [github.com/nvnkennedy/adbnik](https://github.com/nvnkennedy/adbnik) |
| **PyPI** | [pypi.org/project/adbnik](https://pypi.org/project/adbnik/) |
| **Site** | [nvnkennedy.github.io/adbnik](https://nvnkennedy.github.io/adbnik/) |

---

## License

MIT — see [LICENSE](LICENSE).
