# Website (GitHub Pages) for Adbnik

The marketing and install pages live in **`site/`**. The **`pages`** workflow (`.github/workflows/pages.yml`) copies **`site/`** into **`publish/`**, adds **`docs/guide/*.html`** → **`publish/guide/`** and **`docs/css/site.css`** → **`publish/css/`**, and deploys **`publish/`** to **GitHub Pages**.

## One-time setup on GitHub

1. Open **https://github.com/nvnkennedy/adbnik** → **Settings**.
2. **Pages** → **Build and deployment** → **Source** → **GitHub Actions**.
3. The **pages** workflow runs on push to **`main`** when **`site/`**, **`docs/guide/`**, or **`docs/css/`** change, or from **Actions → pages → Run workflow**.

The workflow file **`.github/workflows/pages.yml` must exist on the default branch (`main`)** of the public repository.

## URL

**https://nvnkennedy.github.io/adbnik/**

## Private repository (`adbnik-dev`)

If the **pages** workflow fails at **`actions/configure-pages`** with **Get Pages site failed** / **Not Found**, GitHub has no Pages site record for that repository yet.

1. Open **`https://github.com/<owner>/<repo>`** (for example your private dev repo) → **Settings** → **Pages**.
2. Under **Build and deployment**, set **Source** to **GitHub Actions** (not “Deploy from a branch”) and save.
3. Re-run the failed workflow (**Actions** → **pages** → **Re-run all jobs**).

Until that one-time step is done, the Pages API returns 404 and `configure-pages@v5` cannot proceed. The optional `enablement: true` input on that action requires a **personal access token** with repo/Pages scope, not the default `GITHUB_TOKEN`, so enabling Pages in the UI is the usual fix.

When you also publish from the public **`adbnik`** repo, repeat **Settings → Pages → GitHub Actions** there if you deploy Pages from that repository.

Site sources are often edited in **`adbnik-dev`**; you can publish from either repo depending on which remote’s **main** runs the workflow.

## Manual check

**Actions** → latest **pages** run → green check → open the deploy URL, or visit the site URL above.
