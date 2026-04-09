# Contributing to DeviceDeck

Thanks for helping improve DeviceDeck.

## Local setup

```powershell
pip install -e ".[dev]"
python -m pytest tests -q
```

## Branching and commits

- Use feature branches from `main`.
- Keep commits focused and small.
- Use clear commit messages (`fix:`, `feat:`, `docs:` recommended).

## Release-safe checklist for PRs

- Tests pass locally.
- No generated artifacts committed (`dist/`, `build/`, binaries).
- Docs updated when behavior changes.
- Windows behavior validated for packaging-sensitive changes.

## Reporting bugs

Open a GitHub issue and include:
- app version (`devicedeck.__version__`)
- OS version
- steps to reproduce
- expected vs actual behavior
- logs/screenshots if available
