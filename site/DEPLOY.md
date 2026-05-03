# Website (GitHub Pages) for Adbnik

The marketing and install pages live in **`site/`**. The **`pages`** workflow (`.github/workflows/pages.yml`) copies **`site/`** into **`publish/`**, adds **`docs/guide/*.html`** → **`publish/guide/`** and **`docs/css/site.css`** → **`publish/css/`**, and deploys **`publish/`** to **GitHub Pages**.

## One-time setup on GitHub

1. Open **https://github.com/nvnkennedy/adbnik** → **Settings**.
2. **Pages** → **Build and deployment** → **Source** → **GitHub Actions**.
3. The **pages** workflow runs on push to **`main`** when **`site/`**, **`docs/guide/`**, or **`docs/css/`** change, or from **Actions → pages → Run workflow**.

The workflow file **`.github/workflows/pages.yml` must exist on the default branch (`main`)** of the public repository.

## URL

**https://nvnkennedy.github.io/adbnik/**

## Private repository note

Site sources are edited in **`adbnik-dev`** when applicable; the published site is built from the public **`adbnik`** `main` branch after changes are pushed there.

## Manual check

**Actions** → latest **pages** run → green check → open the deploy URL, or visit the site URL above.
