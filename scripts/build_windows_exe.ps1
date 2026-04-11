# Build a standalone GUI folder: dist\Adbnik\Adbnik.exe
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Resolve-Path (Join-Path $Root "..")

Set-Location $Root
# Headless Windows / CI: Qt needs an offscreen platform for icon export
$env:QT_QPA_PLATFORM = "offscreen"
Write-Host "Generating app icon (assets\adbnik.ico)..."
python scripts/export_app_icon.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "PyInstaller (dist\Adbnik)..."
python -m PyInstaller --noconfirm "$Root\adbnik.spec"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$Exe = Join-Path $Root "dist\Adbnik\Adbnik.exe"
if (Test-Path $Exe) {
    Write-Host "OK: $Exe"
} else {
    Write-Error "Expected exe not found: $Exe"
    exit 1
}
Write-Host "Zip the whole folder dist\Adbnik and ship it (adb/scrcpy stay separate tools on PATH or set in Preferences)."
