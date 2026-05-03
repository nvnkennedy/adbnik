# Adbnik 6.1.3

**Release date:** 2026-05-04

Apache-2.0 · PyPI package **`adbnik`** · Windows installer + portable zip on **GitHub Releases** (**`nvnkennedy/adbnik`**)

## Summary

**6.1.3** is the current stable label on **PyPI** and in this repository (`pyproject.toml`, **`adbnik.__version__`**, changelog, **`site/`** and **`docs/`** copy).

| Channel | What uses `6.1.3` |
|--------|-------------------|
| **PyPI** | Wheel / sdist filenames (`adbnik-6.1.3-*`) and `pip install adbnik==6.1.3` |
| **GitHub Releases** | Tag **`v6.1.3`** — **`Adbnik-6.1.3-Setup-unsigned.exe`**, **`Adbnik-6.1.3-Windows-portable-unsigned.zip`** |
| **Application** | **Help → About** and the status bar read **`adbnik.__version__`** |

## Install

### pip

```bat
py -m pip install --upgrade pip
py -m pip install adbnik==6.1.3
py -m adbnik
```

### Windows (unsigned binaries)

From **[GitHub Releases](https://github.com/nvnkennedy/adbnik/releases/latest)**:

- **`Adbnik-6.1.3-Setup-unsigned.exe`** — Inno Setup per-user install  
- **`Adbnik-6.1.3-Windows-portable-unsigned.zip`** — PyInstaller onedir, unpacked

## Changes

- **Pages:** deploy job now copies **`branding/*.png`** and **`branding/*.ico`** into **`publish/branding/`** so **`https://nvnkennedy.github.io/adbnik/branding/...`** and same-origin **`branding/...`** links resolve.
- **PyPI CI:** publish workflow no longer runs on every push to a packaging branch (prevents “file already exists” failures when the version was unchanged).
- **README / PyPI listing:** logo and screenshots use **`raw.githubusercontent.com/nvnkennedy/adbnik/naveen/...`** so images render even before the next Pages build.

## Links

- **Changelog (full):** [CHANGELOG.md](../CHANGELOG.md)  
- **Previous release notes:** [release-notes-v6.1.2.md](release-notes-v6.1.2.md)
