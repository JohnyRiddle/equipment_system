param(
    [string]$ComposeFile = "docker-compose.prod.yml",
    [switch]$SkipPull
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
Push-Location $repoRoot
try {
    if (-not $SkipPull) {
        git pull --ff-only
    }

    docker compose -f $ComposeFile up -d --build
    docker compose -f $ComposeFile exec web python manage.py migrate
    docker compose -f $ComposeFile exec web python manage.py collectstatic --noinput
    docker compose -f $ComposeFile ps
}
finally {
    Pop-Location
}
