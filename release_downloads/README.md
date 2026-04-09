# DeviceDeck Downloads Folder

This folder is for **end-user binaries only** (no source code).

## Files

- `DeviceDeck_Setup_0.1.0.exe`  
  Recommended for normal users. Installer adds Start menu entry and uninstaller.

- `DeviceDeck_Portable_0.1.0.zip`  
  Portable build. Extract and run `DeviceDeck.exe` inside the extracted folder.

## Why this is separate from source

- `device_deck_release/` is your **source repository** for GitHub maintenance.
- `device_deck_release_downloads/` is your **release output** for sharing with users.

Keeping binaries outside source avoids repository bloat and keeps git history clean.

## Publishing workflow

1. Maintain code in `device_deck_release/`.
2. Build new release artifacts.
3. Replace files in this folder with the new version.
4. Upload these files to GitHub Releases.
