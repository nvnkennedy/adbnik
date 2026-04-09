# DeviceDeck Release Guide

This folder is prepared as a standalone GitHub repo for DeviceDeck.

## Why there are two folders

- `device_deck_release/` = source code repository (what you maintain in GitHub).
- `device_deck_release_downloads/` = ready binaries for users and GitHub Release uploads.

This separation is intentional and is how most production projects are managed.

## What to share with end users

- Installer: `E:\Naveen_Python_coding\projects\device_deck_release_downloads\DeviceDeck_Setup_0.1.0.exe`
- Portable bundle: `E:\Naveen_Python_coding\projects\device_deck_release_downloads\DeviceDeck_Portable_0.1.0.zip`

Users who are not technical should use the installer `.exe`.

## Repo maintenance flow

1. Update source code.
2. Bump version in:
   - `pyproject.toml`
   - `devicedeck/__init__.py`
3. Run tests:
   - `python -m pytest tests -q`
4. Build artifacts:
   - `powershell -ExecutionPolicy Bypass -File scripts/build_windows_exe.ps1`
5. Package outputs outside this repo and place in your downloads/release folder.
6. Commit source changes to GitHub.
7. Create a GitHub Release and upload installer/zip binaries there.
8. Verify the `site/download.html` links resolve to latest release assets.

## Recommended GitHub practice

Do not commit `dist/`, `build/`, or local cache folders.
Use GitHub Releases for installer/zip binaries.
Deploy website via GitHub Actions Pages workflow (`.github/workflows/pages.yml`).
