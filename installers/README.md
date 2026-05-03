# `installers/` — Windows release files

Each shipped version adds:

| File | Description |
|------|-------------|
| **`Adbnik-<version>-Setup-unsigned.exe`** | Inno Setup installer (unsigned) |
| **`Adbnik-<version>-Windows-portable-unsigned.zip`** | PyInstaller **onedir**, zipped |

Builds are produced in the private development repository, then copied here for download from the default branch. The same files are on [GitHub Releases](https://github.com/nvnkennedy/adbnik/releases).

**SmartScreen:** the `.exe` is not Authenticode-signed. See the root [`README.md`](../README.md).
