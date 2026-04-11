# DeviceDeck Changelog

All notable changes to this project are documented in this file.

The format loosely follows Keep a Changelog and Semantic Versioning.

## [0.1.1] - 2026-04-09

### Changed
- PyPI distribution renamed to **`adbsshdeck`** (the name `devicedeck` was unavailable). Console command: **`adbsshdeck`**. Python import package remains **`devicedeck`**.

## [0.1.0] - 2026-04-09

### Added
- Production packaging pipeline with PyInstaller (`DeviceDeck.spec`).
- Windows installer icon embedding and no-console subprocess handling.
- Release helper scripts and release docs.
- GitHub Pages-ready website content under `site/`.

### Fixed
- Prevented repeated visible CMD windows in packaged app by hiding Windows subprocess windows for background commands.
- Improved process cleanup for terminal/scrcpy lifecycle on app close.
