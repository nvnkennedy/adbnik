# `installers/` — Windows build output

After a successful local or CI build:

| File | Description |
|------|-------------|
| **`Adbnik-<version>-Setup-unsigned.exe`** | Inno Setup installer (unsigned) |
| **`Adbnik-<version>-Windows-portable-unsigned.zip`** | PyInstaller **onedir** folder, zipped |

**`<version>`** comes from [`pyproject.toml`](../pyproject.toml). Local outputs here are gitignored until you build.

## Local build (Windows)

From the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File packaging\windows\build.ps1
```

Requires Python, PyInstaller, and Inno Setup 6 (`ISCC.exe`). See [`packaging/windows/README.md`](../packaging/windows/README.md).

## CI and releases

Pushing a **`v*`** version tag (for example **`v6.1.3`**) runs [`.github/workflows/windows-installer.yml`](../.github/workflows/windows-installer.yml): artifacts are attached to the matching [GitHub Release](https://github.com/nvnkennedy/adbnik/releases). Copy the same **`Adbnik-6.1.3-*`** files into **`installers/`** on branch **`main`** when you publish that snapshot, then commit.

## Unsigned installer — SmartScreen

The setup program is not Authenticode-signed. See the root [`README.md`](../README.md) and [`packaging/windows/INSTALLER_NOTICE.txt`](../packaging/windows/INSTALLER_NOTICE.txt).
