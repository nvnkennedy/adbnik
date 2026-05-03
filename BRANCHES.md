# Git branch layout

| Branch | Contents |
|--------|----------|
| **`main`** | **Distribution & website only:** `LICENSE`, `NOTICE`, `README.md`, `CHANGELOG.md`, `CHANGELOG-legacy.md`, `docs/` (including release notes), `site/` (GitHub Pages marketing), `branding/` (icons referenced by URLs), `installers/README.md`. **No** `adbnik/` package, **no** `pyproject.toml`, **no** `packaging/`. Pushing here updates **GitHub Pages** when `site/` or `docs/guide/` / `docs/css/` change. |
| **`naveen`** | **Full application source:** Python package, tests, `pyproject.toml`, `packaging/windows/`, PyInstaller + Inno workflows, pytest CI. **Create `v*` version tags from this branch** so Windows installer artifacts attach to the correct GitHub Release. |
| **`pypi`** | Same **complete** tree as **`naveen`** at release points. A **push** to `pypi` runs [`.github/workflows/publish-pypi.yml`](.github/workflows/publish-pypi.yml) and publishes the current `pyproject.toml` version to PyPI (requires `PYPI_API_TOKEN` in repo secrets). |

## Local Windows installer

Run **`packaging\windows\build.ps1`** only from a checkout of **`naveen`** (or **`pypi`**), not from **`main`**.

## PyPI

- **Automated:** push to branch **`pypi`** (after aligning `pyproject.toml` version), or publish a **GitHub Release** (existing workflow).
- **Manual:** from **`naveen`**, `python -m build` then `twine upload dist/adbnik-<version>-*.whl dist/adbnik-<version>.tar.gz`.

Do **not** merge **`main`** into **`naveen`** after `main` was trimmed to docs-only — that would delete application code on `naveen`. Port changes with cherry-picks or file-by-file PRs from `naveen` → `main` for docs/site only.
