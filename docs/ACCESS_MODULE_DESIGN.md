# Access Module Design

Цель блока: хранить технические доступы к оборудованию и связанным объектам так, чтобы список доступов был удобен в работе, а секретные значения раскрывались только пользователям с отдельным правом и всегда попадали в аудит.

## Границы модуля

Модуль `Доступы` отвечает за:

- учет типов доступа: RDP, SSH, VPN, Web admin, Database, POS admin, Wi-Fi, Other;
- привязку доступа к оборудованию, юрлицу, локации и при необходимости ЦФО;
- хранение несекретных реквизитов: host, port, login, URL, описание;
- зашифрованное хранение секретов: пароль, private key, token, recovery code;
- контроль просмотра секретов;
- журнал раскрытия секретов;
- экспорт метаданных без секретов.

Модуль не должен заменять текущую модель пользователей и доступов к локациям. Он использует существующую схему `system_admin/company_admin/staff` и `UserLegalEntityAccess/UserLocationAccess`.

## Рекомендуемое Django-приложение

Создать отдельное приложение:

```text
backend/apps/accesses/
```

Почему отдельно:

- это самостоятельный домен с повышенными требованиями безопасности;
- его нельзя смешивать с `equipment`, чтобы не протащить секреты в обычные карточки;
- проще тестировать права, аудит и шифрование.

## Модель данных

### AccessType

Справочник типов доступа.

Поля:

- `id` UUID;
- `code` unique slug: `rdp`, `ssh`, `vpn`, `web_admin`, `database`, `pos_admin`, `wifi`, `other`;
- `name`;
- `is_active`;
- `sort_order`.

На первом этапе можно заполнить seed-командой или data migration.

### EquipmentAccess

Основная карточка доступа.

Поля:

- `id` UUID;
- `equipment` FK `equipment.Equipment`, nullable, `PROTECT`, `related_name='accesses'`;
- `legal_entity` FK `organizations.LegalEntity`, `PROTECT`;
- `location` FK `locations.Location`, `PROTECT`;
- `cost_center` FK `organizations.CostCenter`, nullable, blank, `PROTECT`;
- `access_type` FK `AccessType`, `PROTECT`;
- `title` short name;
- `host` blank;
- `port` positive int, nullable;
- `url` blank;
- `username` blank;
- `description` text blank;
- `is_active` bool default true;
- `created_by` FK User SET_NULL;
- `updated_by` FK User SET_NULL;
- `created_at`, `updated_at`;
- `last_secret_viewed_at` nullable;
- `expires_at` nullable;

Индексы:

- `legal_entity`, `location`;
- `equipment`;
- `access_type`;
- `is_active`;
- `expires_at`.

Правило согласованности:

- если `equipment` указан, `legal_entity/location/cost_center` должны соответствовать текущей карточке оборудования;
- если доступ не привязан к оборудованию, он все равно должен быть привязан к `legal_entity` и `location`.

### AccessSecret

Зашифрованные секреты доступа. Один доступ может иметь несколько секретов.

Поля:

- `id` UUID;
- `access` FK `EquipmentAccess`, CASCADE, `related_name='secrets'`;
- `secret_type` choices: `password`, `private_key`, `token`, `recovery_code`, `note`;
- `label`;
- `encrypted_value` binary/text;
- `encryption_version` positive int default 1;
- `is_active` bool default true;
- `created_by` FK User SET_NULL;
- `updated_by` FK User SET_NULL;
- `created_at`, `updated_at`;
- `rotated_at` nullable.

Важно:

- открытое значение секрета не должно храниться в модели, форме, логе, message framework или audit metadata;
- в списке показывать только факт наличия секрета и тип, например `password: есть`.

### AccessGrant

Дополнительные персональные права на доступы. Нужны, если прав по локации недостаточно.

Поля:

