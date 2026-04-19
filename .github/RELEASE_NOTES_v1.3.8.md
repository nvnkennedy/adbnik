# Adbnik v1.3.8

## Fixes

- **Terminal (SSH / ADB):** Lone carriage returns from the PTY are turned into **newlines** again. Mapping them to spaces (v1.3.6) had glued prompts and command output onto a single wrapped line (e.g. multiple `#` on one row) and made the session look like it alternated between normal layout and “stuck” layout.

**Full changelog:** [CHANGELOG.md — 1.3.8](https://github.com/nvnkennedy/adbnik/blob/main/CHANGELOG.md)
