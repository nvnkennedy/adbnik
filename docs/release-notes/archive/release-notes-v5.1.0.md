# Adbnik 5.1.0

**Release date:** 2026-05-03

## License

The project now uses **MIT No Attribution (MIT-0)**. You may use, modify, and redistribute the software **without** being obligated to ship a copyright notice in your own releases.

## Windows installer (unsigned)

Optional **Windows** artifacts are built with **PyInstaller** + **Inno Setup** and published from **GitHub Actions** (`windows-installer` workflow) and [GitHub Releases](https://github.com/nvnkennedy/adbnik/releases):

- **`Adbnik-<version>-Setup-unsigned.exe`** — per-user installer  
- **`Adbnik-<version>-Windows-portable-unsigned.zip`** — unpacked app folder  

These files are **not** Authenticode-signed. **Microsoft SmartScreen** may show “Unknown publisher” or “Windows protected your PC.” Use **More info → Run anyway**; the warning reflects **unsigned** binaries, not an antivirus malware verdict.

Prefer **`pip install adbnik`** if you want to avoid downloaded `.exe` prompts.

## Install (pip)

```bash
py -m pip install --upgrade adbnik
```

Full history: [CHANGELOG.md](https://github.com/nvnkennedy/adbnik/blob/main/CHANGELOG.md).
