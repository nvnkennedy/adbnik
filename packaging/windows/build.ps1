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

# Portable zip (unsigned) for users who do not want an installer
$ver = (py -c "import tomllib, pathlib; print(tomllib.loads(pathlib.Path('pyproject.toml').read_text(encoding='utf-8'))['project']['version'])")
$zipName = "Adbnik-$ver-Windows-portable-unsigned.zip"
$zipPath = Join-Path $Root "dist_installer\$zipName"
New-Item -ItemType Directory -Force -Path (Split-Path $zipPath) | Out-Null
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
Compress-Archive -Path (Join-Path $Root "dist\Adbnik\*") -DestinationPath $zipPath
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
Write-Host "Done. See dist_installer\ for Adbnik-$ver-Setup-unsigned.exe"
