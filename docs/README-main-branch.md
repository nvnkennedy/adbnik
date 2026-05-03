# Adbnik — distribution branch (`main`)

This branch holds **license**, **changelog / release notes**, **documentation**, **marketing site sources**, and **branding** — not the Python application tree.

| Need | Where |
|------|--------|
| **Source code**, `pip install -e .`, tests, **local Windows build** | Branch **[`naveen`](https://github.com/nvnkennedy/adbnik/tree/naveen)** |
| **PyPI publish via git push** | Branch **[`pypi`](https://github.com/nvnkennedy/adbnik/tree/pypi)** (same layout as `naveen`; see [`.github/workflows/publish-pypi.yml`](.github/workflows/publish-pypi.yml)) |
| **Windows `.exe` / portable zip** | Built in CI when you push a **`v*`** tag from **`naveen`**; assets attach to [GitHub Releases](https://github.com/nvnkennedy/adbnik/releases). See [`installers/README.md`](installers/README.md). |
| **Full layout** | **[`BRANCHES.md`](BRANCHES.md)** |

## On this branch

- **`LICENSE`**, **`NOTICE`** — Apache-2.0 and attribution boilerplate.
- **`CHANGELOG.md`**, **`CHANGELOG-legacy.md`**, **`docs/release-notes-*.md`** — release history.
- **`docs/`** — user guide HTML, CSS, and project docs (see `docs/index.html`).
- **`site/`** — GitHub Pages landing assets; deploy workflow runs on push to **`main`** (see `site/DEPLOY.md`).
- **`branding/`** — icons used by README and the site (raw GitHub URLs often point at **`main`**).

## Install (end users)

Use **PyPI** and **GitHub Releases** as usual — packages and installers are produced from **`naveen`** / **`pypi`**, not from this branch’s tree:

```bat
py -m pip install adbnik
```

---

<p align="center">
  <img src="https://raw.githubusercontent.com/nvnkennedy/adbnik/main/branding/adbnik-256.png" width="128" height="128" alt="Adbnik" />
</p>

<p align="center">
  <strong>One desktop workspace for Android debugging, remote shells, and file operations.</strong>
</p>

For capabilities, user guide links, and SmartScreen notes, see the **[same README on `naveen`](https://github.com/nvnkennedy/adbnik/blob/naveen/README.md)** (full copy).
