# Adbnik v1.3.6

## Fixes

- **Terminal (SSH / ADB):** Carriage returns and erase-line / erase-display sequences are turned into **spaces**, not extra newlines — fewer bogus blank lines while still avoiding glued text like `lsbin`.
- **Serial:** The UART/miniterm path no longer runs the SSH/ADB “normalize CR” step, so **serial logs are not inflated** with extra newlines.

**Full changelog:** [CHANGELOG.md — 1.3.6](https://github.com/nvnkennedy/adbnik/blob/main/CHANGELOG.md)
