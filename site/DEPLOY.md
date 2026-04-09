# Publishing the website so downloads work

Downloads are served **from this repo’s GitHub Pages** (`site/downloads/`), not from the GitHub Releases page. Follow these steps whenever you change binaries or site content.

## One-time setup (GitHub)

1. Open the repo on GitHub → **Settings** → **Pages**.
2. Under **Build and deployment**, set **Source** to **GitHub Actions** (not “Deploy from a branch” unless you know you need that older model).
3. The workflow `.github/workflows/pages.yml` deploys the entire **`site/`** folder whenever you push changes under `site/**` to **`main`** or **`master`**.

## Every time you ship new installers

1. Build `DeviceDeck_Setup_<version>.exe` and `DeviceDeck_Portable_<version>.zip` (see `RELEASE_CHECKLIST.md` in the repo root).
2. Copy both files into **`site/downloads/`** in this repository.
3. Edit **`site/config.js`**: set `setupUrl`, `portableUrl`, and `currentVersion` to match the filenames (paths are relative to the site root, e.g. `downloads/DeviceDeck_Setup_0.1.0.exe`).
4. Commit and push from your local clone (use your real branch name, often `master`):

```powershell
cd E:\Naveen_Python_coding\projects\Device_Deck_repo
git add site/
git status
git commit -m "site: publish v0.1.0 downloads"
git push origin master
```

5. On GitHub → **Actions**, open the **pages** workflow and wait until it finishes successfully (green check).
6. Test the live site (replace `nvnkennedy` / `Device_Deck` if your user or repo name differs):

   - `https://nvnkennedy.github.io/Device_Deck/download.html`
   - Click **Download .exe installer** and **Download .zip** — the file should save immediately, not open an empty Releases page.

## Checks if something fails

- **404 on download:** Confirm the files are tracked: `git ls-files site/downloads`. Large binaries must be committed; the Pages workflow only uploads what is in the repo.
- **Workflow did not run:** Ensure you pushed changes under `site/` (or edited `.github/workflows/pages.yml`). Pushing only code outside `site/` does not redeploy the site.
- **File too large for Git:** GitHub blocks files larger than **100 MB**. Keep each installer under that limit.
- **Authentication:** Use HTTPS with a Personal Access Token, or SSH keys, when `git push` asks for credentials.

## Enterprise trust (SmartScreen / company policy)

Unsigned `.exe` files are **often blocked** in production. For workplace distribution, **sign** builds using **`docs/WINDOWS_CODE_SIGNING.md`**, then set `authenticodeSigned: true` in `site/config.js` and publish the signed files. The website cannot remove SmartScreen; signing can.

## Optional: GitHub Releases

You can still create a **Release** on GitHub and attach the same `.exe` / `.zip` for users who prefer that. The website does **not** depend on Releases as long as `site/downloads/` is populated and deployed.
