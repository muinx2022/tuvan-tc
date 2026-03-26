# Apply Spring Boot Flyway SQL files to PostgreSQL in correct version order (V1..V16, not alphabetical).
# Requires: psql via Docker (container mvp-postgres) or set $env:PSQL to your psql.exe
# Usage:
#   .\scripts\apply-flyway-sql.ps1
#   $env:FLYWAY_SQL_DIR = "D:\path\to\java\backend\src\main\resources\db\migration"

param(
    [string]$Database = "mvpdb",
    [string]$User = "mvp",
    [string]$Container = "mvp-postgres"
)

$ErrorActionPreference = "Stop"
$dir = $env:FLYWAY_SQL_DIR
if (-not $dir) {
    $dir = "D:\Projects\java\backend\src\main\resources\db\migration"
}
if (-not (Test-Path $dir)) {
    Write-Error "Migration folder not found: $dir. Set FLYWAY_SQL_DIR to your Spring backend db/migration path."
}

$files = Get-ChildItem $dir -Filter "V*.sql" | Sort-Object { [int]($_.Name -replace '^V(\d+)__.*', '$1') }
foreach ($f in $files) {
    Write-Host "=== $($f.Name) ===" -ForegroundColor Cyan
    Get-Content $f.FullName -Raw | docker exec -i $Container psql -U $User -d $Database -v ON_ERROR_STOP=1
    if ($LASTEXITCODE -ne 0) { throw "Failed on $($f.Name)" }
}
Write-Host "Flyway SQL applied OK ($($files.Count) files)." -ForegroundColor Green
