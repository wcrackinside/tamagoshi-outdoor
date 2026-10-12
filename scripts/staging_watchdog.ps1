param(
  [int]$IntervalSeconds = 60,
  [string]$Origin = 'https://outdoor-staging.privantix.io',
  [string]$Cloudflared = 'C:\Program Files (x86)\cloudflared\cloudflared.exe'
)
$ErrorActionPreference = 'Continue'
$root = Split-Path $PSScriptRoot -Parent
$logs = Join-Path $root 'staging-logs'
New-Item -ItemType Directory -Force $logs | Out-Null
$tunnelLog = Join-Path $logs 'cloudflared.log'
$state = Join-Path $logs 'deployed-api-url.txt'
function Log($msg) { "$(Get-Date -Format s) $msg" | Tee-Object -FilePath (Join-Path $logs 'watchdog.log') -Append }

function Test-Url($url) {
  try { (Invoke-WebRequest $url -UseBasicParsing -TimeoutSec 20).StatusCode -eq 200 } catch { $false }
}

function Start-Backend {
  $env:CORS_ORIGINS = "$Origin,http://localhost:5173,http://127.0.0.1:5173"
  $env:DB_PATH = Join-Path $root 'backend\staging.db'
  # Jobs are polled by the UI for up to 10 minutes, so Gemma may take longer than the old proxy limit.
  $env:OLLAMA_TIMEOUT = '420'
  $env:EXPOSE_DOCS = '0'
  Start-Process -FilePath (Join-Path $root 'backend\.venv\Scripts\python.exe') -WorkingDirectory (Join-Path $root 'backend') `
    -ArgumentList '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000' -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $logs 'backend.out.log') -RedirectStandardError (Join-Path $logs 'backend.err.log')
  Log 'backend started'
}

function Start-Tunnel {
  Get-Process cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force
  Remove-Item $tunnelLog -ErrorAction SilentlyContinue
  Start-Process -FilePath $Cloudflared -ArgumentList 'tunnel', '--no-autoupdate', '--logfile', "`"$tunnelLog`"", '--url', 'http://127.0.0.1:8000' -WindowStyle Hidden
  Log 'tunnel started'
}

function Get-TunnelUrl {
  if (-not (Test-Path $tunnelLog)) { return $null }
  $m = Select-String -Path $tunnelLog -Pattern 'https://[a-z0-9-]+\.trycloudflare\.com' | Select-Object -Last 1
  if ($m) { $m.Matches[0].Value }
}

$failures = 0
while ($true) {
  # While Gemma saturates the CPU /health can be slow; only restart when nothing listens on the port.
  if (-not (Test-Url 'http://127.0.0.1:8000/health')) {
    if (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue) { Log 'backend slow, still listening' }
    else { Start-Backend; Start-Sleep 10 }
  }
  if (-not (Get-Process cloudflared -ErrorAction SilentlyContinue)) { Start-Tunnel; Start-Sleep 20 }

  $url = Get-TunnelUrl
  if ($url -and (Test-Url "$url/health")) {
    $failures = 0
    $deployed = if (Test-Path $state) { (Get-Content $state -Raw).Trim() } else { '' }
    if ($url -ne $deployed) {
      Log "deploying config.js for $url"
      & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'deploy_staging.ps1') -ApiUrl $url -SkipBuild *>> (Join-Path $logs 'deploy.log')
      if ($LASTEXITCODE -eq 0) { Set-Content $state $url; Log 'deploy ok' } else { Log "deploy failed ($LASTEXITCODE)" }
    }
  } else {
    $failures++
    Log "tunnel unhealthy ($failures)"
    if ($failures -ge 3) { Start-Tunnel; $failures = 0; Start-Sleep 20 }
  }
  Start-Sleep $IntervalSeconds
}
