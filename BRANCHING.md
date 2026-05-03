# Branch layout (`nvnkennedy/adbnik`)

This **public** repository uses two primary branches:

| Branch | Purpose |
|--------|---------|
| **`naveen`** | **Full product tree** — Python package (`adbnik/`), tests, Windows packaging (`packaging/`), `pyproject.toml`, `MANIFEST.in`, workflows (**tests**, **windows-installer**, **Publish to PyPI**), marketing sources (`site/`, `docs/`, `branding/`), `installers/` metadata, and `README.md` as edited by maintainers. **Tag `v*`** releases and **PyPI** publishing are done from here. |
| **`main`** | **Distribution snapshot** — installers (and `installers/README.md`), `README.md`, `LICENSE`, `NOTICE`, `CHANGELOG.md` (+ `CHANGELOG-legacy.md` if kept), `site/`, `branding/`, `docs/guide/`, `docs/css/`, `docs/screenshots/`, `docs/release-notes-*.md` (for deep links), and **`.github/workflows/pages.yml`** only. **No** `adbnik/` sources, **no** `tests/`, **no** `packaging/`, **no** `pyproject.toml` on this branch. |

## PyPI publishing

The **Publish to PyPI** workflow runs only when:

- you **publish a GitHub Release**, or  
- you run **Actions → Publish to PyPI → Run workflow** manually.

It does **not** run on every branch push, so you avoid “this file already exists” errors when the version on PyPI is unchanged.

Ensure repository **Settings → Secrets and variables → Actions** defines **`PYPI_API_TOKEN`**.

## GitHub Pages

The **pages** workflow (on **`main`**) copies `site/`, `docs/guide/`, `docs/css/`, `docs/screenshots/`, and **`branding/*.png` / `branding/*.ico`** into the published tree so **`/branding/...`** URLs work.

## Default branch

Set GitHub’s **default branch** to **`naveen`** so issues and pull requests target the full tree. Visitors can still open **`main`** for the trimmed snapshot.

## Prune or refresh `main`

From a clean worktree on **`main`**:

1. Optionally remove old paths: `adbnik/`, `tests/`, `packaging/`, `scripts/`, `pyproject.toml`, `MANIFEST.in`, `main.py`, `BRANCHING.md`, and workflows other than **`pages.yml`**.
2. Restore from **`naveen`**:  
   `git checkout naveen -- README.md LICENSE NOTICE CHANGELOG.md CHANGELOG-legacy.md site docs branding installers .github/workflows/pages.yml`  
   (Use a subset of `docs/` if you prefer; at minimum include `docs/guide`, `docs/css`, `docs/screenshots`, and `docs/release-notes-v*.md`.)
3. Commit and **`git push origin main`**.

Helper: **`scripts/Sync-DistributionPathsFromNaveen.ps1`**.

## Commits

Use plain commit messages. Avoid environments that inject **`Co-authored-by:`** trailers.

## Stable line

**6.1.3** is the current stable version label (`pyproject.toml` on **`naveen`**, **`adbnik.__version__`**, changelog, release notes).
