# Adbnik 6.1.2

**Release date:** 2026-05-03

Apache-2.0 · PyPI package **`adbnik`** · Windows installer + portable zip on **GitHub Releases** (**`nvnkennedy/adbnik`**)

## Summary

**6.1.2** is the current stable label on **PyPI** and in this repository (`pyproject.toml`, **`adbnik.__version__`**, changelog, **`site/`** and **`docs/`** copy).

| Channel | What uses `6.1.2` |
|--------|-------------------|
| **PyPI** | Wheel / sdist filenames (`adbnik-6.1.2-*`) and `pip install adbnik==6.1.2` |
| **GitHub Releases** | Tag **`v6.1.2`** — **`Adbnik-6.1.2-Setup-unsigned.exe`**, **`Adbnik-6.1.2-Windows-portable-unsigned.zip`** |
| **Application** | **Help → About** and the status bar read **`adbnik.__version__`** (aligned with `pyproject.toml`) |

## Install

### pip

```bat
py -m pip install --upgrade pip
py -m pip install adbnik==6.1.2
py -m adbnik
```

### Windows (unsigned binaries)

From **[GitHub Releases](https://github.com/nvnkennedy/adbnik/releases/latest)**:

- **`Adbnik-6.1.2-Setup-unsigned.exe`** — Inno Setup per-user install  
- **`Adbnik-6.1.2-Windows-portable-unsigned.zip`** — PyInstaller onedir, unpacked

**SmartScreen:** the `.exe` is **not** Authenticode-signed. Use **More info → Run anyway** if Windows warns.

## Changes

- **Stable line:** **6.1.2** aligned with **PyPI** and repository metadata.
- **Repository:** development and release automation live in this public **`nvnkennedy/adbnik`** repo; branches **`naveen`**, **`pypi`**, and **`main`** are described in [`BRANCHING.md`](../BRANCHING.md).

## Links

- **Changelog (full):** [CHANGELOG.md](../CHANGELOG.md)  
- **Previous release notes:** [release-notes-v6.1.1.md](release-notes-v6.1.1.md)
