# Windows packaging (unsigned)

1. **Onedir app** — `build.ps1` runs **PyInstaller** and produces `dist\Adbnik\Adbnik.exe` (plus DLLs in the same folder).
2. **Optional installer** — if [Inno Setup 6](https://jrsoftware.org/isinfo.php) is installed (or `choco install innosetup` on a dev machine), the same script runs `ISCC` and writes `dist_installer\Adbnik-<version>-Setup-unsigned.exe`.
3. **Portable zip** — `dist_installer\Adbnik-<version>-Windows-portable-unsigned.zip` (contents of the onedir folder).

The bundle is **not code-signed**. Windows SmartScreen may show a warning; see the main [README](../../README.md) section *Windows: unsigned installer and SmartScreen* and `INSTALLER_NOTICE.txt` (shown in the installer).

CI: workflow **`.github/workflows/windows-installer.yml`** runs the same steps on `workflow_dispatch` and on version tags `v*`.
