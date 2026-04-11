# Release Runbook

Primary distribution: **PyPI** (`pip install adbsshdeck`). This repository stays **source-only** (no checked-in `.exe` / `.zip`).

## 1) Prepare version

Update:

- `pyproject.toml` (`version`)
- `devicedeck/__init__.py` (`__version__`)

Add release notes in `CHANGELOG.md`.

## 2) Validate source

```powershell
python -m pytest tests -q
```

## 3) Build and publish to PyPI

```powershell
pip install build twine
python -m build
python -m twine upload dist/*
```

Or use **GitHub Actions → Publish to PyPI** after setting the `PYPI_API_TOKEN` secret. Details: **`docs/PYPI_PUBLISH.md`**.

## 4) Tag and push (optional but recommended)

```powershell
git add .
git commit -m "release: v<version>"
git tag v<version>
git push origin master --tags
```

## 5) Optional: GitHub Release

Create a **Release** on GitHub with notes from `CHANGELOG.md`. You may attach **optional** PyInstaller artifacts built **outside** this repo (not required for pip users).

## 6) Optional: Windows executable (maintainers, outside git)

If you need a standalone `.exe` for people without Python:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_windows_exe.ps1
```

Do **not** commit outputs. Optional signing: **`docs/WINDOWS_CODE_SIGNING.md`**, **`docs/SIGNPATH_SETUP.md`**.

## 7) Website

The Pages site (`site/`) points users to **pip** and **PyPI**. Push `site/` if you changed copy.

See **`site/DEPLOY.md`**.
