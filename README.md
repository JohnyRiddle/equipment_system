# Equipment System

Django-система учета оборудования: справочники организаций и локаций, карточки оборудования, реквизиты, файлы, заметки, перемещения, QR-коды, печать QR-этикеток и внутренний административный интерфейс.

## Стек

- Python 3.12
- Django
- PostgreSQL
- Bootstrap templates
- Docker / Docker Compose

## Версия

Текущая версия приложения: `0.1.0`.

Версия хранится в `backend/config/version.py`, выводится в боковой панели интерфейса и может быть переопределена на сервере через `APP_VERSION`. История изменений ведется в [CHANGELOG.md](CHANGELOG.md), процесс патчей описан в [docs/RELEASE_PROCESS.md](docs/RELEASE_PROCESS.md).

## Локальный запуск

Команды ниже рассчитаны на запуск из корня проекта `C:\projects\equipment_system`.

```powershell
cd backend
..\venv\Scripts\python.exe manage.py migrate
..\venv\Scripts\python.exe manage.py seed_initial_data
..\venv\Scripts\python.exe manage.py seed_access_types
..\venv\Scripts\python.exe manage.py createsuperuser
..\venv\Scripts\python.exe manage.py runserver 0.0.0.0:8000
```

После запуска:

- приложение: http://127.0.0.1:8000/
- вход: http://127.0.0.1:8000/login/
- оборудование: http://127.0.0.1:8000/equipment/
- внутренний админ-раздел: http://127.0.0.1:8000/admin-panel/
- Django admin: http://127.0.0.1:8000/admin/

## Настройки окружения

Проект имеет рабочие значения по умолчанию, но их можно переопределить переменными окружения:

```powershell
$env:DJANGO_SECRET_KEY="change-me"
$env:DJANGO_DEBUG="True"
$env:DJANGO_ALLOWED_HOSTS="127.0.0.1,localhost"
$env:POSTGRES_DB="equipment_db"
$env:POSTGRES_USER="postgres"
$env:POSTGRES_PASSWORD="postgres"
$env:POSTGRES_HOST="localhost"
$env:POSTGRES_PORT="5432"
$env:ACCESS_SECRET_KEYS="<fernet-key>"
```

Ключ для секретов доступов генерируется так:

