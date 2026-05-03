# Build Windows onedir (PyInstaller) and optional Inno Setup installer.
# Run from repository root:  powershell -ExecutionPolicy Bypass -File packaging\windows\build.ps1
# Requires: Python 3.9+, optional Inno Setup 6 (ISCC.exe) for the .exe setup.

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $Root

Write-Host "Project root: $Root"

py -m pip install -U pip
py -m pip install ".[build]"

py -m PyInstaller (Join-Path $Root "packaging\windows\adbnik.spec") --noconfirm

if (-not (Test-Path (Join-Path $Root "dist\Adbnik\Adbnik.exe"))) {
    throw "PyInstaller did not produce dist\Adbnik\Adbnik.exe"
}

# PyInstaller/AV may still hold DLLs briefly; wait before reading dist for zip.
Start-Sleep -Seconds 3

$ver = (py (Join-Path $Root "packaging\windows\read_project_version.py")).Trim()
if (-not $ver) { throw "Could not read version from pyproject.toml" }

$zipName = "Adbnik-$ver-Windows-portable-unsigned.zip"
$zipPath = Join-Path $Root "installers\$zipName"
New-Item -ItemType Directory -Force -Path (Join-Path $Root "installers") | Out-Null
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }

# Zip a staging copy so Compress-Archive does not race scanners locking files under dist\Adbnik.
$stage = Join-Path $Root "installers\_zip_stage"
if (Test-Path $stage) {
    Remove-Item $stage -Recurse -Force -ErrorAction SilentlyContinue
}
New-Item -ItemType Directory -Path $stage | Out-Null
Copy-Item -Path (Join-Path $Root "dist\Adbnik\*") -Destination $stage -Recurse -Force

$zipOk = $false
for ($attempt = 1; $attempt -le 5; $attempt++) {
    try {
        if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
        Compress-Archive -Path (Join-Path $stage "*") -DestinationPath $zipPath -Force -ErrorAction Stop
        $zipOk = $true
        break
    } catch {
        Write-Warning "Portable zip attempt $attempt failed: $_"
        Start-Sleep -Seconds ($attempt + 2)
    }
}
Remove-Item $stage -Recurse -Force -ErrorAction SilentlyContinue

if (-not $zipOk) {
    throw "Could not create portable zip after retries. Close Adbnik/explorer windows touching dist\Adbnik or retry."
}
Write-Host "Wrote portable: $zipPath"

$iscc = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
    "${env:ProgramFiles}\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $iscc) {
    Write-Warning "Inno Setup 6 (ISCC.exe) not found. Skipping .exe installer. Install from https://jrsoftware.org/isinfo.php or: choco install innosetup -y"
    exit 0
}

& $iscc "/DMyAppVersion=$ver" (Join-Path $Root "packaging\windows\adbnik.iss")
Write-Host "Done. See installers\ at repo root: Adbnik-$ver-Setup-unsigned.exe and $zipName"
