# Release Process

## Версионирование

Проект использует формат `MAJOR.MINOR.PATCH`.

- `PATCH` повышается для исправлений без изменения сценариев работы: `0.1.1`, `0.1.2`.
- `MINOR` повышается для новых модулей или заметной функциональности: `0.2.0`.
- `MAJOR` повышается для несовместимых изменений или первой стабильной production-линии: `1.0.0`.

Текущая версия хранится в `backend/config/version.py` и выводится в интерфейсе. На сервере ее можно переопределить переменной `APP_VERSION`, но штатный процесс - менять файл версии в патч-коммите.

## Подготовка патча

```powershell
git checkout main
git pull
git checkout -b codex/patch-short-name
```

После правок:

```powershell
.\scripts\release_check.ps1
git add .
git commit -m "Prepare patch 0.1.1"
git push origin codex/patch-short-name
```

После проверки ветка вливается в `main`.

## Тег версии

```powershell
git checkout main
git pull
git tag v0.1.1
git push origin v0.1.1
```

## Серверное обновление

На сервере:

```powershell
.\scripts\deploy.ps1
```

Перед патчем с миграциями сделайте backup БД и media. Инструкция: `docs/BACKUP_RESTORE.md`.

## Обязательные проверки перед релизом

- `python manage.py check`
- `python manage.py makemigrations --check --dry-run`
- `python manage.py test`
- `python manage.py collectstatic --noinput --dry-run`
- `docker compose -f docker-compose.prod.yml config --quiet`
