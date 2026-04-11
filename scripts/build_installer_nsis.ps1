# Build PyInstaller output, then compile the NSIS installer (requires NSIS 3).
# Usage (from repo root):
#   powershell -ExecutionPolicy Bypass -File scripts\build_installer_nsis.ps1
#
# Install NSIS: https://nsis.sourceforge.io/Download

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

$MakensisCandidates = @(
    "$env:ProgramFiles\NSIS\makensis.exe",
    "${env:ProgramFiles(x86)}\NSIS\makensis.exe"
)
$Makensis = $MakensisCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $Makensis) {
    Write-Error @"
NSIS (makensis) not found. Install from https://nsis.sourceforge.io/Download
Expected at one of:
  $($MakensisCandidates -join "`n  ")
"@
    exit 1
}

$Nsi = Join-Path $Root "installer\adbnik.nsi"
if (-not (Test-Path $Nsi)) {
    Write-Error "Missing: $Nsi"
    exit 1
}

New-Item -ItemType Directory -Force -Path (Join-Path $Root "dist_installer") | Out-Null

Write-Host "==> NSIS: $Makensis"
Push-Location (Join-Path $Root "installer")
try {
    & $Makensis (Split-Path -Leaf $Nsi)
} finally {
    Pop-Location
}
if ($LASTEXITCODE -ne 0) {
    Write-Error "makensis failed with exit code $LASTEXITCODE"
    exit $LASTEXITCODE
}

$Out = Join-Path $Root "dist_installer"
$Exe = Get-ChildItem -Path $Out -Filter "Adbnik_Setup_*_nsis.exe" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($Exe) {
    Write-Host ""
    Write-Host "OK: $($Exe.FullName)"
} else {
    Write-Host "Check folder: $Out"
}