```powershell
cd backend
..\venv\Scripts\python.exe -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

`ACCESS_SECRET_KEYS` можно задавать списком через запятую: первый ключ используется для новых секретов, остальные позволяют читать старые после ротации.

## Миграции

```powershell
cd backend
..\venv\Scripts\python.exe manage.py makemigrations
..\venv\Scripts\python.exe manage.py migrate
```

Проверить, что миграции применены:

```powershell
..\venv\Scripts\python.exe manage.py showmigrations
..\venv\Scripts\python.exe manage.py migrate --plan
```

## Начальные справочники

Команда заполняет базовые организации, локации, центры затрат, склады, статусы и категории оборудования.

```powershell
cd backend
..\venv\Scripts\python.exe manage.py seed_initial_data
```

Команду можно запускать повторно: существующие записи не дублируются.

Типы технических доступов заполняются отдельной командой:

```powershell
cd backend
..\venv\Scripts\python.exe manage.py seed_access_types
```

Команду также можно запускать повторно.

## Пользователи и роли

Суперпользователь создается стандартной командой Django:

```powershell
cd backend
..\venv\Scripts\python.exe manage.py createsuperuser
```

В проекте используется текущая модель доступа приложения: `system_admin`, `company_admin`, `staff` и ограничения по доступным юрлицам/локациям. Если старый план модулей упоминает роли `developer/admin/support/restaurant`, их не нужно механически переносить поверх уже реализованной схемы.

## QR-коды

QR-код создается при создании оборудования и хранится в `backend/media/`.

Массовая регенерация:

```powershell
cd backend
..\venv\Scripts\python.exe manage.py regenerate_qr_codes
```

Регенерация для всех карточек:

```powershell
..\venv\Scripts\python.exe manage.py regenerate_qr_codes --all
```

В интерфейсе также есть ручная регенерация на карточке оборудования для пользователей с правами редактирования.

## Карточка оборудования

В карточке оборудования доступны:

- основные поля оборудования и текущая привязка к юрлицу, локации, ЦФО и складу;
- бренд, модель, дата покупки, цена приобретения, оценочная текущая стоимость и зона размещения;
- даты последней инвентаризации и последнего ремонта;
- QR-метки и ручная регенерация QR для пользователей с правами редактирования;
- история перемещений;
- фото оборудования с выбором основного изображения;
- история ремонтов с описанием и стоимостью;
- история инвентаризаций с состоянием и оценочной стоимостью;
- заметки к оборудованию;
- реквизиты IP/MAC/домен/hostname/URL/прочее;
- файлы оборудования с загрузкой в `MEDIA_ROOT/equipment_files/`.

Фото, заметки, реквизиты и файлы добавляются из карточки оборудования. Фото, реквизиты и файлы архивируются мягко через `is_active=False`, без удаления записей из базы.

## Инвентаризация

Раздел `/inventory/` ведет акты инвентаризации. Пользователь создает акт, указывает юрлицо, локацию, период и номер акта, затем добавляет оборудование вручную или через карточку оборудования после сканирования QR/NFC-метки.

Основной сценарий:

- создать акт инвентаризации;
- добавить нужные позиции;
- пройти по объекту и отметить найденное оборудование, фактическую локацию, зону/склад, состояние, оценочную стоимость и комментарий;
- подтвердить акт кнопкой `Подтверждено`;
- открыть печатную форму акта и распечатать ее из браузера.

При проверке позиции создается запись в истории инвентаризаций оборудования, а в карточке обновляются дата последней инвентаризации, состояние и оценочная стоимость.

## Ремонты

Ремонт реализован как заявочный процесс. В карточке оборудования доступна кнопка `Отправить в ремонт`: пользователь описывает проблему и выбирает приоритет. После создания заявки оборудование переводится в статус `На ремонте`.

Техник работает с заявками в разделе `/repairs/`:

- принимает заявку в работу;
- назначает техника;
- меняет статус: заявка создана, принято техником, в работе, ожидает запчасти, завершено, отменено;
- фиксирует стоимость, исполнителя, результат ремонта и комментарий по статусу.

При завершении ремонта обновляется дата последнего ремонта в карточке оборудования, а оборудование возвращается в статус `В работе`.

## Отчеты

Раздел `/reports/` собирает основные сводки и выгрузки. Основные отчеты формируются на русском языке в форматах CSV, Excel и PDF:

- оборудование по статусам и локациям;
- отчет по оборудованию: `/reports/equipment.csv`, `/reports/equipment.xlsx`, `/reports/equipment.pdf`;
- отчет по ремонтам: `/reports/repairs.csv`, `/reports/repairs.xlsx`, `/reports/repairs.pdf`;
- отчет по инвентаризациям: `/reports/inventory.csv`, `/reports/inventory.xlsx`, `/reports/inventory.pdf`;
- отчет по перемещениям: `/reports/movements.csv`, `/reports/movements.xlsx`, `/reports/movements.pdf`;
- фильтры для ремонтов и инвентаризаций: `date_from`, `date_to`, `status`;
- быстрые показатели по открытым ремонтам, сумме ремонтов, актам инвентаризации и проверенным позициям.

## Глобальный поиск

Раздел `/search/` ищет по доступным пользователю данным:

- оборудование, серийные и инвентарные номера;
- QR/NFC-метки;
- технические доступы;
- заявки на ремонт;
- акты инвентаризации и позиции актов;
- перемещения оборудования.

Результаты сгруппированы по разделам и ведут в карточки оборудования, доступы, акты инвентаризации или журнал перемещений. Поиск учитывает права пользователя и не показывает данные вне доступных юрлиц/локаций.

## Уведомления

Раздел `/notifications/` показывает события, которые требуют внимания:

- ремонты, которые долго находятся в работе;
- незавершенные акты инвентаризации;
- оборудование, которое давно не инвентаризировалось;
- истекающие технические доступы;
- доступы без активного секрета;
- истекающие гарантии;
- оборудование в статусе `На ремонте` без активной заявки.

Уведомления вычисляются при открытии страницы, учитывают права пользователя и дополнительно показываются кратким блоком на главной панели.

## Доступы и секреты

Раздел `/accesses/` хранит технические доступы к оборудованию и объектам.

На текущем этапе реализовано:

- метаданные доступа: тип, host, port, URL, логин, описание;
- поле `Пароль` в форме доступа, которое сохраняется как зашифрованный секрет;
- добавление зашифрованных секретов;
- ротация и архивирование секретов;
- раскрытие секрета только отдельным POST-действием;
- журнал успешных и запрещенных попыток раскрытия;
- журнал изменений карточки доступа и секретов;
- персональные гранты на одну карточку доступа;
- CSV-экспорт метаданных доступов без секретов;
- отчет по персональным доступам сотрудников.

Пароли, токены и ключи нельзя вводить в обычные поля описания. Для них используется форма добавления секрета на карточке доступа.

Для работы секретов обязательно задайте `ACCESS_SECRET_KEYS`.

## Аудит

Общий журнал действий доступен во внутренней админ-панели: `/admin-panel/audit/`.

В журнал пишутся создание, изменение, архивирование, перемещения, операции с фото/файлами/реквизитами/заметками, действия с техническими доступами и секретами, персональные гранты, CSV/PDF-экспорты.

Модель журнала находится в `apps.core.models.ActionLog`, запись событий выполняется через `apps.core.services.log_action`.

## Статика и медиа

Основные настройки:

- `STATIC_URL=/static/`
- `STATIC_ROOT=backend/staticfiles/`
- `MEDIA_URL=/media/`
- `MEDIA_ROOT=backend/media/`

Сборка статики:

```powershell
cd backend
..\venv\Scripts\python.exe manage.py collectstatic --noinput
```

В режиме разработки Django отдает media-файлы через `MEDIA_URL`, поэтому QR-изображения должны открываться локально после запуска `runserver`.

## Docker

Запуск приложения и PostgreSQL:

```powershell
docker compose up --build
```

После старта контейнера можно выполнить начальное заполнение и создать пользователя:

```powershell
docker compose exec web python manage.py seed_initial_data
docker compose exec web python manage.py seed_access_types
docker compose exec web python manage.py createsuperuser
```

Полезные команды:

```powershell
docker compose exec web python manage.py check
docker compose exec web python manage.py test
docker compose exec web python manage.py regenerate_qr_codes
```

Docker-compose поднимает сервис `web` на порту `8000` и базу `db` на PostgreSQL.

## Production Docker

Для серверного запуска используйте отдельный compose-файл:

```powershell
copy .env.example .env
```

В `.env` обязательно замените:

- `DJANGO_SECRET_KEY`
- `POSTGRES_PASSWORD`
- `ACCESS_SECRET_KEYS`
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_CSRF_TRUSTED_ORIGINS`
- `QR_EQUIPMENT_BASE_URL`
- `APP_VERSION`

