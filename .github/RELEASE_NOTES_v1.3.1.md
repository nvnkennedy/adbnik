# Adbnik v1.3.1

## Fix

- **Terminal startup:** Bookmarks were refreshed before the session tab widget existed, which could raise `AttributeError` (`'TerminalTab' object has no attribute 'tabs'`). Initialization order is corrected; a small guard avoids recurrence.

**Full changelog:** [CHANGELOG.md — 1.3.1](https://github.com/nvnkennedy/adbnik/blob/main/CHANGELOG.md)
