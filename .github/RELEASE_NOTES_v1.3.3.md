# Adbnik v1.3.3

## Fixes

- **Terminal:** SSH/ADB/serial streams treat **bare CR** as *move to start of line* (overwrite), not as an extra newline every time — fewer blank lines, no more glued tokens like `lsbin`, and cursor-movement spacing is preserved more naturally than with naive `\r` → `\n` mapping.
- **Explorer:** After **SFTP/FTP** pull (including **drag-and-drop**), **Open** runs reliably because the completion handler no longer relies on `sender()` from a background thread; pulled **folders** can open in the file manager.

**Full changelog:** [CHANGELOG.md — 1.3.3](https://github.com/nvnkennedy/adbnik/blob/main/CHANGELOG.md)
