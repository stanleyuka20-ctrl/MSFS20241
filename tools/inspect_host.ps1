<#
.SYNOPSIS
  Read-only inventory of the Windows host: MSFS 2024 installation, SDK, Community
  packages and candidate vehicles/scenery that may conflict with this project.

.DESCRIPTION
  Makes NO changes. Writes a JSON report (default: docs\host-inspection.json) that
  is committed with each release so test results are tied to an exact environment.
  Run from the repository root:
      powershell -ExecutionPolicy Bypass -File tools\inspect_host.ps1

  Paths below are the commonly documented locations for the Microsoft Store and
  Steam editions; anything not found is reported as missing rather than guessed.
#>
param([string]$Out = "docs\host-inspection.json")

$ErrorActionPreference = "Continue"
$report = [ordered]@{
  generated_utc = (Get-Date).ToUniversalTime().ToString("o")
  machine       = $env:COMPUTERNAME
  os            = (Get-CimInstance Win32_OperatingSystem | Select-Object Caption, Version, BuildNumber)
  cpu           = (Get-CimInstance Win32_Processor | Select-Object -First 1 Name, NumberOfCores, NumberOfLogicalProcessors)
  ram_gb        = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 1)
  gpu           = (Get-CimInstance Win32_VideoController | Select-Object Name, DriverVersion, AdapterRAM)
  msfs          = [ordered]@{}
  sdk           = [ordered]@{}
  community     = @()
  flags         = @()
}

# ---- Simulator: Microsoft Store / Xbox app edition
$store = Get-AppxPackage -Name "Microsoft.Limitless" -ErrorAction SilentlyContinue
if ($store) {
  $report.msfs.store = [ordered]@{ version = $store.Version; install_location = $store.InstallLocation }
  $cfg = Join-Path $env:LOCALAPPDATA "Packages\Microsoft.Limitless_8wekyb3d8bbwe\LocalCache\UserCfg.opt"
  if (Test-Path $cfg) { $report.msfs.store.usercfg = $cfg }
}

# ---- Simulator: Steam edition (find the app manifest by name, not by a hard-coded app id)
$steamRoots = @("${env:ProgramFiles(x86)}\Steam", "$env:ProgramFiles\Steam") | Where-Object { Test-Path $_ }
foreach ($root in $steamRoots) {
  $libs = @("$root\steamapps")
  $lf = "$root\steamapps\libraryfolders.vdf"
  if (Test-Path $lf) {
    Select-String -Path $lf -Pattern '"path"\s+"([^"]+)"' | ForEach-Object {
      $libs += (Join-Path ($_.Matches[0].Groups[1].Value -replace '\\\\', '\') "steamapps")
    }
  }
  foreach ($lib in ($libs | Select-Object -Unique)) {
    Get-ChildItem -Path $lib -Filter "appmanifest_*.acf" -ErrorAction SilentlyContinue | ForEach-Object {
      $txt = Get-Content $_.FullName -Raw
      if ($txt -match '"name"\s+"Microsoft Flight Simulator 2024"') {
        $build = if ($txt -match '"buildid"\s+"(\d+)"') { $Matches[1] } else { $null }
        $dir   = if ($txt -match '"installdir"\s+"([^"]+)"') { Join-Path $lib "common\$($Matches[1])" } else { $null }
        $report.msfs.steam = [ordered]@{ manifest = $_.FullName; buildid = $build; install_dir = $dir }
      }
    }
  }
}
$steamCfg = Join-Path $env:APPDATA "Microsoft Flight Simulator 2024\UserCfg.opt"
if (Test-Path $steamCfg) { $report.msfs.steam_usercfg = $steamCfg }

# ---- Packages folder (InstalledPackagesPath from UserCfg.opt)
$cfgs = @($report.msfs.store.usercfg, $report.msfs.steam_usercfg) | Where-Object { $_ }
foreach ($c in $cfgs) {
  $line = Select-String -Path $c -Pattern '^InstalledPackagesPath\s+"(.+)"' | Select-Object -First 1
  if ($line) { $report.msfs.installed_packages_path = $line.Matches[0].Groups[1].Value }
}
if (-not $cfgs) { $report.flags += "MSFS 2024 UserCfg.opt not found: simulator may not be installed for this user" }

# ---- SDK
foreach ($var in @("MSFS2024_SDK", "MSFS_SDK")) {
  $v = [Environment]::GetEnvironmentVariable($var)
  if ($v) {
    $report.sdk[$var] = $v
    $tool = Get-ChildItem -Path $v -Recurse -Filter "fspackagetool.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($tool) { $report.sdk["fspackagetool_$var"] = $tool.FullName; $report.sdk["fspackagetool_version_$var"] = $tool.VersionInfo.FileVersion }
    $sc = Get-ChildItem -Path $v -Recurse -Filter "SimConnect.dll" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($sc) { $report.sdk["simconnect_dll_$var"] = $sc.FullName; $report.sdk["simconnect_version_$var"] = $sc.VersionInfo.FileVersion }
    $ver = Get-ChildItem -Path $v -Filter "*.txt" -ErrorAction SilentlyContinue | Where-Object { $_.Name -match "version|release" } | Select-Object -First 1
    if ($ver) { $report.sdk["version_file_$var"] = (Get-Content $ver.FullName -TotalCount 5) -join " " }
  }
}
if (-not $report.sdk.Contains("MSFS2024_SDK")) { $report.flags += "MSFS2024_SDK environment variable not set: install the MSFS 2024 SDK from the in-sim Developer Mode menu" }

# ---- Community packages: list all, flag NYC scenery and ground-vehicle candidates
$pkgRoot = $report.msfs.installed_packages_path
if ($pkgRoot -and (Test-Path "$pkgRoot\Community")) {
  Get-ChildItem "$pkgRoot\Community" -Directory | ForEach-Object {
    $m = Join-Path $_.FullName "manifest.json"
    $entry = [ordered]@{ folder = $_.Name }
    if (Test-Path $m) {
      try {
        $j = Get-Content $m -Raw | ConvertFrom-Json
        $entry.title = $j.title; $entry.content_type = $j.content_type; $entry.creator = $j.creator
        $entry.package_version = $j.package_version; $entry.minimum_game_version = $j.minimum_game_version
      } catch { $entry.manifest_error = $_.Exception.Message }
    }
    $hay = "$($_.Name) $($entry.title)".ToLower()
    if ($hay -match "nyc|new ?york|manhattan|brooklyn|queens|bronx|staten|kjfk|klga|kewr|kteb|hudson|bridge") { $entry.flag = "possible NYC scenery conflict" }
    if ($hay -match "car|truck|vehicle|drive|jeep|bus|taxi") { $entry.flag = "possible ground-vehicle add-on" }
    $report.community += $entry
  }
} else {
  $report.flags += "Community folder not found"
}

$report | ConvertTo-Json -Depth 6 | Set-Content -Encoding UTF8 $Out
Write-Host "Wrote $Out"
$report.flags | ForEach-Object { Write-Warning $_ }
