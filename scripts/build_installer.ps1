# Build PyInstaller output, then compile the Inno Setup installer (requires Inno Setup 6).
# Usage (from repo root):
#   powershell -ExecutionPolicy Bypass -File scripts\build_installer.ps1
#
# Install Inno Setup from: https://jrsoftware.org/isdl.php

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

Write-Host "==> Installing package + PyInstaller..."
python -m pip install -q -e ".[build]"
Write-Host "==> Generating app icon (assets\adbnik.ico)..."
$env:QT_QPA_PLATFORM = "offscreen"
python "$Root\scripts\export_app_icon.py"
Write-Host "==> PyInstaller (dist\Adbnik)..."
python -m PyInstaller --noconfirm "$Root\adbnik.spec"

$DistApp = Join-Path $Root "dist\Adbnik\Adbnik.exe"
if (-not (Test-Path $DistApp)) {
    Write-Error "PyInstaller did not produce: $DistApp"
    exit 1
}

$IsccCandidates = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
)
$Iscc = $IsccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $Iscc) {
    Write-Error @"
Inno Setup 6 not found. Install from https://jrsoftware.org/isdl.php
Expected ISCC.exe at one of:
  $($IsccCandidates -join "`n  ")
"@
    exit 1
}

$Iss = Join-Path $Root "installer\adbnik.iss"
if (-not (Test-Path $Iss)) {
    Write-Error "Missing: $Iss"
    exit 1
}

Write-Host "==> Inno Setup: $Iscc"
& $Iscc $Iss
if ($LASTEXITCODE -ne 0) {
    Write-Error "ISCC failed with exit code $LASTEXITCODE"
    exit $LASTEXITCODE
}

$Out = Join-Path $Root "dist_installer"
$Msi = Get-ChildItem -Path $Out -Filter "Adbnik_Setup_*.exe" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($Msi) {
    Write-Host ""
    Write-Host "OK: $($Msi.FullName)"
} else {
    Write-Host "Check folder: $Out"
}
