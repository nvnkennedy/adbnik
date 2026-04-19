# Adbnik v1.3.5

## Fixes

- **Terminal (SSH / ADB):** ANSI **erase-line** and **erase-display** codes are no longer dropped without a substitute; they become a line break before the rest of the stream is stripped. That stops the **second and later commands** from gluing into the next output (e.g. `lsbin`) after plain-text CSI stripping.

**Full changelog:** [CHANGELOG.md — 1.3.5](https://github.com/nvnkennedy/adbnik/blob/main/CHANGELOG.md)
