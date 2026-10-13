<#
  One-line installer for Home Hub. Paste this into PowerShell on the always-on PC:

    irm https://raw.githubusercontent.com/fenphen/trooper-cadence/claude/home-printer-network-dashboard-jh14d2/homehub/bootstrap.ps1 | iex

  It installs Python if needed (via winget), downloads the homehub folder from GitHub to
  C:\HomeHub, and runs install-windows.ps1 (which asks for admin once).
#>
$ErrorActionPreference = "Stop"
$branch = "claude/home-printer-network-dashboard-jh14d2"
$dest = "C:\HomeHub"

Write-Host "Home Hub bootstrap" -ForegroundColor Cyan

# Python
$havePy = $false
foreach ($cand in @("py -3", "python")) {
  try { $v = & cmd /c "$cand -c `"import sys;print(sys.version_info[0]*100+sys.version_info[1])`"" 2>$null; if ($v -and [int]$v -ge 310) { $havePy = $true; break } } catch {}
}
if (-not $havePy) {
  Write-Host "Python not found; installing with winget (this takes a minute)..."
  winget install --id Python.Python.3.12 -e --accept-source-agreements --accept-package-agreements --silent
  $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
}

# Download the branch and keep only homehub/
$zip = Join-Path $env:TEMP "homehub.zip"
$tmp = Join-Path $env:TEMP "homehub-unzip"
Write-Host "Downloading from GitHub..."
Invoke-WebRequest -Uri "https://codeload.github.com/fenphen/trooper-cadence/zip/refs/heads/$branch" -OutFile $zip
if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
Expand-Archive $zip -DestinationPath $tmp
$src = Get-ChildItem $tmp -Directory | Select-Object -First 1 | ForEach-Object { Join-Path $_.FullName "homehub" }
New-Item -ItemType Directory -Force $dest | Out-Null
# keep config.json and data/ from a previous install
Get-ChildItem $src | Where-Object { $_.Name -notin @("config.json", "data", ".venv") } | ForEach-Object { Copy-Item $_.FullName -Destination $dest -Recurse -Force }
Remove-Item $zip, $tmp -Recurse -Force
Write-Host "Files are in $dest"

# Install (elevates itself for the firewall rule and startup task)
Set-Location $dest
& powershell -ExecutionPolicy Bypass -File (Join-Path $dest "install-windows.ps1")
