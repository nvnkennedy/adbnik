# Sign Adbnik.exe and the Inno Setup output with Authenticode (after building).
# Requires: Windows SDK signtool, a .pfx code-signing certificate.
# Usage (repo root):
#   powershell -ExecutionPolicy Bypass -File scripts\sign_windows_artifacts.ps1 -PfxPath C:\path\cert.pfx
# Optional env: ADBNIK_PFX, ADBNIK_PFX_PASSWORD (plain text — prefer interactive -PfxPassword in CI secrets)

param(
    [string] $PfxPath = $env:ADBNIK_PFX,
    [SecureString] $PfxPassword,
    [string] $TimestampUrl = "http://timestamp.digicert.com",
    [string] $Root = ""
)

$ErrorActionPreference = "Stop"

if (-not $Root) {
    $Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
}
Set-Location $Root

function Find-SignTool {
    $kits = "C:\Program Files (x86)\Windows Kits\10\bin"
    if (-not (Test-Path $kits)) {
        return $null
    }
    $signtool = Get-ChildItem -Path $kits -Recurse -Filter "signtool.exe" -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -match "\\x64\\signtool\.exe$" } |
        Sort-Object FullName -Descending |
        Select-Object -First 1
    if ($signtool) {
        return $signtool.FullName
    }
    return $null
}

$SignTool = Find-SignTool
if (-not $SignTool) {
    Write-Error "signtool.exe not found. Install the Windows SDK or Visual Studio Build Tools with Windows SDK."
}

if (-not $PfxPath -or -not (Test-Path -LiteralPath $PfxPath)) {
    Write-Error "Provide -PfxPath to your .pfx or set ADBNIK_PFX."
}

if (-not $PfxPassword) {
    if ($env:ADBNIK_PFX_PASSWORD) {
        $PfxPassword = ConvertTo-SecureString $env:ADBNIK_PFX_PASSWORD -AsPlainText -Force
    } else {
        $PfxPassword = Read-Host "PFX password" -AsSecureString
    }
}

$Bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($PfxPassword)
try {
    $Plain = [Runtime.InteropServices.Marshal]::PtrToStringAuto($Bstr)
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($Bstr)
}

$SignArgs = @(
    "sign", "/fd", "sha256",
    "/tr", $TimestampUrl, "/td", "sha256",
    "/f", $PfxPath,
    "/p", $Plain
)

$Exe = Join-Path $Root "dist\Adbnik\Adbnik.exe"
if (Test-Path $Exe) {
    Write-Host "Signing: $Exe"
    & $SignTool @SignArgs $Exe
} else {
    Write-Warning "Skip: not found: $Exe"
}

$Installer = Get-ChildItem -Path (Join-Path $Root "dist_installer") -Filter "Adbnik_Setup_*.exe" -ErrorAction SilentlyContinue |
    Select-Object -First 1
if ($Installer) {
    Write-Host "Signing: $($Installer.FullName)"
    & $SignTool @SignArgs $Installer.FullName
} else {
    Write-Warning "Skip: no Adbnik_Setup_*.exe under dist_installer\"
}

Write-Host "Done. Rebuild the portable ZIP if it must embed the signed Adbnik.exe, then publish."
