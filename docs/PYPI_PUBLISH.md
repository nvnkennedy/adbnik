# Publish DeviceDeck to PyPI

End users install with **`pip install adbsshdeck`**. This document is for **maintainers** who upload new releases.

**PyPI project name:** `adbsshdeck` (the Python **import** package remains `devicedeck`).

## One-time: PyPI account

1. Create an account on [pypi.org](https://pypi.org) (and [test.pypi.org](https://test.pypi.org) if you want a dry run).
2. Enable **2FA** on your account (required for uploads).
3. Under **Account settings → API tokens**, create a token scoped to the **adbsshdeck** project (or whole account for first upload).

## One-time: GitHub Actions secret (optional automation)

Repository → **Settings → Secrets and variables → Actions** → **New repository secret**

- Name: `PYPI_API_TOKEN`  
- Value: your PyPI API token

Used by `.github/workflows/publish-pypi.yml` when you run it manually or on release.

## Every release

1. Bump version in **`pyproject.toml`** and **`devicedeck/__init__.py`** (`__version__`).
2. Update **`CHANGELOG.md`** if you maintain one.
3. Build:

   ```bash
   pip install build
   python -m build
   ```

4. Upload **manually** (use a **current** Twine, e.g. `pip install -U twine`, to avoid metadata errors):

   ```bash
   pip install -U twine build
   python -m twine check dist/*
   python -m twine upload dist/*
   ```

   If you see `InvalidDistribution ... license-expression` / `license-file`, either **upgrade Twine** (5.1+) or rebuild with the repo’s pinned setuptools (`setuptools<77` in `pyproject.toml`).

   Or trigger **Actions → Publish to PyPI** workflow (after `PYPI_API_TOKEN` is set).

5. Confirm: [pypi.org/project/adbsshdeck](https://pypi.org/project/adbsshdeck/)

## TestPyPI (optional)

```bash
python -m twine upload --repository testpypi dist/*
```

Install from TestPyPI:

```bash
pip install --index-url https://test.pypi.org/simple/ adbsshdeck
```

## Website

After publishing, users get the new version with `pip install -U adbsshdeck`. The GitHub Pages site (`site/install.html`) does not need a version bump in HTML — it points to PyPI generically.