- `id` UUID;
- `user` FK User CASCADE;
- `access` FK `EquipmentAccess` CASCADE;
- `level` choices: `view_meta`, `view_secret`, `edit`, `admin`;
- `granted_by` FK User SET_NULL;
- `created_at`;
- `expires_at` nullable;

Уникальность:

- `unique_together = ('user', 'access')`.

На первом этапе можно не делать UI для персональных grant, но модель полезна сразу: она решает кейс “сотрудник видит только один конкретный VPN”.

### AccessSecretViewLog

Журнал раскрытия секретов.

Поля:

- `id` UUID;
- `access` FK `EquipmentAccess`, PROTECT;
- `secret` FK `AccessSecret`, PROTECT;
- `user` FK User SET_NULL;
- `viewed_at`;
- `ip_address`;
- `user_agent`;
- `result` choices: `allowed`, `denied`;
- `reason` blank.

Журнал нельзя удалять из UI. В Django admin можно оставить read-only.

### AccessChangeLog

Журнал изменений метаданных и факта изменения секрета.

Поля:

- `id` UUID;
- `access` FK `EquipmentAccess`, PROTECT;
- `user` FK User SET_NULL;
- `action` choices: `created`, `updated`, `archived`, `secret_added`, `secret_updated`, `secret_rotated`, `secret_deleted`;
- `created_at`;
- `metadata` JSONField.

В `metadata` нельзя писать открытые секреты.

## Шифрование

Рекомендуемый механизм: `cryptography.fernet.MultiFernet`.

Новая зависимость:

```text
cryptography
```

Новые env-переменные:

```text
ACCESS_SECRET_KEYS=base64-fernet-key-current,base64-fernet-key-previous
```

Правила:

- первый ключ используется для шифрования новых секретов;
- все ключи используются для расшифровки старых секретов;
- ротация ключей делается management command;
- без `ACCESS_SECRET_KEYS` приложение должно запрещать создание и раскрытие секретов, но может показывать метаданные.

Не использовать `DJANGO_SECRET_KEY` как ключ шифрования секретов. Его ротация и назначение другие.

## Права доступа

Разделяем два уровня:

1. `metadata access` — видеть карточку доступа без секрета;
2. `secret access` — раскрыть пароль/token/private key.

### Metadata access

Пользователь видит карточку доступа, если:

- он `superuser`, `system_admin` или `is_global_access`;
- или у него есть доступ к `legal_entity/location` через текущую модель;
- или у него есть персональный `AccessGrant` на этот доступ.

### Edit access

Пользователь может создавать/редактировать доступ, если:

- он `superuser`, `system_admin` или `is_global_access`;
- или у него есть `edit/admin` на соответствующую локацию или юрлицо;
- или у него есть `AccessGrant.level in ('edit', 'admin')`.

### Secret access

Пользователь может раскрыть секрет, если:

- он `superuser`;
- или `system_admin`;
- или у него есть персональный `AccessGrant.level in ('view_secret', 'admin')`;
- или роль `service_engineer` и есть `edit/admin` на локацию.

`company_admin` по умолчанию видит метаданные и может управлять карточками в своем контуре, но не обязательно видит секреты. Это более безопасный дефолт.

### Auditor

Роль `auditor`:

- видит метаданные в своем контуре;
- видит логи;
- не раскрывает секреты.

## UI

### Навигация

Добавить пункт:

```text
Доступы
```

Маршруты:

- `/accesses/` список;
- `/accesses/create/`;
- `/accesses/<uuid:pk>/`;
- `/accesses/<uuid:pk>/edit/`;
- `/accesses/<uuid:pk>/archive/`;
- `/accesses/<uuid:pk>/secrets/add/`;
- `/accesses/<uuid:pk>/secrets/<uuid:secret_pk>/reveal/`;
- `/accesses/<uuid:pk>/logs/`.

### Список доступов

Колонки:

- название;
- тип;
- оборудование;
- юрлицо;
- локация;
- host/url;
- username;
- есть секреты;
- истекает;
- активен.

Фильтры:

