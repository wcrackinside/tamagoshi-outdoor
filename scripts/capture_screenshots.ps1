# Captures desktop + mobile screenshots into docs/screenshots using a fresh SQLite DB.
# Requires: backend venv in backend/.venv, Vite dev server on :5173 (npm run dev), frontend devDependencies
# (puppeteer-core) and Microsoft Edge (override with BROWSER_PATH).
# Example: .\scripts\capture_screenshots.ps1 -Lang en -Name en-gemma -Complete
#          .\scripts\capture_screenshots.ps1 -Lang es -Name es-demo -OllamaUrl http://127.0.0.1:9
param(
  [ValidateSet("es", "en")][string]$Lang = "es",
  [string]$Name = $Lang,
  [string]$OllamaUrl = "http://localhost:11434",
  [int]$Minutes = 10,
  [switch]$Complete,
  [string]$ReuseDb
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$out = Join-Path $root "docs\screenshots"
$work = Join-Path $env:TEMP ("tamagoshi-shots-" + [guid]::NewGuid().ToString("N").Substring(0, 8))
New-Item -ItemType Directory -Force $out, $work | Out-Null

Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
Start-Sleep 2

$env:DB_PATH = if ($ReuseDb) { (Resolve-Path $ReuseDb).Path } else { Join-Path $work "outdoor.db" }
$env:OLLAMA_URL = $OllamaUrl
$backend = Start-Process -PassThru -WindowStyle Hidden -WorkingDirectory (Join-Path $root "backend") `
  -FilePath (Join-Path $root "backend\.venv\Scripts\python.exe") -ArgumentList "-m", "uvicorn", "app.main:app", "--port", "8000"
try {
  for ($i = 0; $i -lt 40; $i++) {
    try { Invoke-RestMethod http://localhost:8000/health -TimeoutSec 2 | Out-Null; break } catch { Start-Sleep -Milliseconds 500 }
  }
  $interests = if ($Lang -eq "es") { "naturaleza, arquitectura" } else { "nature, architecture" }
  if (-not $ReuseDb) {
  $body = @{ minutes = $Minutes; language = $Lang; interests = $interests } | ConvertTo-Json
  $gen = Invoke-RestMethod -Method Post http://localhost:8000/missions/generate -ContentType "application/json; charset=utf-8" `
    -Body ([Text.Encoding]::UTF8.GetBytes($body)) -TimeoutSec 400
  Write-Host "source=$($gen.source) fallback_reason=$($gen.fallback_reason)"
  if ($Complete) {
    $note = if ($Lang -eq "es") { "Entrada de prueba para la captura (no es una salida real)." } else { "Test entry for the screenshot (not a real outing)." }
    $c = @{ reflection = $note } | ConvertTo-Json
    Invoke-RestMethod -Method Post "http://localhost:8000/missions/$($gen.missions[0].id)/complete" -ContentType "application/json; charset=utf-8" `
      -Body ([Text.Encoding]::UTF8.GetBytes($c)) | Out-Null
    $body2 = @{ minutes = 5; language = $Lang; interests = $interests } | ConvertTo-Json
    Invoke-RestMethod -Method Post http://localhost:8000/missions/generate -ContentType "application/json; charset=utf-8" `
      -Body ([Text.Encoding]::UTF8.GetBytes($body2)) -TimeoutSec 400 | Out-Null
  }
  }
  Write-Host "db=$env:DB_PATH"
  foreach ($mode in "desktop", "mobile") {
    $file = Join-Path $out "$Name-$mode.png"
    Start-Process -Wait -NoNewWindow -WorkingDirectory (Join-Path $root "frontend") -FilePath node `
      -ArgumentList "scripts/screenshot.mjs", "http://localhost:5173/?lang=$Lang", "`"$file`"", $mode
    if (-not (Test-Path $file)) { throw "Screenshot was not written: $file" }
    Write-Host "saved $file"
  }
} finally {
  Stop-Process -Id $backend.Id -Force -ErrorAction SilentlyContinue
}
