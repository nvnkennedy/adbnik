# Adbnik Changelog

All notable changes are documented here.

**Public versioning** starts at **`1.0.0`**. Earlier development releases (**2.x–5.x** on PyPI) are summarized in [`CHANGELOG-legacy.md`](CHANGELOG-legacy.md) only.

The format follows Keep a Changelog and Semantic Versioning.

## [1.0.0] - 2026-05-03

### Summary

First **public** release under **`1.0.0`** numbering.

### License

- **Apache License 2.0** ([`LICENSE`](LICENSE), SPDX **`Apache-2.0`**) with [`NOTICE`](NOTICE) — permissive, enterprise-friendly terms including an explicit patent grant.

### Distribution

- **PyPI:** `pip install adbnik` installs the **wheel / sdist** (Python package). PyPI does not host the Windows `.exe` inside the wheel (cross-platform packages stay small); the PyPI project page lists a **Windows installer** link under **Project links** ([`pyproject.toml`](pyproject.toml) `[project.urls]`).
- **GitHub Releases:** CI attaches **`Adbnik-1.0.0-Setup-unsigned.exe`** (Inno Setup) and **`Adbnik-1.0.0-Windows-portable-unsigned.zip`** when you push tag **`v1.0.0`** ([`windows-installer`](.github/workflows/windows-installer.yml) workflow).

### Windows installer (unsigned)

The setup program is **not** Authenticode-signed. **Microsoft SmartScreen** may warn (“Unknown publisher”). That reflects **missing code signing**, not an antivirus malware verdict. Use **More info → Run anyway**; see [`README.md`](README.md) and [`packaging/windows/INSTALLER_NOTICE.txt`](packaging/windows/INSTALLER_NOTICE.txt).