- поиск;
- тип доступа;
- юрлицо;
- локация;
- оборудование;
- активность;
- истекает до даты.

В списке не показывать пароли, токены и ключи.

### Детальная страница

Блоки:

- реквизиты подключения;
- привязка к оборудованию;
- секреты, но только как список типов;
- кнопка `Показать` рядом с секретом, если есть право;
- последние просмотры секрета;
- история изменений.

Раскрытие секрета:

- отдельный POST endpoint;
- CSRF обязателен;
- после раскрытия создать `AccessSecretViewLog`;
- показывать секрет на странице кратковременно, без сохранения в URL.

## API и формы

Формы:

- `EquipmentAccessForm`;
- `AccessSecretForm`;
- `AccessGrantForm` на втором этапе.

Сервисный слой:

- `encrypt_secret(value: str) -> str`;
- `decrypt_secret(encrypted_value: str) -> str`;
- `create_access_secret(access, secret_type, label, raw_value, user)`;
- `reveal_access_secret(secret, user, request)`;
- `log_secret_view(secret, user, request, result, reason='')`.

Права лучше держать в отдельном файле:

```text
apps/accesses/access.py
```

Он может переиспользовать `apps/dashboard/access.py`.

## Management commands

На первом этапе:

- `seed_access_types`;
- `rotate_access_secret_keys`;
- `export_access_metadata`.

Не делать команду, которая выгружает открытые секреты.

## Тесты

Минимальный набор:

- создание доступа пользователем с edit-правами;
- запрет создания вне доступной локации;
- список показывает только доступный контур;
- метаданные видны без раскрытия секрета;
- секрет не отображается в HTML списка и detail по умолчанию;
- раскрытие секрета доступно только разрешенным ролям;
- каждое раскрытие пишет `AccessSecretViewLog`;
- denied-попытка раскрытия тоже пишет лог;
- ротация ключа не ломает старые секреты;
- auditor не может раскрыть секрет.

## Этапы реализации

### Этап 1. База без раскрытия

- создать app `accesses`;
- добавить модели `AccessType`, `EquipmentAccess`;
- добавить seed типов;
- добавить список/detail/create/edit/archive;
- привязать к существующим правам по локации/юрлицу;
- добавить тесты metadata access.

Статус: реализовано.

### Этап 2. Секреты и шифрование

- добавить `cryptography`;
- добавить `ACCESS_SECRET_KEYS`;
- добавить `AccessSecret`;
- добавить сервисы шифрования;
- добавить форму добавления/обновления секрета;
- запретить вывод открытого секрета по умолчанию.

Статус: реализовано для добавления, ротации и архивирования секрета.

### Этап 3. Раскрытие и аудит

- добавить `AccessSecretViewLog`;
- добавить POST reveal endpoint;
- добавить логи denied/allowed;
- добавить UI последних просмотров;
- добавить тесты аудита.

Статус: реализовано для раскрытия, журнала просмотров и общего журнала изменений.

### Этап 4. Персональные гранты и отчеты

- добавить `AccessGrant`;
- добавить UI управления персональными правами;
- добавить CSV-экспорт метаданных;
- добавить отчет “доступы по сотрудникам”.

Статус: реализовано.

## Открытые решения перед реализацией

1. Разрешаем ли `company_admin` раскрывать секреты по умолчанию? Рекомендация: нет, только через персональный grant или `service_engineer`.
2. Нужен ли второй фактор перед раскрытием секрета? Если будет production-доступ извне, рекомендация: да.
3. Храним ли SSH private key как текстовый секрет или как файл? Рекомендация: на первом этапе как текстовый секрет.
4. Нужна ли ротация паролей по расписанию? Можно заложить поле `expires_at`, автоматизацию оставить на потом.
5. Делаем ли отдельные зоны/помещения до доступов? Не обязательно, но если доступы часто относятся к “серверной/кассовой зоне”, зоны стоит добавить раньше.
