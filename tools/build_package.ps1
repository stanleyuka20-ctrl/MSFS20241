<#
.SYNOPSIS
  Build an MSFS 2024 package from a project folder with the installed SDK's package tool.

.DESCRIPTION
  Locates fspackagetool.exe under $env:MSFS2024_SDK (falls back to $env:MSFS_SDK only if
  told to). Command-line options of the package tool differ between SDK versions:
  this script passes only the project file. If it fails, build from the simulator's
  Developer Mode Project Editor instead (the supported interactive route) and record
  which method was used in the release notes.

  Example:
    powershell -ExecutionPolicy Bypass -File tools\build_package.ps1 -Project package\nycroads-r0-demo\nycroads-r0-demo.xml
#>
param(
  [Parameter(Mandatory = $true)][string]$Project,
  [switch]$AllowLegacySdk
)
$sdk = $env:MSFS2024_SDK
if (-not $sdk -and $AllowLegacySdk) { $sdk = $env:MSFS_SDK }
if (-not $sdk) { throw "MSFS2024_SDK is not set. Install the MSFS 2024 SDK (Developer Mode > Help > SDK Installer)." }
$tool = Get-ChildItem -Path $sdk -Recurse -Filter "fspackagetool.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $tool) { throw "fspackagetool.exe not found under $sdk" }
$verified = (Get-Content "config\msfs_gltf.json" -Raw | ConvertFrom-Json).verified
if (-not $verified) { Write-Warning "config\msfs_gltf.json is UNVERIFIED: this is a TEST build, not a release." }
Write-Host "Using $($tool.FullName) ($($tool.VersionInfo.FileVersion))"
& $tool.FullName (Resolve-Path $Project)
if ($LASTEXITCODE -ne 0) { throw "fspackagetool exited with $LASTEXITCODE" }
Write-Host "Done. Output: $(Split-Path (Resolve-Path $Project))\Packages"
