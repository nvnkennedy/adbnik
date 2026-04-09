# Build a standalone GUI folder: dist\DeviceDeck\DeviceDeck.exe
# Requires Python 3.9+ on PATH. Run from repo root:
#   powershell -ExecutionPolicy Bypass -File scripts\build_windows_exe.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

Write-Host "Installing package + PyInstaller (build extra)..."
python -m pip install -e ".[build]"

Write-Host "Generating app icon (assets\devicedeck.ico)..."
$env:QT_QPA_PLATFORM = "offscreen"
python "$Root\scripts\export_app_icon.py"

Write-Host "Running PyInstaller..."
python -m PyInstaller --noconfirm "$Root\DeviceDeck.spec"

$Exe = Join-Path $Root "dist\DeviceDeck\DeviceDeck.exe"
if (Test-Path $Exe) {
    Write-Host ""
    Write-Host "OK: $Exe"
    Write-Host "Zip the whole folder dist\DeviceDeck and ship it (adb/scrcpy stay separate tools on PATH or set in Preferences)."
} else {
    Write-Host "Build finished but exe not found at expected path."
    exit 1
}
