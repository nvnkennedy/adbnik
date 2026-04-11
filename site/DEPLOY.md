# Publishing the GitHub Pages site

The site under `site/` explains **pip install adbsshdeck** and links to **PyPI**. It does **not** host Windows `.exe` installers in the repository.

## One-time setup (GitHub)

1. Repository → **Settings** → **Pages**.
2. **Build and deployment** → Source: **GitHub Actions**.
3. Workflow: `.github/workflows/pages.yml` deploys when you push changes under `site/**` to **`main`** or **`master`**.

## When you change the website

```powershell
cd E:\Naveen_Python_coding\projects\Device_Deck_repo
git add site/
git commit -m "site: update copy"
git push origin master
```

Wait for the **pages** workflow to finish, then open:

`https://nvnkennedy.github.io/Device_Deck/`

## PyPI releases

Publishing the Python package is separate — see **`docs/PYPI_PUBLISH.md`**.
