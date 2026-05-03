# Adbnik 6.1.1

**Release date:** 2026-05-03

Apache-2.0 · PyPI package **`adbnik`** · Windows installer + portable zip on **GitHub Releases**

## Summary

**6.1.1** is the current stable label across:

| Channel | What uses `6.1.1` |
|--------|-------------------|
| **PyPI** | Wheel / sdist filenames (`adbnik-6.1.1-*`) and `pip install adbnik==6.1.1` |
| **GitHub Releases** | Tag **`v6.1.1`** — **`Adbnik-6.1.1-Setup-unsigned.exe`**, **`Adbnik-6.1.1-Windows-portable-unsigned.zip`** |
| **Application** | **Help → About** and the status bar read [`adbnik.__version__`](../adbnik/__init__.py) (aligned with `pyproject.toml`) |

## Install

### pip

```bat
py -m pip install --upgrade pip
py -m pip install adbnik==6.1.1
py -m adbnik
```

### Windows (unsigned binaries)

From **[GitHub Releases](https://github.com/nvnkennedy/adbnik/releases/latest)**:

- **`Adbnik-6.1.1-Setup-unsigned.exe`** — Inno Setup per-user install  
- **`Adbnik-6.1.1-Windows-portable-unsigned.zip`** — PyInstaller onedir, unpacked

**SmartScreen:** the `.exe` is **not** Authenticode-signed. Use **More info → Run anyway** if Windows warns.

## Changes

- Version **6.1.1** aligned across `pyproject.toml`, **`adbnik.__version__`**, Windows artifact names, **`README.md`**, **`site/`**, **`docs/index.html`**, and changelog.

## Links

- **Changelog (full):** [CHANGELOG.md](../CHANGELOG.md)  
- **Previous release notes:** [release-notes-v6.0.0.md](release-notes-v6.0.0.md)
