# Adbnik v1.3.9

## Fixes

- **Terminal (SSH / ADB):** Inserts a **newline** when the PTY **glues** the next prompt or the next line of output to the previous line (no ``\\n`` in the byte stream). Fixes prompts stuck to the end of ``ls`` output and ``# ls`` + ``bin`` style merging.
- **Commands → SSH:** Quick commands go to a **running SSH session tab** only (preferring the current tab when it is SSH), not the active terminal tab when that tab is ADB or another shell.

**Full changelog:** [CHANGELOG.md — 1.3.9](https://github.com/nvnkennedy/adbnik/blob/main/CHANGELOG.md)
