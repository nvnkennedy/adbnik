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

## 6) Create GitHub release

- Title: `DeviceDeck v<version>`
- Notes: copy from `CHANGELOG.md`
- Upload both binaries from the downloads folder.

## 7) Update website release links

- Update `site/config.js` if needed.
- Ensure download URLs point to latest GitHub release assets.
