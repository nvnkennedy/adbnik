# Screenshots (GitHub + PyPI)

PNG files in this folder are referenced from:

- **README.md** (GitHub project home **and** PyPI project description) using  
  `https://raw.githubusercontent.com/nvnkennedy/adbnik/main/docs/screenshots/<file>.png`
- **`site/index.html`** (GitHub Pages) using the same URLs so images stay in sync.

## Filenames

| File | Suggested content |
|------|-------------------|
| `01-main-window.png` | Full window: tabs + log panel (Terminal selected). |
| `02-terminal.png` | ADB or SSH session tab in use. |
| `03-file-explorer.png` | File Explorer / device storage view. |
| `04-screen-control.png` | Screen Control tab or mirroring session. |

**Do not** save the app icon (`branding/adbnik-256.png`) under these names—they are for **window screenshots** only, and duplicating the logo looks like fake UI shots on GitHub and PyPI.

## README / PyPI gallery (after real PNGs are on `main`)

When the four PNGs exist on the default branch, paste this block into **`README.md`** in place of the plain Screenshots section (PyPI requires **absolute** URLs):

```html
## Screenshots

<p align="center">
  <b>Main window</b><br />
  <img src="https://raw.githubusercontent.com/nvnkennedy/adbnik/main/docs/screenshots/01-main-window.png" width="720" alt="Adbnik main window" /><br /><br />
  <b>Terminal</b><br />
  <img src="https://raw.githubusercontent.com/nvnkennedy/adbnik/main/docs/screenshots/02-terminal.png" width="720" alt="Adbnik terminal tab" /><br /><br />
  <b>File Explorer</b><br />
  <img src="https://raw.githubusercontent.com/nvnkennedy/adbnik/main/docs/screenshots/03-file-explorer.png" width="720" alt="Adbnik file explorer" /><br /><br />
  <b>Screen Control</b><br />
  <img src="https://raw.githubusercontent.com/nvnkennedy/adbnik/main/docs/screenshots/04-screen-control.png" width="720" alt="Adbnik screen control" />
</p>
```

For **`site/index.html`**, you can wrap the same four URLs in `<figure class="shot">` / `<img ...>` inside `<div class="screenshot-grid">` (see git history) so GitHub Pages matches the README.

## How to capture (Windows)

1. Run Adbnik, arrange the UI, **Win + Shift + S** (or Snipping Tool).
2. Save as **PNG** with the exact names above (one distinct capture per filename).
3. Commit and push to **`main`**:

   ```bat
   git add docs/screenshots/*.png
   git commit -m "docs: refresh UI screenshots"
   git push origin main
   ```

4. PyPI picks up images on the **next** release that includes the updated PNGs in the repo (README renders from the published package metadata + raw GitHub URLs).

**Privacy:** crop or blur serial numbers, IPs, hostnames, and sensitive log lines.
