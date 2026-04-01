$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$runtimeDir = Join-Path $repoRoot ".local-dev"
$backendDir = Join-Path $repoRoot "backend"
$adminDir = Join-Path $repoRoot "admin"

New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null

if (Test-Path (Join-Path $repoRoot ".venv\Scripts\python.exe")) {
  $pythonExe = Join-Path $repoRoot ".venv\Scripts\python.exe"
} else {
  $pythonExe = "python"
}

function Test-PortListening {
  param([int]$Port)
  $result = netstat -ano | Select-String ":$Port "
  return [bool]$result
}

function Start-DetachedService {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Name,
    [Parameter(Mandatory = $true)]
    [string]$Workdir,
    [Parameter(Mandatory = $true)]
    [string]$Executable,
    [Parameter(Mandatory = $true)]
    [string[]]$Arguments,
    [Parameter(Mandatory = $true)]
    [int]$Port
  )

  if (Test-PortListening -Port $Port) {
    Write-Host "$Name is already listening on port $Port" -ForegroundColor Yellow
    return
  }

  $stdoutPath = Join-Path $runtimeDir "$Name.out.log"
  $stderrPath = Join-Path $runtimeDir "$Name.err.log"
  $pidPath = Join-Path $runtimeDir "$Name.pid"

  Write-Host "Starting $Name on port $Port..." -ForegroundColor Cyan
  $process = Start-Process -FilePath $Executable -ArgumentList $Arguments -WorkingDirectory $Workdir -WindowStyle Hidden -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath -PassThru

  Set-Content -LiteralPath $pidPath -Value $process.Id
}

Start-DetachedService -Name "backend" -Workdir $backendDir -Executable $pythonExe -Arguments @("manage.py", "runserver", "0.0.0.0:8080") -Port 8080
Start-DetachedService -Name "admin" -Workdir $adminDir -Executable "npm.cmd" -Arguments @("run", "dev", "--", "--host", "0.0.0.0", "--port", "5173") -Port 5173

Write-Host ""
Write-Host "Local dev status:" -ForegroundColor Green
Write-Host "  Backend: http://localhost:8080"
Write-Host "  Admin:   http://localhost:5173"
Write-Host "  Logs:    $runtimeDir"
