# Copies distribution paths from branch naveen onto the current branch (expected: main).
# Run AFTER removing non-distribution paths from main if you use a slim snapshot.
# Requires: clean working tree, git, branch naveen exists locally.
$ErrorActionPreference = "Stop"
$src = "naveen"
$paths = @(
    "README.md", "LICENSE", "NOTICE", "CHANGELOG.md", "CHANGELOG-legacy.md",
    "site", "branding", "installers",
    "docs/guide", "docs/css", "docs/screenshots",
    "docs/release-notes-v1.0.0.md", "docs/release-notes-v6.0.0.md",
    "docs/release-notes-v6.1.1.md", "docs/release-notes-v6.1.2.md", "docs/release-notes-v6.1.3.md",
    ".github/workflows/pages.yml"
)
foreach ($p in $paths) {
    if (-not (git rev-parse --verify -q "${src}:$p")) {
        Write-Warning "Skip missing on ${src}: $p"
        continue
    }
    git checkout $src -- $p
    Write-Host "Updated $p from $src"
}
Write-Host "Done. Review git status then commit."
