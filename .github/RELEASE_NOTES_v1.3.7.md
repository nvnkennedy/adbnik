# Adbnik v1.3.7

## Fixes

- **Terminal (SSH / ADB):** Non-color ANSI sequences (especially **cursor movement**) are no longer deleted without a substitute — each becomes a **space** so text does not merge into strings like `lsbin` after the first command.
- **Terminal (SSH / ADB):** **Empty Enter** no longer adds an extra synthetic newline on top of what the shell echoes (serial behavior unchanged).

**Full changelog:** [CHANGELOG.md — 1.3.7](https://github.com/nvnkennedy/adbnik/blob/main/CHANGELOG.md)
