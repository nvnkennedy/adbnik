# Print SHA-256 for site/downloads/* and suggested config.js fragments.
# Usage from repo root:
#   powershell -ExecutionPolicy Bypass -File scripts\compute_release_hashes.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$dir = Join-Path $Root "site\downloads"
if (-not (Test-Path $dir)) {
    Write-Error "Not found: $dir — copy installers there first."
}

$setup = Get-ChildItem $dir -Filter "*.exe" | Select-Object -First 1
$zip = Get-ChildItem $dir -Filter "*.zip" | Select-Object -First 1

Write-Host "SHA-256 (verify locally before trusting):"
Write-Host ""
if ($setup) {
    $h = (Get-FileHash -Algorithm SHA256 -LiteralPath $setup.FullName).Hash
    Write-Host ("  Installer ({0}): {1}" -f $setup.Name, $h)
}
if ($zip) {
    $h2 = (Get-FileHash -Algorithm SHA256 -LiteralPath $zip.FullName).Hash
    Write-Host ("  Portable  ({0}): {1}" -f $zip.Name, $h2)
}

Write-Host ""
Write-Host "Suggested config.js entries (paste and check filenames match setupUrl/portableUrl):"
Write-Host ""
if ($setup) {
    $hs = (Get-FileHash -Algorithm SHA256 -LiteralPath $setup.FullName).Hash
    Write-Host ('  sha256Setup: "' + $hs + '",')
}
if ($zip) {
    $hz = (Get-FileHash -Algorithm SHA256 -LiteralPath $zip.FullName).Hash
    Write-Host ('  sha256Portable: "' + $hz + '",')
}
