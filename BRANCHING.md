# Branch layout (`nvnkennedy/adbnik-dev`)

Use **three branches** in this private repository, then mirror **`main`** to the public **`nvnkennedy/adbnik`** **`main`** branch when you want the public site and installers updated.

| Branch | Purpose | Typical contents |
|--------|---------|------------------|
| **`naveen`** | **Full product tree** — application code, tests, Windows packaging, local installer outputs, marketing sources, everything you need to run tests and `packaging/windows/build.ps1`. | `adbnik/`, `tests/`, `packaging/`, `pyproject.toml`, `MANIFEST.in`, `site/`, `docs/`, `installers/`, `.github/workflows/*` (all), etc. |
| **`pypi`** | **PyPI packaging** — whatever must exist on disk for `python -m build` and the **Publish to PyPI** workflow. | Same as today’s sdist inputs: `adbnik/`, `pyproject.toml`, `MANIFEST.in`, `README.md`, `LICENSE`, `NOTICE`, `CHANGELOG*.md`, `docs/` (per `MANIFEST.in`), `tests/`, `packaging/` if referenced, etc. Keep this branch **buildable** on every push. |
| **`main`** | **Public distribution snapshot** — only what belongs on the **public** repo: installers (and `installers/README.md`), README, website (`site/`), user-facing docs used by Pages (`docs/guide/`, `docs/css/`, `docs/screenshots/`, release notes HTML/markdown as you publish), `LICENSE`, `NOTICE`, `CHANGELOG.md` (+ legacy if you ship it), `branding/`, and **`.github/workflows/pages.yml`** (GitHub Actions → GitHub Pages). **No** `adbnik/` package sources on this branch once you prune (public `adbnik` is not required to host Python sources if you prefer installers + site only). |

## Default branch on GitHub

Set the repository **default branch** to **`naveen`** so day-to-day work and PRs open there. Keep **`main`** as the branch you fast-forward or merge into when cutting a public snapshot.

## CI mapping

- **`tests.yml`** — runs on pushes and PRs to **`naveen`** and **`pypi`** (both must be able to `pip install -e ".[dev]"` and run pytest).
- **`publish-pypi.yml`** — runs on pushes to **`pypi`** (and release events if you use them).
- **`pages.yml`** — runs on pushes to **`main`** under `site/`, `docs/guide/`, `docs/css/`, `docs/screenshots/`, or the workflow file.
- **`windows-installer.yml`** — runs on **`v*`** tags and manual dispatch; the tagged commit must include **`adbnik/`** and **`packaging/windows/`** (create tags from **`naveen`**, not from a pruned **`main`**).

## Sync to public `nvnkennedy/adbnik`

After **`main`** contains the snapshot you want (installers committed if you ship binaries from git, site, docs, changelog):

```bash
git remote add public https://github.com/nvnkennedy/adbnik.git   # once
git push public main:main
```

Use **`--force-with-lease`** only if you intentionally replace the public default branch.

## Pruning `main` to distribution-only

While **`naveen`** carries the full tree, **`main`** can drop Python sources and tests. From a clean worktree on **`main`**:

1. Remove paths that must not ship on public **`main`** (example): `adbnik/`, `tests/`, `packaging/`, `pyproject.toml`, `MANIFEST.in`, and workflows other than **`pages.yml`** if you do not want them public.
2. Restore distribution paths from **`naveen`**:  
   `git checkout naveen -- README.md LICENSE NOTICE CHANGELOG.md CHANGELOG-legacy.md site docs branding installers .github/workflows/pages.yml`
3. Commit on **`main`**, then **`git push origin main`** and **`git push public main:main`**.

Automate step 2 with **`scripts/Sync-DistributionPathsFromNaveen.ps1`**. Run step 1 manually once per layout change (or extend the script with an explicit remove list).

## Commits: no co-author / no Cursor attribution

Use plain commit messages and commit **outside** any environment that injects **`Co-authored-by:`** trailers, so GitHub does not list unwanted co-authors on **`nvnkennedy/adbnik-dev`** or **`nvnkennedy/adbnik`**.

## Stable line

**6.1.1** is the current stable version label in this layout (`pyproject.toml`, **`adbnik.__version__`**, changelog, release notes).