Запуск:

```powershell
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml exec web python manage.py seed_initial_data
docker compose -f docker-compose.prod.yml exec web python manage.py seed_access_types
docker compose -f docker-compose.prod.yml exec web python manage.py createsuperuser
```

Production compose запускает Django через Gunicorn, отдает `/static/` и `/media/` через Nginx и не публикует PostgreSQL наружу. Если HTTPS завершается на внешнем reverse proxy, включите в `.env` `DJANGO_SECURE_SSL_REDIRECT=1` и передавайте `X-Forwarded-Proto=https`. HSTS (`DJANGO_SECURE_HSTS_SECONDS`, include subdomains и preload) включайте только после проверки SSL на домене и поддоменах.

## Backup и restore

Для backup PostgreSQL и `backend/media` добавлены PowerShell-скрипты:

```powershell
.\scripts\backup.ps1
.\scripts\restore.ps1 -BackupDir ".\backups\YYYYMMDD-HHMMSS" -Force
```

Подробная инструкция: [docs/BACKUP_RESTORE.md](docs/BACKUP_RESTORE.md).

## Проверки

```powershell
cd backend
..\venv\Scripts\python.exe manage.py check
..\venv\Scripts\python.exe manage.py test
..\venv\Scripts\python.exe manage.py migrate
```

Перед передачей проекта на другой компьютер полезно также проверить:

```powershell
..\venv\Scripts\python.exe manage.py collectstatic --noinput
docker compose config
```

## Частые проблемы

PostgreSQL недоступен:

- проверьте, что сервер PostgreSQL запущен;
- проверьте `POSTGRES_HOST`, `POSTGRES_PORT`, имя БД и пароль;
- для Docker внутри контейнера используется `POSTGRES_HOST=db`.

Статика не загружается:

- выполните `collectstatic`;
- проверьте, что директория `backend/staticfiles/` создается;
- в разработке убедитесь, что `DEBUG=True`.

QR-код не отображается:

- проверьте наличие файла в `backend/media/`;
- выполните `regenerate_qr_codes`;
- убедитесь, что карточка оборудования имеет сохраненный QR image field.

Ошибка 403 или кнопки редактирования скрыты:

- проверьте роль пользователя;
- проверьте доступные юрлица и локации пользователя;
- суперпользователь и `system_admin` видят весь контур.

## Заметки разработчику

- Основное приложение находится в `backend/apps/`.
- Общая логика доступа вынесена в `backend/apps/dashboard/access.py`.
- Пользовательский бизнес-админ находится в `backend/apps/dashboard/admin_views.py`.
- CRUD оборудования и перемещения находятся в `backend/apps/dashboard/views.py`.
- PDF-печать QR-этикеток находится в `backend/apps/dashboard/pdf.py`.
- Справочные данные заполняются командой `backend/apps/core/management/commands/seed_initial_data.py`.
- Историю миграций не стоит переписывать без отдельной причины: проект уже рассчитан на последовательное применение существующих миграций.
