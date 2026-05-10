param(
    [string]$OutputRoot = "backups",
    [string]$DbContainer = "equipment_db",
    [string]$DbName = "equipment_db",
    [string]$DbUser = "equipment_user",
    [string]$MediaPath = "backend\media"
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
$outputRootPath = Join-Path $repoRoot $OutputRoot
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupDir = Join-Path $outputRootPath $timestamp
$dbDumpPath = Join-Path $backupDir "database.sql"
$mediaArchivePath = Join-Path $backupDir "media.zip"
$manifestPath = Join-Path $backupDir "manifest.txt"
$mediaFullPath = Join-Path $repoRoot $MediaPath

New-Item -ItemType Directory -Force -Path $backupDir | Out-Null

Write-Host "Creating PostgreSQL dump..."
$dbDump = docker exec $DbContainer pg_dump -U $DbUser -d $DbName --clean --if-exists --no-owner --no-privileges
$utf8NoBom = New-Object System.Text.UTF8Encoding -ArgumentList $false
[System.IO.File]::WriteAllLines($dbDumpPath, $dbDump, $utf8NoBom)

Write-Host "Archiving media files..."
if (Test-Path -LiteralPath $mediaFullPath) {
    $mediaItems = Get-ChildItem -LiteralPath $mediaFullPath -Force
    if ($mediaItems.Count -gt 0) {
        Compress-Archive -Path (Join-Path $mediaFullPath "*") -DestinationPath $mediaArchivePath -Force
    }
} else {
    New-Item -ItemType Directory -Force -Path $mediaFullPath | Out-Null
}

@(
    "created_at=$(Get-Date -Format o)",
    "db_container=$DbContainer",
    "db_name=$DbName",
    "db_user=$DbUser",
    "media_path=$MediaPath",
    "database_dump=database.sql",
    "media_archive=$(if (Test-Path -LiteralPath $mediaArchivePath) { 'media.zip' } else { '' })"
) | Set-Content -Path $manifestPath -Encoding utf8

Write-Host "Backup created: $backupDir"
