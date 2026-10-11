# Lancé par la tâche planifiée Windows « ASP Buvette - sync » (toutes les 4 h).
# Scrape les matchs du club sur la FFBB et les envoie dans Supabase.
# Journal : logs\run_sync.log
$ErrorActionPreference = "Continue"
$repo = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repo
New-Item -ItemType Directory -Force logs | Out-Null
$log = Join-Path $repo "logs\run_sync.log"
if ((Test-Path $log) -and (Get-Item $log).Length -gt 500KB) { Move-Item $log "$log.old" -Force }
function Log($m) { "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $m" | Add-Content -Encoding utf8 $log }

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"
$python = "C:\Users\utilisateur\AppData\Local\Programs\Python\Python312\python.exe"

Log "=== début ==="
$out = & $python sync.py 2>&1 | Out-String
$code = $LASTEXITCODE
Log ($out -split "`r?`n" | Where-Object { $_ -notmatch "tect|uniques" } | Out-String).Trim()
if ($code -ne 0) { Log "sync en échec ou partielle (code $code)"; exit 1 }
Log "sync OK"
