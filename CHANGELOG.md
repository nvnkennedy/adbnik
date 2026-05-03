# Adbnik Changelog

All notable changes are documented here.

**Current stable** uses the **`6.x`** version line on PyPI and GitHub Releases. The first **public** baseline was **`1.0.0`**; development-era **2.x–5.x** on PyPI remains summarized in [`CHANGELOG-legacy.md`](CHANGELOG-legacy.md).

The format follows Keep a Changelog and Semantic Versioning.

## [6.1.2] - 2026-05-03

### Summary

**6.1.2** is the stable line on **PyPI** (wheel + sdist) and the version label in this repository. Source, packaging, and docs now live in the public **`nvnkennedy/adbnik`** repository with branches **`naveen`** (full tree), **`pypi`** (PyPI CI), and **`main`** (distribution snapshot when pruned). See [`BRANCHING.md`](BRANCHING.md).

### Distribution

- **PyPI:** **`adbnik==6.1.2`**. See [`docs/release-notes-v6.1.2.md`](docs/release-notes-v6.1.2.md).
- **Windows:** **`Adbnik-6.1.2-Setup-unsigned.exe`** and **`Adbnik-6.1.2-Windows-portable-unsigned.zip`** when tag **`v6.1.2`** is built from **`naveen`** and attached to **GitHub Releases**.

---

## [6.1.1] - 2026-05-03

### Summary

**6.1.1** is the stable public line across **PyPI**, **Windows installers** (`build.ps1` / GitHub Releases), marketing **`site/`** and **`docs/`** copy, **`README.md`**, and **`adbnik.__version__`** (status bar and **Help → About**).

### Fixed

- **PyPI / README images:** README screenshots and logo use **`https://nvnkennedy.github.io/adbnik/...`** so the listing does not depend on **`raw.githubusercontent.com/.../main/...`** being populated. **GitHub Pages** publishes **`docs/screenshots/`** under **`/screenshots/`**; **`site/index.html`** uses same-origin **`screenshots/...`** links.

### Distribution

- **PyPI:** **`adbnik==6.1.1`** (wheel + sdist). See [`docs/release-notes-v6.1.1.md`](docs/release-notes-v6.1.1.md).
- **Windows:** **`Adbnik-6.1.1-Setup-unsigned.exe`** and **`Adbnik-6.1.1-Windows-portable-unsigned.zip`** under **`installers/`** and on **GitHub Releases** for tag **`v6.1.1`**.

---

## [6.0.0] - 2026-05-03

### Summary

**6.0.0** is the single version label across **PyPI** (wheel + sdist), **GitHub Releases** (Windows installer + portable zip), **Inno Setup** / **`build.ps1`** artifact names, marketing pages, and **`adbnik.__version__`**.

### Released

- **`adbnik==6.0.0`** uploaded to **PyPI** (wheel + sdist).
- **Windows:** `Adbnik-6.0.0-Setup-unsigned.exe` and `Adbnik-6.0.0-Windows-portable-unsigned.zip` built with **`packaging/windows/build.ps1`**; the same files are committed under **`installers/`** on the public **`adbnik`** `main` branch.

### Distribution

- **PyPI:** publish **`adbnik==6.0.0`** (artifacts `adbnik-6.0.0-py3-none-any.whl`, `adbnik-6.0.0.tar.gz`). See [`docs/release-notes-v6.0.0.md`](docs/release-notes-v6.0.0.md).
- **GitHub Releases:** push tag **`v6.0.0`** — workflow [`.github/workflows/windows-installer.yml`](.github/workflows/windows-installer.yml) attaches **`Adbnik-6.0.0-Setup-unsigned.exe`** and **`Adbnik-6.0.0-Windows-portable-unsigned.zip`** into **`installers/`** and to the release. See [`installers/README.md`](installers/README.md).

### Fixed

- **Windows packaging:** Read version from `pyproject.toml` on **Python 3.10** without stdlib `tomllib`; copy PyInstaller **`dist\Adbnik`** to a staging folder before **`Compress-Archive`** with retries (local script and CI).

### Windows installer (unsigned)

The setup program is **not** Authenticode-signed. **Microsoft SmartScreen** may warn (“Unknown publisher”). Use **More info → Run anyway**; see [`README.md`](README.md) and [`packaging/windows/INSTALLER_NOTICE.txt`](packaging/windows/INSTALLER_NOTICE.txt).

---

## [1.0.1] - 2026-05-03

### Fixed

- **PyPI:** Publishing requires **new artifact filenames** after deleted uploads — PyPI never allows reusing a filename ([file name reuse](https://pypi.org/help/#file-name-reuse)).
- **Windows packaging:** Read version from `pyproject.toml` on **Python 3.10** (no `tomllib`); staging folder before zip.

## [1.0.0] - 2026-05-03

### Summary

First **public** release under **`1.0.0`** numbering.

### License

- **Apache License 2.0** ([`LICENSE`](LICENSE), SPDX **`Apache-2.0`**) with [`NOTICE`](NOTICE).

### Distribution

- **PyPI:** `pip install adbnik` installs the **wheel / sdist**. **Project links** include the Windows installer URL ([`pyproject.toml`](pyproject.toml) `[project.urls]`).
- **GitHub Releases:** **`Adbnik-1.0.0-Setup-unsigned.exe`** and **`Adbnik-1.0.0-Windows-portable-unsigned.zip`** when tag **`v1.0.0`** was pushed.

### Windows installer (unsigned)

The setup program is **not** Authenticode-signed. **SmartScreen** may warn — see [`README.md`](README.md).
