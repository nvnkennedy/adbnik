# Adbnik 6.0.0

**Release date:** 2026-05-03

Apache-2.0 · PyPI package **`adbnik`** · Windows installer + portable zip on **GitHub Releases**

## Summary

**6.0.0** is the unified version across:

| Channel | What uses `6.0.0` |
|--------|-------------------|
| **PyPI** | Wheel / sdist filenames (`adbnik-6.0.0-*`) and `pip install adbnik==6.0.0` |
| **GitHub Releases** | Tag **`v6.0.0`** — **`Adbnik-6.0.0-Setup-unsigned.exe`**, **`Adbnik-6.0.0-Windows-portable-unsigned.zip`** |
| **Application** | **Help → About** reads [`adbnik.__version__`](../adbnik/__init__.py) (from `pyproject.toml`) |

This release continues the public product from the **1.0.x** line; the version number is bumped to **6.0.0** so PyPI, installers, marketing sites, and CI share one label.

## Install

### pip

```bat
py -m pip install --upgrade pip
py -m pip install adbnik==6.0.0
py -m adbnik
```

### Windows (unsigned binaries)

From **[GitHub Releases](https://github.com/nvnkennedy/adbnik/releases/latest)**:

- **`Adbnik-6.0.0-Setup-unsigned.exe`** — Inno Setup per-user install  
- **`Adbnik-6.0.0-Windows-portable-unsigned.zip`** — PyInstaller onedir, unpacked

**SmartScreen:** the `.exe` is **not** Authenticode-signed. Use **More info → Run anyway** if Windows warns.

## Changes

- Aligns version **6.0.0** everywhere: `pyproject.toml`, Windows packaging ([`packaging/windows/`](../packaging/windows)), site/docs copy, and changelog.
- Windows build: read `pyproject.toml` version on Python 3.10 without `tomllib`; stage PyInstaller output before zipping to reduce DLL lock failures ([`packaging/windows/build.ps1`](../packaging/windows/build.ps1)). CI uses the same staging logic ([`.github/workflows/windows-installer.yml`](../.github/workflows/windows-installer.yml)).

## Links

- **Changelog (full):** [CHANGELOG.md](../CHANGELOG.md)  
- **Previous public baseline notes:** [release-notes-v1.0.0.md](release-notes-v1.0.0.md) (historical)  
- **User guide:** [guide/index.html](guide/index.html)
