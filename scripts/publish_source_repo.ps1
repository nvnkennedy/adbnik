# Publish Adbnik source repo (helper script)

This script initializes and publishes the source repository.
# Update variables below once.

param(
    [string]$RepoUrl = "https://github.com/nvnkennedy/adbnik.git"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

if (-not (Test-Path ".git")) {
    git init
}

git add .
if ((git diff --cached --name-only).Count -gt 0) {
    git commit --trailer "Made-with: Cursor" -m "chore: initialize Adbnik production repo"
}

git branch -M main

$hasOrigin = git remote | Select-String -SimpleMatch "origin"
if (-not $hasOrigin) {
    git remote add origin $RepoUrl
} else {
    git remote set-url origin $RepoUrl
}

git push -u origin main
Write-Host "Published source repo to $RepoUrl"
