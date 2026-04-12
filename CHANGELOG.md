# Adbnik Changelog

All notable changes to this project are documented in this file.

The format loosely follows Keep a Changelog and Semantic Versioning.

## [0.2.9] - 2026-04-09

### Changed

- **README** and **GitHub Pages** show real **UI screenshots** (`docs/screenshots/*.png`) on GitHub and PyPI (absolute `raw.githubusercontent.com` URLs).

## [0.2.3] - 2026-04-11

### Changed

- **App icon** follows light/dark UI: light theme uses a light “card” icon; dark theme uses the slate tile. Taskbar/window icon updates when you toggle **View → Dark theme**.

## [0.2.2] - 2026-04-11

### Changed

- New **Adbnik** window icon (slate tile, teal accent, “A” mark)—replacing the older generic device-style glyph.
- **Version** shown in the **status bar** (bottom-right) and in **Help → About** (title + body).

## [0.2.1] - 2026-04-11

### Changed

- README rewritten for end users: what Adbnik does, install, first run, and Windows `ModuleNotFoundError: adbnik` troubleshooting.

### Fixed

- Packaging metadata description shortened; version aligned across `pyproject.toml` and `adbnik.__version__`.

## [0.2.0] - 2026-04-09

### Changed

- **Product and PyPI name:** **`adbnik`**. Console command: **`adbnik`**. Python import package: **`adbnik`** (replacing `devicedeck` / `adbsshscreen` / `adbsshdeck` naming).
- User settings file default: **`~/.adbnik.json`**, with automatic migration from **`~/.devicedeck.json`** when present.
- Windows build output: **`dist/Adbnik/`**, **`Adbnik.exe`**, installers **`Adbnik_Setup_*.exe`**.
- GitHub Pages and repository URLs target **`adbnik`** (rename the GitHub repo to match).

## [0.1.1] - 2026-04-09

### Changed

- Earlier PyPI distribution names (`adbsshdeck`, etc.) and import package `devicedeck` (superseded by 0.2.0).

## [0.1.0] - 2026-04-09

### Added

- Production packaging pipeline with PyInstaller (`adbnik.spec`).
- Windows installer icon embedding and no-console subprocess handling.
- Release helper scripts and release docs.
- GitHub Pages-ready website content under `site/`.

### Fixed

- Prevented repeated visible CMD windows in packaged app by hiding Windows subprocess windows for background commands.
- Improved process cleanup for terminal/scrcpy lifecycle on app close.
