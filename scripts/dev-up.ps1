$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $root "backend"
$webDir = Join-Path $root "web"
$adminDir = Join-Path $root "admin"

if (Test-Path (Join-Path $root ".venv\Scripts\python.exe")) {
  $pythonExe = Join-Path $root ".venv\Scripts\python.exe"
} else {
  $pythonExe = "python"
}

function Start-ServiceProcess {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Name,
    [Parameter(Mandatory = $true)]
    [string]$Workdir,
    [Parameter(Mandatory = $true)]
    [string]$Command
  )

  Write-Host "Starting $Name..." -ForegroundColor Cyan
  Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "Set-Location '$Workdir'; $Command"
  ) | Out-Null
}

Start-ServiceProcess -Name "backend" -Workdir $backendDir -Command "$pythonExe manage.py runserver 0.0.0.0:8080"
Start-ServiceProcess -Name "web" -Workdir $webDir -Command "npm run dev"
Start-ServiceProcess -Name "admin" -Workdir $adminDir -Command "npm run dev -- --host 0.0.0.0 --port 5173"

Write-Host ""
Write-Host "Services are starting in separate PowerShell windows:" -ForegroundColor Green
Write-Host "Backend: http://localhost:8080/api/v1"
Write-Host "Web:     http://localhost:3000"
Write-Host "Admin:   http://localhost:5173"
