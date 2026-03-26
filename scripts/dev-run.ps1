$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

function Stop-ListeningPort {
  param([int]$Port)
  $connections = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $_.LocalPort -eq $Port }
  foreach ($connection in $connections) {
    try {
      Stop-Process -Id $connection.OwningProcess -Force -ErrorAction SilentlyContinue
    } catch {
    }
  }
}

function Stop-RepoProcessByPattern {
  param([string]$Pattern)
  $processes = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -and $_.CommandLine -match 'tuvan-tc' -and $_.CommandLine -match $Pattern
  }
  foreach ($process in $processes) {
    try {
      Stop-Process -Id $process.ProcessId -Force -ErrorAction SilentlyContinue
    } catch {
    }
  }
}

Stop-ListeningPort -Port 8080
Stop-ListeningPort -Port 3000
Stop-ListeningPort -Port 5173

Stop-RepoProcessByPattern -Pattern 'run_t0_worker'
Stop-RepoProcessByPattern -Pattern 'run_t0_foreign_worker'
Stop-RepoProcessByPattern -Pattern 'run_foreign_backfill_worker'
Stop-RepoProcessByPattern -Pattern 'vite'
Stop-RepoProcessByPattern -Pattern 'next dev'
Stop-RepoProcessByPattern -Pattern 'manage.py runserver 0.0.0.0:8080'

$pythonPath = if (Test-Path (Join-Path $repoRoot '.venv\Scripts\python.exe')) { (Join-Path $repoRoot '.venv\Scripts\python.exe') } else { 'python' }

Push-Location (Join-Path $repoRoot 'backend')
@'
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from apps.settings_app import services as s
s.save_t0_worker_lock({})
s.save_t0_foreign_worker_lock({})
s.save_t0_worker_status({
    'running': False,
    'connected': False,
    'phase': 'Stopped',
    'lastError': 'Reset before npm run dev',
})
s.save_foreign_backfill_lock({})
s.save_foreign_backfill_runtime({
    'running': False,
    'phase': 'Stopped',
    'lastError': 'Reset before npm run dev',
})
print('locks_reset')
'@ | & $pythonPath - | Out-Null
Pop-Location

npx concurrently -k -n backend,web,admin,t0-worker,t0-foreign,foreign-worker -c blue,green,magenta,cyan,white,yellow "npm run dev:backend" "npm run dev:web" "npm run dev:admin" "npm run dev:t0-worker" "npm run dev:t0-foreign-worker" "npm run dev:foreign-worker"
