# Adbnik

<p align="center">
  <img src="https://raw.githubusercontent.com/nvnkennedy/adbnik/main/branding/adbnik-256.png" width="128" height="128" alt="Adbnik" />
</p>

**Adbnik** is a **desktop control room** for Android and embedded work: **ADB shell** tabs, **SSH** sessions, **serial (COM)** consoles, **device and remote file** browsing, and **USB screen mirroring** (via scrcpy or another tool you install)—in **one window** with tabs and bookmarks.

It is **not** made by Google. It does **not** bundle ADB, OpenSSH, or scrcpy. Install those yourself (or use existing installs) and set paths under **File → Preferences** if they are not on your `PATH`.

**Positioning:** Adbnik is an **ADB device workspace**—an **ADB explorer–style workflow** in one window: shells, on-device files, optional **APK** push via `adb install`, plus SSH, serial, and launching your mirroring binary. The product name stays **Adbnik** everywhere.

### Why “Adbnik”

The name keeps **ADB** visible and uses **‑nik** as a short, memorable suffix (a compact “nickname” for an ADB‑centric desktop). It is **not** a Google or Android trademark; the project is **Adbnik** only.

---

## What you can do

| Goal | In Adbnik |
|------|------------|
| Shell, APK install, device commands | **ADB**: pick a device, shell tabs, **Session → ADB → Install APK**, bookmarks, shortcuts. |
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

**If you use a specific Python installation, use that interpreter for both `pip` and `adbnik`:**

```bat
"C:\Path\To\Python\python.exe" -m pip install --upgrade pip
"C:\Path\To\Python\python.exe" -m pip install adbnik
"C:\Path\To\Python\python.exe" -m adbnik
```

Always prefer **`python -m adbnik`** if double-clicking **`adbnik.exe`** ever fails.

---

## First run

1. Start the app with **`py -m adbnik`** (or **`python -m adbnik`** from the environment where you installed the package).
2. Set **ADB** / **scrcpy** paths in **File → Preferences** if not on `PATH`.
3. Open **ADB**, **SSH**, **Serial**, **Files**, or **Screen** from the UI.

**Settings** are stored in a **`.adbnik.json`** file under your user profile. If you previously used an older config named **`.devicedeck.json`**, it is migrated when you save preferences.

---

## Fix: `ModuleNotFoundError: No module named 'adbnik'`

The package is not installed for the same Python that runs your command or shortcut (often **mixed `pip` / mixed Python**). Reinstall using **that** interpreter:

```bat
"C:\Path\To\Python\python.exe" -m pip uninstall adbnik -y
"C:\Path\To\Python\python.exe" -m pip install --force-reinstall adbnik
"C:\Path\To\Python\python.exe" -c "import adbnik; print(adbnik.__file__)"
"C:\Path\To\Python\python.exe" -m adbnik
```

Use **`python.exe -m pip`** for the same **`python.exe`** you use to run the app—not a different `pip` on `PATH`.

On Windows, list interpreters: `py -0p`.

---

## Development

From a clone of this repository:

```bat
git clone https://github.com/nvnkennedy/adbnik.git
cd adbnik
py -m venv .venv
.venv\Scripts\activate
py -m pip install -e ".[dev]"
py -m pytest tests -q
py -m adbnik
```

Optional **Windows installers** or other distribution formats may be published via **GitHub Releases** or the **project site** (see links below)—not part of the PyPI package.

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
