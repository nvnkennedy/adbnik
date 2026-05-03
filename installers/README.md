# `installers/` — Windows build output (repo root)

After a successful local or CI build, this folder contains:

| File | Description |
|------|-------------|
| **`Adbnik-<version>-Setup-unsigned.exe`** | Inno Setup installer (unsigned) |
| **`Adbnik-<version>-Windows-portable-unsigned.zip`** | PyInstaller **onedir** folder, zipped |

**`<version>`** comes from `pyproject.toml` (currently **1.0.0**).

## Why you might not see files here

These binaries are **build artifacts**, not committed to git (see root `.gitignore`). The folder is empty until you build.

## Generate locally (Windows)

From the **repository root**:

```powershell
powershell -ExecutionPolicy Bypass -File packaging\windows\build.ps1
```

Requires **Python** + **PyInstaller**; the `.exe` also needs **Inno Setup 6** (`ISCC.exe`). See [`packaging/windows/README.md`](../packaging/windows/README.md).

## CI / GitHub Releases

Pushing tag **`v1.0.0`** (or any **`v*`** tag) runs [`.github/workflows/windows-installer.yml`](../.github/workflows/windows-installer.yml): it fills **`installers/`** the same way, uploads **artifacts**, and attaches **`*.exe`** / **`*.zip`** to the matching **GitHub Release**.

## Unsigned installer — SmartScreen

The setup program is **not** code-signed. Windows may show **Unknown publisher** — use **More info → Run anyway**. See [`README.md`](../README.md) and [`packaging/windows/INSTALLER_NOTICE.txt`](../packaging/windows/INSTALLER_NOTICE.txt).
