# Adbnik

**Adbnik** is a desktop app for people who live in **ADB shells**, **SSH sessions**, **serial consoles**, and **on-device file trees**—and want one place to run them instead of juggling five terminals and three bookmark files.

It is built with **PyQt5** for Windows (and runs where Python + Qt do). You bring your own **platform-tools** (ADB), **OpenSSH** client, **scrcpy** (or similar) for USB display forwarding, and **serial hardware**; Adbnik wires them into a single window with tabs, bookmarks, and sane defaults.

---

## What you get

- **ADB** — pick a device, open shell tabs, drive common actions from the UI instead of retyping paths.
- **SSH** — terminal tabs that use the `ssh` on your PATH; session fields line up with remote file access where it matters.
- **Serial** — COM ports at your baud rate, next to everything else.
- **Files** — browse and transfer on Android and remote hosts from the same app.
- **Screen** — start USB mirroring through the tool you configure (e.g. scrcpy); embedding vs separate window is a preference, not a fight with the rest of the UI.

This is a **workbench**, not a cloud service and not a Google product. It does not ship Google’s binaries; it expects you to install standard tools and point to them in **Preferences** if they are not on `PATH`.

---

## Install

Requires **Python 3.9+**.

```bash
python -m pip install --upgrade pip
python -m pip install adbnik
adbnik
```

Equivalent: `python -m adbnik`

First run may ask for basic paths (ADB, scrcpy, etc.). Settings live in **`~/.adbnik.json`** (with migration from an older **`.devicedeck.json`** if it exists).

---

## Links

| | |
|--|--|
| **Source & issues** | [github.com/nvnkennedy/adbnik](https://github.com/nvnkennedy/adbnik) |
| **PyPI** | [pypi.org/project/adbnik](https://pypi.org/project/adbnik/) |
| **Site** | [nvnkennedy.github.io/adbnik](https://nvnkennedy.github.io/adbnik/) (after Pages is enabled — see `site/DEPLOY.md`) |

---

## Development

```bash
git clone https://github.com/nvnkennedy/adbnik.git
cd adbnik
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -e ".[dev]"
python -m pytest tests/ -q
python -m adbnik
```

Optional Windows packaging: see `adbnik.spec` and `scripts/build_windows_exe.ps1`. Installers live under `installer/` (Inno Setup / NSIS) for maintainers who ship `.exe` builds.

---

## PyPI: if you published older names before

PyPI **never deletes** a project name. You **cannot** remove `devicedeck` (or similar) from the index entirely.

**What to do:**

1. Sign in at [pypi.org](https://pypi.org) → open the **old** project (e.g. `devicedeck`).
2. **Manage** → **Releases** → for each release you want to block: **Yank** (add a reason like “Superseded by `adbnik`”).
3. In **Project description** (or README on the PyPI project page), add one line: *Deprecated — use `pip install adbnik`.*
4. Publish **`adbnik`** from this repo (`python -m build` → `twine upload`) so the new name is the one people should install.

Details for maintainers: [docs/PYPI_PUBLISH.md](docs/PYPI_PUBLISH.md).

---

## License

MIT — see [LICENSE](LICENSE).
