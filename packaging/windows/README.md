# Windows packaging (unsigned)

1. **Onedir app** — `build.ps1` runs **PyInstaller** and produces `dist\Adbnik\Adbnik.exe` (plus DLLs in the same folder).
2. **Optional installer** — if [Inno Setup 6](https://jrsoftware.org/isinfo.php) is installed (or `choco install innosetup` on a dev machine), the same script runs `ISCC` and writes **`installers\Adbnik-<version>-Setup-unsigned.exe`** at the repo root.
3. **Portable zip** — `installers\Adbnik-<version>-Windows-portable-unsigned.zip` at the **repository root** (contents of the PyInstaller onedir).

The bundle is **not code-signed**. Windows SmartScreen may show a warning; see the main [README](../../README.md) section *Windows: unsigned installer and SmartScreen* and `INSTALLER_NOTICE.txt` (shown in the installer).

CI: workflow **`.github/workflows/windows-installer.yml`** runs the same steps on `workflow_dispatch` and on version tags `v*`. Both write outputs to **`installers/`** at the repo root (see **[`installers/README.md`](../../installers/README.md)**).
