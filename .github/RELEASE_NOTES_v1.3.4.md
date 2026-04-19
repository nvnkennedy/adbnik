# Adbnik v1.3.4

## Fixes

- **Terminal:** Remote PTY output again treats **carriage return as a line break** for plain-text display (with a cap on huge blank-line runs), so prompts and listings are not glued to prior text and lone `#` lines are not produced by bogus “overwrite” handling.
- **Explorer:** **SFTP/FTP** pull completed via **drag-and-drop** shows the same **Pull complete** dialog as the **Pull** button (path + **Open**), with the same follow-up behavior for opening a single file.

**Full changelog:** [CHANGELOG.md — 1.3.4](https://github.com/nvnkennedy/adbnik/blob/main/CHANGELOG.md)
