param(
    [string]$Python = "..\venv\Scripts\python.exe"
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
$backendPath = Join-Path $repoRoot "backend"

Push-Location $backendPath
try {
    & $Python manage.py check
    & $Python manage.py makemigrations --check --dry-run
    & $Python manage.py test
    & $Python manage.py collectstatic --noinput --dry-run
}
finally {
    Pop-Location
}

$env:DJANGO_SECRET_KEY = if ($env:DJANGO_SECRET_KEY) { $env:DJANGO_SECRET_KEY } else { "release-check-secret-key-with-more-than-fifty-characters-1234567890" }
$env:DJANGO_ALLOWED_HOSTS = if ($env:DJANGO_ALLOWED_HOSTS) { $env:DJANGO_ALLOWED_HOSTS } else { "ays-crm.ru,www.ays-crm.ru" }
$env:DJANGO_CSRF_TRUSTED_ORIGINS = if ($env:DJANGO_CSRF_TRUSTED_ORIGINS) { $env:DJANGO_CSRF_TRUSTED_ORIGINS } else { "https://ays-crm.ru,https://www.ays-crm.ru" }
$env:ACCESS_SECRET_KEYS = if ($env:ACCESS_SECRET_KEYS) { $env:ACCESS_SECRET_KEYS } else { "Fb5x5XVWJ8JzZ8aQJiM9sGnfp4QYEqxdDS1qupz7Uj8=" }
$env:POSTGRES_DB = if ($env:POSTGRES_DB) { $env:POSTGRES_DB } else { "equipment_db" }
$env:POSTGRES_USER = if ($env:POSTGRES_USER) { $env:POSTGRES_USER } else { "equipment_user" }
$env:POSTGRES_PASSWORD = if ($env:POSTGRES_PASSWORD) { $env:POSTGRES_PASSWORD } else { "replace-me" }

Push-Location $repoRoot
try {
    docker compose -f docker-compose.prod.yml config --quiet
}
finally {
    Pop-Location
}

Write-Host "Release checks completed successfully."
