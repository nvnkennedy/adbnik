# Branch layout (`nvnkennedy/adbnik`)

This **public** repository uses **three branches** for separation of concerns:

| Branch | Purpose | Typical contents |
|--------|---------|------------------|
| **`naveen`** | **Full product tree** — application code, tests, Windows packaging, local installer outputs, marketing sources, everything you need to run tests and `packaging/windows/build.ps1`. | `adbnik/`, `tests/`, `packaging/`, `pyproject.toml`, `MANIFEST.in`, `site/`, `docs/`, `installers/`, `.github/workflows/*` (all), etc. |
| **`pypi`** | **PyPI packaging** — whatever must exist on disk for `python -m build` and the **Publish to PyPI** workflow. | Same as sdist inputs: `adbnik/`, `pyproject.toml`, `MANIFEST.in`, `README.md`, `LICENSE`, `NOTICE`, `CHANGELOG*.md`, `docs/` (per `MANIFEST.in`), `tests/`, `packaging/` if referenced, etc. Keep this branch **buildable** on every push. |
| **`main`** | **Distribution snapshot** — what you want visitors to see first on the default **GitHub** view if you use **`main`** that way: installers (and `installers/README.md`), README, website (`site/`), user-facing docs for Pages (`docs/guide/`, `docs/css/`, `docs/screenshots/`, release notes), `LICENSE`, `NOTICE`, `CHANGELOG.md` (+ legacy if shipped), `branding/`, and **`.github/workflows/pages.yml`**. You may **prune** Python sources from **`main`** only (see below); **`naveen`** always keeps the full tree. |

## Default branch on GitHub

Set the repository **default branch** to **`naveen`** so day-to-day work and pull requests open there. Use **`main`** for the trimmed **site + installers + docs** snapshot when you choose that workflow.

## CI mapping

- **`tests.yml`** — runs on pushes and pull requests to **`naveen`** and **`pypi`**.
- **`publish-pypi.yml`** — runs on pushes to **`pypi`** (and release events if configured).
- **`pages.yml`** — runs on pushes to **`main`** when `site/`, `docs/guide/`, `docs/css/`, `docs/screenshots/`, or the workflow file change.
- **`windows-installer.yml`** — runs on **`v*`** tags and manual dispatch; the tagged commit must include **`adbnik/`** and **`packaging/windows/`** (tag from **`naveen`**, not from a pruned **`main`**).

## Pruning `main` to distribution-only (optional)

While **`naveen`** carries the full tree, **`main`** can drop Python sources and tests:

1. Remove paths not needed on **`main`** (for example): `adbnik/`, `tests/`, `packaging/`, `pyproject.toml`, `MANIFEST.in`, and workflows other than **`pages.yml`** if you prefer.
2. Restore distribution paths from **`naveen`**:  
   `git checkout naveen -- README.md LICENSE NOTICE CHANGELOG.md CHANGELOG-legacy.md site docs branding installers .github/workflows/pages.yml`
3. Commit on **`main`**, then **`git push origin main`**.

Automate step 2 with **`scripts/Sync-DistributionPathsFromNaveen.ps1`**.

## Commits

Use plain commit messages. Avoid environments that inject **`Co-authored-by:`** trailers so GitHub does not list unintended co-authors.

## Stable line

**6.1.2** is the current stable version label (`pyproject.toml`, **`adbnik.__version__`**, changelog, release notes).
