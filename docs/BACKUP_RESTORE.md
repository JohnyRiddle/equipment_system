# Backup and Restore

Инструкция рассчитана на текущую Docker-конфигурацию проекта:

- PostgreSQL container: `equipment_db`
- database: `equipment_db`
- user: `equipment_user`
- media directory: `backend/media`

## Создание backup

Запустите из корня проекта:

```powershell
.\scripts\backup.ps1
```

Скрипт создаст папку:

```text
backups\YYYYMMDD-HHMMSS\
```

Внутри:

- `database.xml` - полный backup базы в стандартном XML-формате фикстур Django;
- `media.zip` - архив `backend/media`, если в media есть файлы;
- `manifest.txt` - краткое описание backup.

Можно переопределить параметры:

```powershell
.\scripts\backup.ps1 `
  -OutputRoot "D:\equipment_backups" `
  -DbContainer "equipment_db" `
  -WebContainer "equipment_web" `
  -DbName "equipment_db" `
  -DbUser "equipment_user" `
  -MediaPath "backend\media"
```

Прямая команда для создания XML backup внутри web-контейнера:

```powershell
docker compose -f docker-compose.prod.yml exec web python manage.py backup_database_xml
```

## Восстановление

Восстановление перезаписывает данные в текущей базе объектами из `database.xml`.
Перед запуском убедитесь, что выбран правильный backup.

```powershell
.\scripts\restore.ps1 -BackupDir ".\backups\YYYYMMDD-HHMMSS" -Force
```

Скрипт:

- очищает текущую базу через `manage.py flush`;
- загружает `database.xml` через `manage.py loaddata`;
- распаковывает `media.zip` в `backend/media`, если архив есть.

## Проверка после восстановления

```powershell
cd backend
..\venv\Scripts\python.exe manage.py check
..\venv\Scripts\python.exe manage.py migrate --plan
..\venv\Scripts\python.exe manage.py test
```

Ожидаемо:

- `check` без ошибок;
- `migrate --plan` без ожидающих операций;
- тесты проходят.

## Практические правила

- Храните backup вне репозитория и вне сервера приложения.
- Проверяйте восстановление на отдельной тестовой БД, а не сразу на production.
- Не храните backup с секретами в публичных папках: XML backup содержит пользователей, доступы и зашифрованные секреты.
- Сохраняйте вместе с backup актуальный `.env` или production secret vault: без `ACCESS_SECRET_KEYS` старые секреты доступов нельзя расшифровать.
