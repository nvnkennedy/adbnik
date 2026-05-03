# Website (GitHub Pages) for Adbnik

The marketing/install pages live in **`site/`** (HTML + `assets/`). The **`pages`** workflow (`.github/workflows/pages.yml`) **assembles** the published tree: it copies **`site/`** into **`publish/`**, then adds **`docs/guide/*.html`** → **`publish/guide/`** and **`docs/css/site.css`** → **`publish/css/`**, and uploads **`publish/`** to **GitHub Pages**. That way the **user guide** at **`/guide/`** is the same styled site as the home page (`nvnkennedy.github.io/adbnik`).

## One-time setup on GitHub

1. Open **`https://github.com/nvnkennedy/adbnik`** → **Settings**.
2. In the left sidebar, open **Pages** (under “Code and automation”).
3. Under **Build and deployment** → **Source**, choose **GitHub Actions** (not “Deploy from a branch” unless you intentionally use `gh-pages`).
4. Save. The workflow **pages** runs when you push changes under **`site/`**, **`docs/guide/`**, or **`docs/css/`** on **`main`** or **`naveen`**, or when you run it manually (**Actions** → **pages** → **Run workflow**).

**Important:** The workflow file **`.github/workflows/pages.yml` must exist on the default branch (`main`)**. If it lived only on another branch, GitHub Pages may never deploy the current `site/` (you would see **404** on paths like `/branding/favicon.ico` even though files exist in git).

## URL

After a successful run, the site is usually at:

**`https://nvnkennedy.github.io/adbnik/`**

(Replace with your username/repo if you fork.)

## Private repositories

GitHub **Free** accounts often only get **public** GitHub Pages. If the repo is **private** and Pages fails or is disabled, either:

- make the repo **public** for a free project site, **or**
- use a **paid** GitHub plan that includes Pages for private repos, **or**
- host the same static files elsewhere (any static host).

## Manual check

- **Actions** → latest **pages** run → green check → open the **deploy** step URL, or visit **`https://nvnkennedy.github.io/adbnik/`** directly.

## What is not in git

Windows **`.exe`** / **`.zip`** installers are **not** checked into `site/downloads/` (see `.gitignore`). Distribution for most users is **`pip install adbnik`** on PyPI.
