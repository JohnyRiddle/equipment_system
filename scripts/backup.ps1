param(
    [string]$OutputRoot = "backups",
    [string]$DbContainer = "equipment_db",
    [string]$WebContainer = "equipment_web",
    [string]$DbName = "equipment_db",
    [string]$DbUser = "equipment_user",
    [string]$MediaPath = "backend\media"
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
$outputRootPath = Join-Path $repoRoot $OutputRoot
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupDir = Join-Path $outputRootPath $timestamp
$dbDumpPath = Join-Path $backupDir "database.xml"
$mediaArchivePath = Join-Path $backupDir "media.zip"
$manifestPath = Join-Path $backupDir "manifest.txt"
$mediaFullPath = Join-Path $repoRoot $MediaPath

New-Item -ItemType Directory -Force -Path $backupDir | Out-Null

Write-Host "Creating XML database backup..."
docker exec $WebContainer python manage.py backup_database_xml --output /tmp/database.xml
docker cp "${WebContainer}:/tmp/database.xml" $dbDumpPath
docker exec $WebContainer rm -f /tmp/database.xml | Out-Null

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
    "web_container=$WebContainer",
    "db_name=$DbName",
    "db_user=$DbUser",
    "media_path=$MediaPath",
    "database_dump=database.xml",
    "database_format=xml",
    "media_archive=$(if (Test-Path -LiteralPath $mediaArchivePath) { 'media.zip' } else { '' })"
) | Set-Content -Path $manifestPath -Encoding utf8

Write-Host "Backup created: $backupDir"
