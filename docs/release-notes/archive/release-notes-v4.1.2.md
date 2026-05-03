# Adbnik 4.1.2

**Release date:** 2026-05-03

**Note:** **4.1.3** restores the user guide as part of the styled **GitHub Pages** site (`nvnkennedy.github.io/adbnik`); the blob-only navigation described below was reverted.

## Documentation (website behavior)

Static HTML under **`docs/guide/`** no longer uses **relative** links for navigation (`index.html`, `../index.html`, etc.). Those URLs were resolving on **`https://nvnkennedy.github.io/adbnik/guide/...`** when GitHub Pages served the `/docs` folder, instead of staying on the GitHub source viewer.

Every guide nav link, card, footer, and “next/previous” control now points at explicit **`https://github.com/nvnkennedy/adbnik/blob/main/docs/...`** URLs—the same style as **Help → User guide** in the app—so browsing Terminal / Explorer / Screen pages stays on **`github.com`**.

The **`docs/index.html`** logo/home link also targets the **`blob`** URL for **`docs/index.html`**.

## Install

```bash
py -m pip install --upgrade adbnik
```

Full history: [CHANGELOG.md](https://github.com/nvnkennedy/adbnik/blob/main/CHANGELOG.md).
