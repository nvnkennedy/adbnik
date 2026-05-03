# Git branch layout

| Branch | Contents |
|--------|----------|
| **`main`** | **Public release branch:** what visitors see by default. **No application source** in the tree (no `adbnik/`, no `pyproject.toml`, no `packaging/`). Includes **`LICENSE`**, **`NOTICE`**, full **[`README.md`](README.md)** (same story as PyPI), **`CHANGELOG*.md`**, **`docs/`**, **`site/`**, **`branding/`**, and **`installers/`** — **release `.exe` / `.zip` binaries are committed here** after each version ships (see [`installers/README.md`](installers/README.md)). **GitHub Pages** deploys from pushes to **`main`**. |
| **`naveen`** | **Personal / maintainer branch — full codebase:** Python package, tests, `pyproject.toml`, `packaging/windows/`, PyInstaller + Inno CI, pytest. **`README.md` here is what PyPI shows** (`readme` in `pyproject.toml`). **Create `v*` tags from here** so the Windows workflow runs. |
| **`pypi`** | Same complete tree as **`naveen`**. Pushing **`pypi`** runs [`.github/workflows/publish-pypi.yml`](.github/workflows/publish-pypi.yml) (needs `PYPI_API_TOKEN`). |

## Installers on `main`

Builds are produced on **`naveen`** (CI or `packaging\windows\build.ps1`). For the **public release repo**, copy the resulting **`Adbnik-*-Setup-unsigned.exe`** and **`Adbnik-*-Windows-portable-unsigned.zip`** into **`installers/`** on **`main`** and commit (this branch’s `.gitignore` allows those files).

## Local Windows build

Run **`packaging\windows\build.ps1`** only from **`naveen`** (or **`pypi`**), not from **`main`**.

## PyPI

- **Automated:** push branch **`pypi`**, or publish a **GitHub Release** (workflow on **`naveen`**).
- **Manual:** on **`naveen`**, `python -m build` then `twine upload dist/adbnik-<version>-*.whl dist/adbnik-<version>.tar.gz`.

## README alignment

**`naveen`/`README.md`** is the PyPI long description (`readme` in `pyproject.toml`). **`main`/`README.md`** should stay **word-aligned** on every end-user section (capabilities, guide links, pip, SmartScreen, screenshots, troubleshooting, license). Only the **top callout**, the **PyPI metadata** paragraph on **`main`** (absolute link to `pyproject.toml` on `naveen`), and **Building from source** differ.

Do **not** merge **`main`** into **`naveen`** — that would delete source on **`naveen`**. To refresh **`main`**, cherry-pick or copy **docs / site / changelog / README / installers** only from **`naveen`**.
