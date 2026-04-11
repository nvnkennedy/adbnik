# Publish Adbnik to PyPI

End users install with **`pip install adbnik`**. This document is for **maintainers** who upload new releases.

**PyPI project name:** `adbnik` (the Python **import** package is also `adbnik`).

## One-time: PyPI account

1. Create an account on [pypi.org](https://pypi.org) (and [test.pypi.org](https://test.pypi.org) if you want a dry run).
2. Enable **2FA** on your account (required for uploads).
3. Under **Account settings → API tokens**, create a token scoped to the **adbnik** project (or whole account for first upload).

## One-time: GitHub Actions secret (optional automation)

Repository → **Settings → Secrets and variables → Actions** → **New repository secret**

- Name: `PYPI_API_TOKEN`  
- Value: your PyPI API token

Used by `.github/workflows/publish-pypi.yml` when you run it manually or on release.

## Every release

1. Bump version in **`pyproject.toml`** and **`adbnik/__init__.py`** (`__version__`).
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

5. Confirm: [pypi.org/project/adbnik](https://pypi.org/project/adbnik/)

## TestPyPI (optional)

```bash
python -m twine upload --repository testpypi dist/*
```

Install from TestPyPI:

```bash
pip install --index-url https://test.pypi.org/simple/ adbnik
```

## Website

After publishing, users get the new version with `pip install -U adbnik`. The GitHub Pages site (`site/install.html`) does not need a version bump in HTML — it points to PyPI generically.

## Retiring old PyPI projects

PyPI does not delete projects. **Yank** old releases on deprecated package names and point users to **`adbnik`** in the project description.

## Upload errors (troubleshooting)

**`400 File already exists` / `duplicate`**

- PyPI never allows reusing the same **version** string. Bump **`version`** in **`pyproject.toml`** and **`adbnik/__init__.py`**, rebuild, upload again.

**`403 Forbidden` / `invalid credentials`**

- Use an **API token**, not your password (2FA is required on PyPI).
- **Username** must be **`__token__`** when using a token.
- **Password** is the token string (often starts with `pypi-`).
- Token must be scoped to the **`adbnik`** project or the whole account.

**`InvalidDistribution` / `license-expression` / metadata errors**

- Upgrade tools: `pip install -U twine build`
- Keep **`setuptools>=61,<77`** in `[build-system]` (this repo already caps it).
- Run **`python -m twine check dist/*`** before upload; fix anything it reports.

**Upload only the new files**

- Delete **`dist/`** before each build so old wheels are not uploaded by mistake:

  ```bash
  rm -rf dist   # Linux/macOS
  rmdir /s /q dist   # Windows cmd
  ```

**Windows path tip**

- From repo root: `python -m build` then `python -m twine check dist\*` and `python -m twine upload dist\*`.
