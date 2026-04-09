# Publish Source Repository

Use this once to set up the canonical GitHub source repo.

1. Edit `scripts/publish_source_repo.ps1` parameter value or pass `-RepoUrl`.
2. Run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/publish_source_repo.ps1 -RepoUrl "https://github.com/YOUR_USER/YOUR_REPO.git"
```

This script initializes git if needed, sets `main`, configures `origin`, and pushes source.

Note: GitHub CLI (`gh`) is not required for this script.
