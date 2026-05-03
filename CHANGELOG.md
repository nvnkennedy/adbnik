# Adbnik Changelog

All notable changes to this project are documented in this file.

**Versioning:** [Semantic Versioning](https://semver.org/spec/v2.0.0.html) — **`6.0.x`** patch releases for **bugfixes**, **`6.y.0`** minor releases for **new features** (unless policy changes).

**Git baseline:** This branch’s history starts at **6.0.0** as the first **stable** line. Older PyPI / pre-6 narrative material lives in [`CHANGELOG-legacy.md`](CHANGELOG-legacy.md).

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [6.0.0] - 2026-05-03

### Initial stable release

This tree is the **6.0.0** stable baseline: application source, docs, marketing site (`site/` + `docs/guide/`), packaging, and Windows artifacts under **`installers/`**, aligned with **`adbnik==6.0.0`** on **PyPI** and Git tag **`v6.0.0`**.

### Distribution

- **PyPI:** `pip install adbnik==6.0.0` — wheel and sdist. Details: [`docs/release-notes-v6.0.0.md`](docs/release-notes-v6.0.0.md).
- **GitHub Releases:** tag **`v6.0.0`** — **`Adbnik-6.0.0-Setup-unsigned.exe`**, **`Adbnik-6.0.0-Windows-portable-unsigned.zip`**. See [`installers/README.md`](installers/README.md).

### Windows installer (unsigned)

Binaries are **not** Authenticode-signed. **SmartScreen** may warn — use **More info → Run anyway**; see [`README.md`](README.md) and [`packaging/windows/INSTALLER_NOTICE.txt`](packaging/windows/INSTALLER_NOTICE.txt).

---

## [Unreleased]

*(Add **6.0.1** / **6.1.0** sections here as you ship fixes and features.)*
