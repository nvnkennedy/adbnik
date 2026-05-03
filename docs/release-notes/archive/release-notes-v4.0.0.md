# Adbnik 4.0.0

**Release date:** 2026-05-03

PyQt5 workspace for Android **ADB**, **SSH** / **serial** terminals, **SFTP** / **FTP** file transfer, and **screen mirroring** (e.g. scrcpy).

## Highlights

- **Terminal history keys:** **Up** and **Down** always drive **command-line history** when you expect them to—even if you had clicked into **scrollback**. The caret jumps to the live input line first, then walks history (same behavior no matter where the cursor was).
- **Bookmarks:** Saved sessions in the sidebar and in **Login…** open on **double-click** consistently; platform “single-click activate” for list rows is turned off so accidental opens are less likely on Windows.
- **Reliability:** Duplicate `showEvent` on the main window removed so startup geometry clamping is not shadowed by a second definition.
- **Site:** GitHub Pages landing page refreshed (visual polish, version badge).

## Install / upgrade

```bash
py -m pip install --upgrade adbnik
py -m adbnik
```

Use the **same** Python for `pip` and launch.

## Full changelog

See [CHANGELOG.md](https://github.com/nvnkennedy/adbnik/blob/main/CHANGELOG.md) in the repository.

## Previous major release

**3.0.0** removed the Camera tab and OpenCV-related dependencies; the app has three main tabs: **Terminal**, **File Explorer**, and **Screen Control**.
