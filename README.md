# InfraScope

Платформа мониторинга IT-инфраструктуры. Отслеживает состояние принтеров через SNMP, сканирует сеть, определяет устройства по MAC-адресу, автоматически обнаруживает смену IP при DHCP.

## Содержание

- [Возможности](#возможности)
- [Стек технологий](#стек-технологий)
- [Быстрый старт](#быстрый-старт)
- [Ручная установка](#ручная-установка)
- [Настройка HTTPS](#настройка-https)
- [Локальный домен](#локальный-домен)
- [Безопасность](#безопасность)
- [Разработка](#разработка)
- [Переменные окружения](#переменные-окружения)
- [Настройка SNMP на принтерах](#настройка-snmp-на-принтерах)
- [Поддерживаемые принтеры](#поддерживаемые-принтеры)
- [Структура проекта](#структура-проекта)
- [API](#api)
- [MAC-идентификация и DHCP](#mac-идентификация-и-dhcp)
- [Кросс-платформенность](#кросс-платформенность)
- [CI/CD](#cicd)
- [Решение проблем](#решение-проблем)

---

## Возможности

- **Мониторинг принтеров** — SNMP-опрос HP, Ricoh, Kyocera, Brother, Canon, Xerox и др. Статус онлайн/офлайн, уровни тонера K/C/M/Y
- **Параллельный опрос** — одновременный опрос до 20 принтеров через пул потоков
- **Сканер сети** — обнаружение принтеров в подсетях по TCP-портам (9100, 631, 80, 443), идентификация через SNMP (hostname, MAC)
- **MAC-first идентификация** — MAC-адрес как неизменный якорь устройства. Автоматическое обнаружение смены IP при DHCP
- **Верификация MAC** — при каждом опросе сверяется текущий MAC с сохранённым. Статусы: подтверждён / не совпадает / недоступен
- **Redis-кеширование** — кеш списков принтеров, результатов сканирования, прогресса сканирования
- **Управление пользователями** — JWT-аутентификация с поддержкой отзыва токенов (jti + Redis blacklist), роли admin/user
- **Два типа принтеров** — картриджные (SNMP) и этикетки/Zebra (TCP-порт 9100)
- **HTTPS** — автоматические самоподписанные сертификаты или доверенные через mkcert
- **Локальный домен** — `infrascope.local` вместо localhost
- **Rate limiting** — защита от брутфорса на эндпоинте логина (5 запросов/минута)
- **Argon2id** — хеширование паролей по стандарту OWASP
- **Swagger UI** — интерактивная документация API по адресу `/docs`

---

## Стек технологий

| Слой           | Технология                                                              |
|----------------|-------------------------------------------------------------------------|
| Backend        | Python 3.14, FastAPI, SQLModel, PostgreSQL 17, Alembic, pysnmp-lextudio |
| Frontend       | React 19, TypeScript, Vite, Tailwind CSS v4, TanStack Query             |
| Кеш            | Redis 7 (alpine)                                                        |
| Безопасность   | Argon2id, JWT (jti blacklist), slowapi rate limiting                     |
| Инфра          | Docker Compose, Nginx (SSL termination), GitHub Actions CI/CD           |

---

## Быстрый старт

После `git clone` достаточно запустить один скрипт — он автоматически создаст `.env` с безопасными паролями, настроит SSL, домен и запустит Docker.

### Требования

- Docker 24+ и Docker Compose v2
- Порты **80** и **443** свободны на хосте

### Linux / macOS

```bash
git clone https://github.com/GolubchikovKirill/SiteGKA.git
cd SiteGKA
./setup.sh
```

### Windows (PowerShell от администратора)

```powershell
git clone https://github.com/GolubchikovKirill/SiteGKA.git
cd SiteGKA
.\setup.ps1
```

### Что делает скрипт

1. Проверяет, что Docker установлен
2. Создаёт `.env` с автосгенерированными безопасными паролями (`SECRET_KEY`, `POSTGRES_PASSWORD`, пароль администратора)
3. Если установлен [mkcert](https://github.com/FiloSottile/mkcert) — создаёт доверенные SSL-сертификаты. Если нет — Nginx автоматически сгенерирует самоподписанные при первом запуске
4. Настраивает локальный домен `infrascope.local` в файле hosts
5. Спрашивает подсети для сканера принтеров
6. Собирает и запускает все Docker-контейнеры
7. Показывает URL и пароль администратора

После запуска приложение доступно:
- `https://infrascope.local`
- `https://localhost`
- API документация: `https://localhost/docs`

### Обновление

```bash
git pull
docker compose up -d --build
```

### Остановка

```bash
docker compose down          # остановить контейнеры
docker compose down -v       # + удалить данные БД и Redis
```

---

## Ручная установка

Если скрипт не подходит, можно настроить вручную:

```bash
# 1. Клонировать репозиторий
git clone https://github.com/GolubchikovKirill/SiteGKA.git
cd SiteGKA

# 2. Создать файл окружения
cp .env.example .env

# 3. Заполнить обязательные значения в .env:
#    SECRET_KEY — сгенерировать:
python -c "import secrets; print(secrets.token_urlsafe(32))"
#    POSTGRES_PASSWORD — надёжный пароль для БД
#    FIRST_SUPERUSER_PASSWORD — пароль администратора (мин. 8 символов, буквы + цифры)
#    SCAN_SUBNET — подсети для сканера (например: 10.10.98.0/24, 10.10.99.0/24)

# 4. (Опционально) Настроить SSL — см. раздел «Настройка HTTPS»

# 5. Запустить
docker compose up -d --build
```

> Если SSL-сертификаты не созданы вручную — Nginx автоматически сгенерирует самоподписанные при первом запуске. Браузер покажет предупреждение, но HTTPS будет работать.

---

## Настройка HTTPS

HTTPS работает из коробки — при первом запуске Nginx автоматически генерирует самоподписанные сертификаты. Для доверенных сертификатов (без предупреждений в браузере) используйте [mkcert](https://github.com/FiloSottile/mkcert).

### macOS

```bash
brew install mkcert
mkcert -install
mkcert -cert-file certs/cert.pem -key-file certs/key.pem infrascope.local localhost 127.0.0.1 ::1
```

### Linux (Ubuntu/Debian)

```bash
sudo apt install mkcert
mkcert -install
mkcert -cert-file certs/cert.pem -key-file certs/key.pem infrascope.local localhost 127.0.0.1 ::1
```

### Windows (PowerShell от администратора)

```powershell
choco install mkcert
mkcert -install
mkcert -cert-file certs/cert.pem -key-file certs/key.pem infrascope.local localhost 127.0.0.1 ::1
```

После создания сертификатов перезапустите контейнеры:

```bash
docker compose restart frontend
```

> Папка `certs/` включена в `.gitignore` — сертификаты генерируются на каждой машине отдельно.

---

## Локальный домен

Вместо `localhost` приложение доступно по адресу `infrascope.local`. Скрипты `setup.sh` / `setup.ps1` настраивают это автоматически. Для ручной настройки:

### macOS / Linux

```bash
sudo sh -c 'echo "127.0.0.1 infrascope.local" >> /etc/hosts'
```

### Windows (PowerShell от администратора)

```powershell
Add-Content C:\Windows\System32\drivers\etc\hosts "127.0.0.1 infrascope.local"
```

При развёртывании на сервере в локальной сети — на каждой клиентской машине добавьте `<IP-сервера> infrascope.local` в файл hosts, или пропишите запись в локальном DNS.

---

## Безопасность

| Мера                         | Реализация                                                    |
|------------------------------|---------------------------------------------------------------|
| Хеширование паролей          | Argon2id (time_cost=3, memory=64MB, parallelism=4)            |
| Аутентификация               | JWT с jti для отзыва токенов, blacklist в Redis               |
| Rate limiting                | 5 запросов/минуту на `/auth/login` (slowapi + Redis)          |
| Авторизация                  | Роли admin/user, все мутации — admin only                     |
| Валидация входных данных     | Pydantic: email, IP, длина строк, формат портов/подсетей      |
| Пароли                       | Мин. 8 символов, буквы + цифры, макс. 128 символов            |
| JWT payload                  | Только `sub` (user ID), `exp`, `jti` — без чувствительных данных |
| HTTPS                        | TLS 1.2/1.3, автоматический HTTP → HTTPS редирект             |
| CORS                         | Whitelist origin из `.env`                                    |
| Секреты                      | `.env` и `certs/` в `.gitignore`                              |
| Миграция хешей               | Автоматический rehash bcrypt → Argon2id при логине             |

---

## Разработка

```bash
# 1. Запустить PostgreSQL и Redis
docker compose up db redis -d

# 2. Backend (порт 8000)
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload

# 3. Frontend (порт 5173, /api проксируется на backend)
cd frontend
npm install
npm run dev
```

Приложение в dev-режиме: `http://localhost:5173`

---

## Переменные окружения

Файл `.env` (создаётся из `.env.example` или автоматически скриптом `setup.sh`/`setup.ps1`):

| Переменная                  | Обязательно | Описание                                                      |
|-----------------------------|:-----------:|---------------------------------------------------------------|
| `SECRET_KEY`                | ✅           | JWT-секрет (автогенерируется скриптом setup)                  |
| `ENVIRONMENT`               |             | `production` или `development` (default: `production`)        |
| `POSTGRES_SERVER`           |             | Хост БД (default: `db`)                                       |
| `POSTGRES_PORT`             |             | Порт БД (default: `5432`)                                     |
| `POSTGRES_USER`             |             | Пользователь БД (default: `postgres`)                         |
| `POSTGRES_PASSWORD`         | ✅           | Пароль БД (автогенерируется скриптом setup)                   |
| `POSTGRES_DB`               |             | Имя БД (default: `infrascope`)                                |
| `REDIS_URL`                 |             | URL Redis (default: `redis://redis:6379/0`)                   |
| `FIRST_SUPERUSER_EMAIL`     |             | Email администратора (default: `admin@infrascope.dev`)        |
| `FIRST_SUPERUSER_PASSWORD`  | ✅           | Пароль первого администратора (автогенерируется скриптом setup)|
| `DOMAIN`                    |             | Локальный домен (default: `infrascope.local`)                 |
| `SCAN_SUBNET`               |             | Подсети для сканера, через запятую (например: `10.10.98.0/24, 10.10.99.0/24`) |
| `SCAN_PORTS`                |             | Порты для сканирования (default: `9100,631,80,443`)           |
| `BACKEND_CORS_ORIGINS`      |             | JSON-массив разрешённых CORS origin                           |
| `FRONTEND_PORT`             |             | HTTP-порт Nginx (default: `80`)                               |

> В режиме `ENVIRONMENT=production` приложение не запустится, если `SECRET_KEY` не задан или равен `changethis`.

---

## Настройка SNMP на принтерах

Для работы мониторинга на каждом принтере необходимо включить SNMP. Обычно это делается через веб-интерфейс принтера (`http://<IP-принтера>`).

### Что нужно включить

1. **SNMP v1/v2c** — протокол опроса. Ищите в разделах:
   - `Network → Protocol Settings → SNMP`
   - `Admin → Security → SNMP`
   - `Settings → Network → SNMP`

2. **Community string** — пароль для чтения. По умолчанию `public`. Если меняете — укажите своё значение при добавлении принтера.

3. **Доступ по IP** — убедитесь, что IP сервера с InfraScope не заблокирован в ACL принтера.

### Настройка по производителям

| Производитель        | Путь в меню                                          |
|----------------------|------------------------------------------------------|
| **HP**               | `Settings → Security → Access Control → SNMP`        |
| **Ricoh**            | `Device Management → Configuration → SNMP`           |
| **Kyocera**          | `Network Settings → TCP/IP → SNMP`                   |
| **Brother**          | `Administrator → Network → Protocol → SNMP`          |
| **Canon**            | `Settings/Registration → Network → SNMP Settings`    |
| **Xerox**            | `Properties → Connectivity → Protocols → SNMP`       |
| **Lexmark**          | `Settings → Network/Ports → SNMP`                    |
| **OKI**              | `Admin Setup → Network Menu → SNMP`                  |
| **Konica Minolta**   | `Network → SNMP Setting`                             |

### Требования к сети

- Принтер доступен по **UDP 161** с сервера InfraScope
- Если принтеры в другой подсети — нужен маршрут или VPN
- Docker bridge-сеть поддерживает SNMP через NAT. На Linux для ARP/MAC-определения можно использовать `network_mode: host` (см. `docker-compose.prod.yml`)

---

## Поддерживаемые принтеры

Используется стандартный Printer MIB (RFC 3805) как основной метод и проприетарные OID как резерв.

| Производитель             | Статус | Метод                                         |
|---------------------------|:------:|-----------------------------------------------|
| HP LaserJet               | ✅      | Стандартный Printer MIB                       |
| Ricoh / Savin / Gestetner | ✅      | Стандартный Printer MIB                       |
| Kyocera / Mita            | ✅      | Стандартный Printer MIB                       |
| Xerox                     | ✅      | Стандартный Printer MIB                       |
| Canon (лазерные)          | ✅      | Стандартный Printer MIB                       |
| Lexmark                   | ✅      | Стандартный Printer MIB                       |
| Samsung (лазерные)        | ✅      | Стандартный Printer MIB                       |
| OKI                       | ✅      | Стандартный Printer MIB                       |
| Konica Minolta / bizhub   | ✅      | Стандартный Printer MIB                       |
| Epson (бизнес WF/ET)      | ✅      | Стандартный Printer MIB                       |
| **Brother**               | ✅      | Стандартный MIB + фолбэк на проприетарные OID |
| Epson (домашние струйные) | ❌      | SNMP отсутствует или нет Printer MIB          |
| Очень старые (до 2000 г.) | ⚠️     | Может не поддерживать Printer MIB             |

**Автоматическое определение:**
- Производитель (из sysDescr)
- Тонерные картриджи vs барабаны/maintenance kit (фильтруются)
- Цвет тонера по описанию (EN, DE, FR, RU, аббревиатуры BK/C/M/Y)

---

## Структура проекта

```
├── app/
│   ├── main.py              # FastAPI entrypoint, lifespan, rate limiting
│   ├── models.py            # SQLModel: User, Printer (mac_address, mac_status)
│   ├── schemas.py           # Pydantic: валидация, ScanRequest, DiscoveredDevice
│   ├── crud.py              # CRUD + auto-rehash паролей
│   ├── core/
│   │   ├── config.py        # Настройки (pydantic-settings, DOMAIN, SCAN_SUBNET)
│   │   ├── db.py            # Engine, init_db
│   │   ├── redis.py         # Redis-клиент (async)
│   │   ├── limiter.py       # Rate limiter (slowapi + Redis)
│   │   └── security.py      # JWT (jti + Redis blacklist) + Argon2id
│   ├── services/
│   │   ├── snmp.py          # SNMP: poll_printer, get_snmp_mac (ifPhysAddress)
│   │   ├── scanner.py       # Сканер сети: TCP-проба, SNMP-идентификация, ARP
│   │   └── ping.py          # TCP port check для Zebra/этикеточных
│   └── api/
│       ├── deps.py          # Auth-зависимости FastAPI
│       └── routes/
│           ├── auth.py      # Логин (rate limited), logout
│           ├── users.py     # Управление пользователями
│           ├── printers.py  # CRUD + poll + MAC-верификация + авто-relocate
│           └── scanner.py   # Сканер: запуск, прогресс, результаты
├── frontend/
│   ├── src/
│   │   ├── App.tsx          # Роутинг (React Router)
│   │   ├── auth.tsx         # Auth контекст (JWT в localStorage)
│   │   ├── client.ts        # API клиент (axios + interceptors)
│   │   ├── components/
│   │   │   ├── Layout.tsx          # Шапка, навигация, табы
│   │   │   ├── PrinterCard.tsx     # Карточка принтера + MacStatus
│   │   │   ├── ZebraCard.tsx       # Карточка Zebra/этикеточного
│   │   │   ├── PrinterForm.tsx     # Форма добавления/редактирования
│   │   │   ├── UserForm.tsx        # Форма пользователя
│   │   │   ├── NetworkScanner.tsx  # Вкладка сканера сети
│   │   │   └── TonerBar.tsx        # Полоска уровня тонера
│   │   └── pages/
│   │       ├── Login.tsx           # Страница входа
│   │       ├── Dashboard.tsx       # Главная: принтеры, статистика
│   │       └── Users.tsx           # Управление пользователями (admin)
│   ├── Dockerfile              # Multi-stage: Node build → Nginx + auto-SSL
│   ├── docker-entrypoint.sh    # Автогенерация SSL при отсутствии сертификатов
│   └── nginx.conf              # HTTPS, SPA-роутинг, проксирование /api
├── alembic/                 # Миграции базы данных
├── certs/                   # SSL-сертификаты (авто или mkcert, не в git)
├── scripts/
│   └── prestart.sh          # Миграции + seed при старте контейнера
├── setup.sh                 # Скрипт установки для Linux/macOS
├── setup.ps1                # Скрипт установки для Windows
├── Dockerfile               # Backend: Python 3.14 + uv (multi-stage)
├── docker-compose.yml       # Production-стек (HTTP + HTTPS)
├── docker-compose.prod.yml  # Linux-override: network_mode: host для ARP/MAC
├── .env.example             # Шаблон конфигурации
└── .github/workflows/ci.yml # CI/CD pipeline
```

---

## API

Интерактивная документация: `https://infrascope.local/docs`

### Аутентификация

| Метод  | Путь                        | Описание                      | Доступ   |
|--------|-----------------------------|-------------------------------|----------|
| `POST` | `/api/v1/auth/login`        | Вход (rate limited: 5/мин)    | Публично |
| `POST` | `/api/v1/auth/logout`       | Выход (отзыв токена)          | Auth     |
| `POST` | `/api/v1/auth/test-token`   | Проверить токен               | Auth     |

### Пользователи

| Метод    | Путь                          | Описание             | Доступ |
|----------|-------------------------------|----------------------|--------|
| `GET`    | `/api/v1/users/me`            | Текущий пользователь | Auth   |
| `PATCH`  | `/api/v1/users/me`            | Обновить профиль     | Auth   |
| `PATCH`  | `/api/v1/users/me/password`   | Сменить пароль       | Auth   |
| `GET`    | `/api/v1/users/`              | Список пользователей | Admin  |
| `POST`   | `/api/v1/users/`              | Создать пользователя | Admin  |
| `GET`    | `/api/v1/users/{id}`          | Пользователь по ID   | Admin  |
| `PATCH`  | `/api/v1/users/{id}`          | Изменить пользователя| Admin  |
| `DELETE` | `/api/v1/users/{id}`          | Удалить пользователя | Admin  |

### Принтеры

| Метод    | Путь                            | Описание                                  | Доступ |
|----------|---------------------------------|-------------------------------------------|--------|
| `GET`    | `/api/v1/printers/`             | Список (фильтр по магазину, тип)          | Auth   |
| `POST`   | `/api/v1/printers/`             | Добавить принтер                          | Admin  |
| `GET`    | `/api/v1/printers/{id}`         | Принтер по ID                             | Auth   |
| `PATCH`  | `/api/v1/printers/{id}`         | Обновить принтер                          | Admin  |
| `DELETE` | `/api/v1/printers/{id}`         | Удалить принтер                           | Admin  |
| `POST`   | `/api/v1/printers/{id}/poll`    | Опросить один принтер (SNMP + MAC)        | Auth   |
| `POST`   | `/api/v1/printers/poll-all`     | Опросить все принтеры параллельно          | Auth   |

### Сканер сети

| Метод  | Путь                        | Описание                              | Доступ |
|--------|-----------------------------|---------------------------------------|--------|
| `POST` | `/api/v1/scanner/scan`      | Запустить сканирование подсети        | Admin  |
| `GET`  | `/api/v1/scanner/status`    | Прогресс текущего сканирования        | Auth   |
| `GET`  | `/api/v1/scanner/results`   | Результаты последнего сканирования    | Auth   |
| `POST` | `/api/v1/scanner/add`       | Добавить найденный принтер            | Admin  |
| `POST` | `/api/v1/scanner/update-ip` | Обновить IP принтера (DHCP)           | Admin  |
| `GET`  | `/api/v1/scanner/settings`  | Настройки сканера по умолчанию        | Auth   |

### Система

| Метод | Путь       | Описание        |
|-------|------------|-----------------|
| `GET` | `/health`  | Health check    |
| `GET` | `/docs`    | Swagger UI      |

---

## MAC-идентификация и DHCP

InfraScope использует MAC-адрес как неизменный идентификатор устройства. Это обеспечивает надёжность в сетях с DHCP.

### Как это работает

1. **Первый опрос** — MAC определяется через SNMP (OID `ifPhysAddress`) и автоматически сохраняется в базу
2. **Каждый следующий опрос** — текущий MAC сверяется с сохранённым:
   - **Подтверждён** (зелёный) — MAC совпал, это тот же принтер
   - **Не совпадает** (красный) — на этом IP другое устройство
   - **Недоступен** (серый) — не удалось получить MAC (принтер оффлайн или SNMP не отвечает)
3. **Автоматическое обнаружение смены IP** — если принтер оффлайн, система ищет его MAC в кеше последнего сканирования сети. Если MAC найден на другом IP — IP обновляется автоматически
4. **Сканер сети** — при обнаружении устройства по MAC, которое есть в базе, но с другим IP, помечает его как «IP изменился»

### Рекомендации

- Периодически запускайте сканирование сети — результаты кешируются в Redis и используются для авто-обнаружения
- На DHCP-сервере по возможности привяжите принтеры к MAC (DHCP reservation)

---

## Кросс-платформенность

InfraScope работает на macOS, Linux и Windows через Docker.

| Функция                  | macOS         | Linux            | Windows          |
|--------------------------|---------------|------------------|------------------|
| SNMP-опрос               | ✅             | ✅                | ✅                |
| TCP-сканирование         | ✅             | ✅                | ✅                |
| SNMP MAC (ifPhysAddress) | ✅             | ✅                | ✅                |
| ARP MAC (из таблицы)     | ⚠️ Docker VM  | ✅ (host network) | ⚠️ Docker VM     |
| `network_mode: host`     | ❌ не работает | ✅                | ❌ не работает    |
| Скрипт установки         | `./setup.sh`  | `./setup.sh`     | `.\setup.ps1`    |

> На macOS/Windows Docker Desktop запускает контейнеры внутри VM — ARP таблица хоста недоступна. MAC-адреса определяются через SNMP (работает везде).

> На Linux для полного доступа к ARP используйте: `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build`

---

## CI/CD

GitHub Actions запускается при каждом push/PR в `main`:

1. **Backend Lint** — Ruff (правила E, F, I, UP)
2. **Backend Test** — Pytest с PostgreSQL 17 (миграции + тесты)
3. **Frontend Build** — TypeScript typecheck + Vite production build
4. **Docker Build** — сборка образов backend и frontend (только на push в `main`)

---

## Решение проблем

### Принтер показывается офлайн, хотя он работает

1. Проверить, что SNMP включён (см. [Настройка SNMP](#настройка-snmp-на-принтерах))
2. Проверить UDP 161:
   ```bash
   nc -vzu <IP-принтера> 161
   ```
3. Убедиться, что community string совпадает (по умолчанию `public`)
4. Запустить сканирование сети — возможно, IP изменился (DHCP)

### MAC-статус «не совпадает»

- На данном IP сейчас другое устройство (MAC изменился)
- Возможные причины: замена принтера, пересадка IP, конфликт адресов
- Запустите сканирование, чтобы найти принтер по его MAC на новом IP

### Тонер не показывается (`—`)

- Принтер не поддерживает Printer MIB (RFC 3805)
- Для Brother: обновите прошивку — старые версии не отдают тонер по стандартному MIB
- Проверить логи: `docker compose logs backend | grep <IP-принтера>`

### Backend не запускается (SECRET_KEY)

```
ValueError: SECRET_KEY must be set to a secure value in production
```

Используйте скрипт `setup.sh` / `setup.ps1` — он автоматически генерирует безопасный ключ. Или вручную:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### HTTPS не работает / предупреждение в браузере

1. HTTPS работает из коробки с самоподписанными сертификатами — браузер покажет предупреждение, но можно продолжить
2. Для доверенных сертификатов установите mkcert (см. [Настройка HTTPS](#настройка-https))
3. После `mkcert -install` перезапустите браузер

### Ошибка 429 Too Many Requests на логине

Rate limiting — 5 попыток в минуту. Подождите 60 секунд и попробуйте снова.

### Сканер не находит устройства

1. Проверьте `SCAN_SUBNET` в `.env` — должна совпадать с подсетью принтеров
2. Формат: CIDR через запятую, например `10.10.98.0/24, 10.10.99.0/24`
3. Максимум 10 подсетей, минимальная маска /16
4. Убедитесь, что принтеры доступны по сети из Docker-контейнера

### Пересборка и перезапуск

```bash
docker compose down
docker compose up -d --build
```

Если нужно сбросить кеш сборки:

```bash
docker compose build --no-cache
docker compose up -d
```

### Просмотр логов

```bash
docker compose logs backend --tail=100 -f    # бэкенд
docker compose logs frontend --tail=50       # nginx
docker compose logs db --tail=30             # postgres
docker compose logs redis --tail=30          # redis
```
