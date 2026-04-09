# Release Runbook

Use this document for every production release.

## 1) Prepare version

Update both files:
- `pyproject.toml`
- `devicedeck/__init__.py`

Then add release notes entry in `CHANGELOG.md`.

## 2) Validate source

```powershell
python -m pytest tests -q
```

## 3) Build Windows binary folder

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_windows_exe.ps1
```

Artifacts are generated in `dist/DeviceDeck/`.

## 4) Create release assets outside source repo

Recommended output folder (outside repo):
- `E:\Naveen_Python_coding\projects\device_deck_release_downloads`

Create:
- `DeviceDeck_Setup_<version>.exe` (installer)
- `DeviceDeck_Portable_<version>.zip` (portable bundle)

## 5) Publish source changes

```powershell
git add .
git commit --trailer "Made-with: Cursor" -m "release: v<version>"
git tag v<version>
git push origin main --tags
```

## 6) Code signing (strongly recommended; free for OSS)

Unsigned Windows executables are **commonly blocked** by SmartScreen and enterprise policy. **You do not have to buy a certificate:** qualifying open-source projects can use **[SignPath Foundation](https://signpath.org/)** (see **`docs/WINDOWS_CODE_SIGNING.md`**). If you use your own `.pfx`, sign with `scripts/sign_windows_artifacts.ps1`.

Set `authenticodeSigned: true` in `site/config.js` **only** when the published files are actually signed.

## 7) Copy binaries into the website (required for one-click download page)

Copy the **signed** (or unsigned preview) installer and portable ZIP into the source repo:

- `site/downloads/DeviceDeck_Setup_<version>.exe`
- `site/downloads/DeviceDeck_Portable_<version>.zip`

Update `site/config.js` (`setupUrl`, `portableUrl`, `currentVersion`) so filenames match.

Run `scripts/compute_release_hashes.ps1` and add `sha256Setup` / `sha256Portable` so IT teams can verify integrity.

Push `site/` so GitHub Pages deploys them. See **`site/DEPLOY.md`** for the exact git push and GitHub Actions checks.

## 8) Optional: GitHub Release

- Title: `DeviceDeck v<version>`
- Notes: copy from `CHANGELOG.md`
- Upload both binaries (same files as above) for users who browse Releases.

This is optional for the marketing site: **downloads on the website are served from `site/downloads/` via Pages**, not from the Releases URL.