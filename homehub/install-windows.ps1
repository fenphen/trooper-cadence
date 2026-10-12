<#
  Home Hub installer for the always-on Windows PC.
  Right-click this file -> "Run with PowerShell" (it asks for admin once, for the firewall rule).

  What it does:
    1. Checks Python 3.10+ is installed (tells you where to get it if not).
    2. Creates a private Python environment in .venv and installs the few packages needed.
    3. Opens Windows Firewall port 8080 so the other PCs in the house can reach it.
    4. Registers a Scheduled Task "Home Hub" that starts the server at boot, hidden, and restarts it if it stops.
    5. Writes "Home Hub.url" next to this script: copy that shortcut to any PC's desktop.
  Run with -Uninstall to remove the task and firewall rule.
#>
param([switch]$Uninstall, [int]$Port = 8080)

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here

if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
  Write-Host "Asking for administrator rights (needed for the firewall rule and the startup task)..."
  $args = @("-ExecutionPolicy", "Bypass", "-File", "`"$($MyInvocation.MyCommand.Path)`"", "-Port", $Port)
  if ($Uninstall) { $args += "-Uninstall" }
  Start-Process powershell -Verb RunAs -ArgumentList $args
  exit
}

$taskName = "Home Hub"
$ruleName = "Home Hub dashboard ($Port)"

if ($Uninstall) {
  schtasks /End /TN $taskName 2>$null | Out-Null
  schtasks /Delete /TN $taskName /F 2>$null | Out-Null
  Remove-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
  Write-Host "Removed the startup task and firewall rule. The files in $here are untouched."
  Read-Host "Press Enter to close"
  exit
}

# 1. Python
$py = $null
foreach ($cand in @("py -3", "python")) {
  try {
    $v = & cmd /c "$cand -c `"import sys;print(sys.version_info[0]*100+sys.version_info[1])`"" 2>$null
    if ($v -and [int]$v -ge 310) { $py = $cand; break }
  } catch {}
}
if (-not $py) {
  Write-Host "Python 3.10 or newer was not found." -ForegroundColor Yellow
  Write-Host "Install it from https://www.python.org/downloads/windows/ and tick 'Add python.exe to PATH', then run this again."
  Read-Host "Press Enter to close"
  exit 1
}

# 2. venv + packages
if (-not (Test-Path ".venv\Scripts\python.exe")) {
  Write-Host "Creating Python environment..."
  & cmd /c "$py -m venv .venv"
}
Write-Host "Installing packages..."
& ".venv\Scripts\python.exe" -m pip install -q --upgrade pip
& ".venv\Scripts\python.exe" -m pip install -q -r requirements.txt

if (-not (Test-Path "config.json")) { Copy-Item config.example.json config.json }
if ($Port -ne 8080) {
  $cfg = Get-Content config.json -Raw | ConvertFrom-Json
  $cfg.port = $Port
  $cfg | ConvertTo-Json -Depth 5 | Set-Content config.json
}

# 3. firewall
Remove-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Protocol TCP -LocalPort $Port -Action Allow -Profile Private,Domain | Out-Null

# 4. scheduled task (runs at startup as SYSTEM so nobody has to log in; restarts every minute if it dies)
$pythonw = Join-Path $here ".venv\Scripts\pythonw.exe"
$action = New-ScheduledTaskAction -Execute $pythonw -Argument "-m homehub" -WorkingDirectory $here
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) -StartWhenAvailable -DontStopOnIdleEnd -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description "Printer, scanner and network dashboard for the house" | Out-Null
Start-ScheduledTask -TaskName $taskName

# 5. shortcut
$ip = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" -and $_.PrefixOrigin -ne "WellKnown" } | Sort-Object InterfaceMetric | Select-Object -First 1).IPAddress
$host = $env:COMPUTERNAME.ToLower()
$url = "http://$host`:$Port/"
@"
[InternetShortcut]
URL=$url
IconIndex=0
"@ | Set-Content "Home Hub.url"

Start-Sleep -Seconds 3
Write-Host ""
Write-Host "Home Hub is installed and running." -ForegroundColor Green
Write-Host "  On this PC:      http://localhost:$Port/"
Write-Host "  On other PCs:    $url   (or http://$ip`:$Port/ if the name does not resolve)"
Write-Host "  Shortcut file:   $here\Home Hub.url  - copy it to any desktop"
Write-Host "  Stop/start:      Task Scheduler -> 'Home Hub', or run this script with -Uninstall"
Write-Host ""
Start-Process $url
Read-Host "Press Enter to close"
