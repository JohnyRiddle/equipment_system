param(
    [Parameter(Mandatory = $true)]
    [string]$BackupDir,

    [string]$DbContainer = "equipment_db",
    [string]$WebContainer = "equipment_web",
    [string]$DbName = "equipment_db",
    [string]$DbUser = "equipment_user",
    [string]$MediaPath = "backend\media",
    [switch]$Force
)

$ErrorActionPreference = "Stop"

if (-not $Force) {
    throw "Restore is destructive. Re-run with -Force after verifying BackupDir."
}

$repoRoot = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
$backupPath = Resolve-Path -LiteralPath $BackupDir
$dbDumpPath = Join-Path $backupPath "database.xml"
$mediaArchivePath = Join-Path $backupPath "media.zip"
$mediaFullPath = Join-Path $repoRoot $MediaPath

if (-not (Test-Path -LiteralPath $dbDumpPath)) {
    throw "XML database backup not found: $dbDumpPath"
}

Write-Host "Restoring XML database backup..."
docker cp $dbDumpPath "${WebContainer}:/tmp/database.xml"
docker exec $WebContainer python manage.py flush --noinput
docker exec $WebContainer python manage.py loaddata /tmp/database.xml
docker exec $WebContainer rm -f /tmp/database.xml | Out-Null

if ((Test-Path -LiteralPath $mediaArchivePath) -and ((Get-Item -LiteralPath $mediaArchivePath).Length -gt 0)) {
    Write-Host "Restoring media files..."
    New-Item -ItemType Directory -Force -Path $mediaFullPath | Out-Null
    Expand-Archive -LiteralPath $mediaArchivePath -DestinationPath $mediaFullPath -Force
}

Write-Host "Restore completed from: $backupPath"
