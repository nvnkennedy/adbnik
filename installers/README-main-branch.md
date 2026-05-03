# `installers/` — Windows build output

This folder on **`main`** is documented only — **binaries are not committed** (see root `.gitignore`).

| Artifact | Produced how |
|----------|----------------|
| **`Adbnik-<version>-Setup-unsigned.exe`** | Inno Setup, from **`naveen`** CI or local `build.ps1` |
| **`Adbnik-<version>-Windows-portable-unsigned.zip`** | PyInstaller onedir, zipped |

**`<version>`** comes from `pyproject.toml` on **`naveen`** / **`pypi`** (currently **6.0.0**).

## Where builds run

- **GitHub Actions:** Pushing a **`v*`** tag on commits that include **`packaging/windows/`** (i.e. branch **`naveen`**) runs [`.github/workflows/windows-installer.yml`](../.github/workflows/windows-installer.yml) and attaches **`*.exe`** / **`*.zip`** to that [Release](https://github.com/nvnkennedy/adbnik/releases).
- **Local:** Clone **`naveen`**, then from repo root run `powershell -ExecutionPolicy Bypass -File packaging\windows\build.ps1`. Outputs land in **`installers/`** here when you use a worktree or switch branches — or stay under `naveen`’s tree.

See **[`BRANCHES.md`](../BRANCHES.md)** and **[`packaging/windows/README.md`](../packaging/windows/README.md)**.
