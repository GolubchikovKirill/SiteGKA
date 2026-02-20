# InfraScope

Платформа мониторинга IT-инфраструктуры. Отслеживает состояние принтеров через SNMP: онлайн/офлайн, уровни тонера CMYK по всем локациям в реальном времени.

## Содержание

- [Возможности](#возможности)
- [Стек технологий](#стек-технологий)
- [Быстрый старт (Docker)](#быстрый-старт-docker)
- [Разработка](#разработка)
- [Переменные окружения](#переменные-окружения)
- [Настройка SNMP на принтерах](#настройка-snmp-на-принтерах)
- [Поддерживаемые принтеры](#поддерживаемые-принтеры)
- [Структура проекта](#структура-проекта)
- [API](#api)
- [CI/CD](#cicd)
- [Решение проблем](#решение-проблем)

---

## Возможности

- **Мониторинг принтеров** — SNMP-опрос принтеров HP, Ricoh, Kyocera, Brother, Canon, Xerox и других. Статус онлайн/офлайн, уровни тонера K/C/M/Y
- **Параллельный опрос** — одновременный опрос до 20 принтеров, фоллбэк на вендорные OID для Brother
- **Управление пользователями** — JWT-аутентификация, роли admin/user
- **Swagger UI** — интерактивная документация API по адресу `/docs`

---

## Стек технологий

| Слой       | Технология                                                         |
|------------|--------------------------------------------------------------------|
| Backend    | Python 3.14, FastAPI, SQLModel, PostgreSQL 17, Alembic, pysnmp    |
| Frontend   | React 19, TypeScript, Vite, Tailwind CSS v4, TanStack Query        |
| Инфра      | Docker Compose, Nginx, GitHub Actions CI/CD                        |

---

## Быстрый старт (Docker)

### Требования

- Docker 24+ и Docker Compose v2
- Порт **80** свободен на хосте

### Установка

```bash
# 1. Клонировать репозиторий
git clone https://github.com/GolubchikovKirill/SiteGKA.git
cd SiteGKA

# 2. Создать файл окружения
cp .env.example .env

# 3. Обязательно заполнить три значения в .env:
#    SECRET_KEY  — сгенерировать командой ниже
python -c "import secrets; print(secrets.token_urlsafe(32))"
#    POSTGRES_PASSWORD  — любой надёжный пароль
#    FIRST_SUPERUSER_PASSWORD  — пароль первого администратора

# 4. Запустить стек
docker compose up -d --build

# Приложение доступно на http://localhost
# API документация: http://localhost/docs
```

### Обновление

```bash
git pull
docker compose up -d --build
```

### Остановка

```bash
docker compose down          # остановить контейнеры
docker compose down -v       # + удалить данные БД
```

---

## Разработка

```bash
# 1. Запустить только PostgreSQL
docker compose up db -d

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

Запуск с hot-reload через Docker:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
```

---

## Переменные окружения

Файл `.env` (создаётся из `.env.example`):

| Переменная                  | Обязательно | Описание                                                      |
|-----------------------------|:-----------:|---------------------------------------------------------------|
| `SECRET_KEY`                | ✅           | JWT-секрет. Генерировать: `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `ENVIRONMENT`               |             | `production` (default) или `development`                      |
| `POSTGRES_SERVER`           |             | Хост БД (default: `db` — имя Docker-сервиса)                  |
| `POSTGRES_PORT`             |             | Порт БД (default: `5432`)                                     |
| `POSTGRES_USER`             |             | Пользователь БД (default: `infrascope`)                       |
| `POSTGRES_PASSWORD`         | ✅           | Пароль БД                                                     |
| `POSTGRES_DB`               |             | Имя БД (default: `infrascope`)                                |
| `FIRST_SUPERUSER_EMAIL`     |             | Email первого администратора (default: `admin@infrascope.dev`)|
| `FIRST_SUPERUSER_PASSWORD`  | ✅           | Пароль первого администратора                                 |
| `BACKEND_CORS_ORIGINS`      |             | JSON-массив разрешённых origin для CORS                        |
| `FRONTEND_PORT`             |             | Порт Nginx на хосте (default: `80`)                           |

> **Важно:** в режиме `ENVIRONMENT=production` приложение не запустится, если `SECRET_KEY` не задан или равен `changethis`.

---

## Настройка SNMP на принтерах

Для работы мониторинга на каждом принтере необходимо выполнить следующие настройки. Обычно это делается через веб-интерфейс принтера (открыть в браузере `http://<IP-принтера>`).

### Что нужно включить

1. **SNMP v1/v2c** — протокол опроса. Ищите в разделах:
   - `Network → Protocol Settings → SNMP`
   - `Admin → Security → SNMP`
   - `Settings → Network → SNMP`

2. **Community string** (строка сообщества) — пароль для чтения SNMP. По умолчанию везде `public`. Если вы меняете его — укажите своё значение при добавлении принтера в приложении.

3. **Доступ по IP** — некоторые принтеры позволяют ограничивать SNMP по IP. Убедитесь, что IP-адрес сервера с InfraScope не заблокирован.

### Настройка по производителям

| Производитель | Путь в меню                                          |
|---------------|------------------------------------------------------|
| **HP**        | `Settings → Security → Access Control → SNMP`        |
| **Ricoh**     | `Device Management → Configuration → SNMP`           |
| **Kyocera**   | `Network Settings → TCP/IP → SNMP`                  |
| **Brother**   | `Administrator → Network → Protocol → SNMP`          |
| **Canon**     | `Settings/Registration → Network → SNMP Settings`   |
| **Xerox**     | `Properties → Connectivity → Protocols → SNMP`      |
| **Lexmark**   | `Settings → Network/Ports → SNMP`                   |
| **OKI**       | `Admin Setup → Network Menu → SNMP`                  |
| **Konica Minolta** | `Network → SNMP Setting`                       |

### Требования к сети

- Принтер должен быть доступен по **UDP порту 161** с сервера, где запущен InfraScope
- Если принтеры в другой подсети — нужен маршрут или VPN между подсетями
- При запуске в Docker: контейнер использует сеть хоста для SNMP-запросов через NAT. Для надёжности на Linux можно добавить `network_mode: host` в секцию `backend` в `docker-compose.yml`

---

## Поддерживаемые принтеры

Используется стандартный Printer MIB (RFC 3805) как основной метод, и проприетарные OID как резерв.

| Производитель             | Статус | Метод                                  |
|---------------------------|:------:|----------------------------------------|
| HP LaserJet               | ✅      | Стандартный Printer MIB                |
| Ricoh / Savin / Gestetner | ✅      | Стандартный Printer MIB                |
| Kyocera / Mita            | ✅      | Стандартный Printer MIB                |
| Xerox                     | ✅      | Стандартный Printer MIB                |
| Canon (лазерные)          | ✅      | Стандартный Printer MIB                |
| Lexmark                   | ✅      | Стандартный Printer MIB                |
| Samsung (лазерные)        | ✅      | Стандартный Printer MIB                |
| OKI                       | ✅      | Стандартный Printer MIB                |
| Konica Minolta / bizhub   | ✅      | Стандартный Printer MIB                |
| Epson (бизнес WF/ET)      | ✅      | Стандартный Printer MIB                |
| **Brother**               | ✅      | Стандартный MIB + фолбэк на проприетарные OID |
| Epson (домашние струйные) | ❌      | SNMP отсутствует или нет Printer MIB   |
| Очень старые (до 2000 г.) | ⚠️     | Может не поддерживать Printer MIB      |

**Что система определяет автоматически:**
- Производитель принтера (из sysDescr)
- Какие картриджи тонерные, а какие барабаны/maintenance kit (фильтруются)
- Цвет тонера по описанию (English, Deutsch, Français, Русский, аббревиатуры BK/C/M/Y)

---

## Структура проекта

```
├── app/
│   ├── main.py              # FastAPI entrypoint, lifespan
│   ├── models.py            # SQLModel модели (User, Printer)
│   ├── schemas.py           # Pydantic схемы запросов/ответов
│   ├── crud.py              # CRUD операции
│   ├── core/
│   │   ├── config.py        # Настройки (pydantic-settings, .env)
│   │   ├── db.py            # Engine, init_db (создание первого admin)
│   │   └── security.py      # JWT + bcrypt
│   ├── services/
│   │   └── snmp.py          # SNMP-сервис (стандартный MIB + Brother fallback)
│   └── api/
│       ├── deps.py          # Auth зависимости FastAPI
│       └── routes/
│           ├── auth.py      # Регистрация, логин
│           ├── users.py     # Управление пользователями
│           └── printers.py  # CRUD принтеров + SNMP-опрос
├── frontend/
│   ├── src/
│   │   ├── App.tsx          # Роутинг (React Router)
│   │   ├── auth.tsx         # Auth контекст (JWT в localStorage)
│   │   ├── client.ts        # API клиент (axios + interceptors)
│   │   ├── components/
│   │   │   ├── Layout.tsx       # Шапка, навигация
│   │   │   ├── PrinterCard.tsx  # Карточка принтера
│   │   │   ├── PrinterForm.tsx  # Форма добавления/редактирования
│   │   │   └── TonerBar.tsx     # Полоска уровня тонера
│   │   └── pages/
│   │       ├── Login.tsx        # Страница входа
│   │       └── Dashboard.tsx    # Главная: список принтеров, статистика
│   ├── Dockerfile           # Multi-stage: Node build → Nginx
│   └── nginx.conf           # SPA-роутинг + проксирование /api
├── alembic/                 # Миграции базы данных
├── scripts/
│   └── prestart.sh          # Запуск миграций + seed при старте контейнера
├── Dockerfile               # Backend: Python 3.14 + uv (multi-stage)
├── docker-compose.yml       # Production-стек
├── docker-compose.dev.yml   # Dev-оверрайды (порты, hot-reload)
├── .env.example             # Шаблон конфигурации
└── .github/workflows/ci.yml # CI/CD pipeline
```

---

## API

Интерактивная документация: `http://localhost/docs`

### Аутентификация

| Метод  | Путь                        | Описание               | Доступ  |
|--------|-----------------------------|------------------------|---------|
| `POST` | `/api/v1/auth/register`     | Регистрация            | Публично|
| `POST` | `/api/v1/auth/login`        | Вход (получить JWT)    | Публично|
| `POST` | `/api/v1/auth/test-token`   | Проверить токен        | Auth    |

### Пользователи

| Метод    | Путь                          | Описание             | Доступ |
|----------|-------------------------------|----------------------|--------|
| `GET`    | `/api/v1/users/me`            | Текущий пользователь | Auth   |
| `PATCH`  | `/api/v1/users/me`            | Обновить профиль     | Auth   |
| `PATCH`  | `/api/v1/users/me/password`   | Сменить пароль       | Auth   |
| `GET`    | `/api/v1/users/`              | Список пользователей | Admin  |
| `GET`    | `/api/v1/users/{id}`          | Пользователь по ID   | Admin  |
| `PATCH`  | `/api/v1/users/{id}`          | Изменить пользователя| Admin  |
| `DELETE` | `/api/v1/users/{id}`          | Удалить пользователя | Admin  |

### Принтеры

| Метод    | Путь                            | Описание                        | Доступ |
|----------|---------------------------------|---------------------------------|--------|
| `GET`    | `/api/v1/printers/`             | Список (фильтр по магазину)     | Auth   |
| `POST`   | `/api/v1/printers/`             | Добавить принтер                | Admin  |
| `GET`    | `/api/v1/printers/{id}`         | Принтер по ID                   | Auth   |
| `PATCH`  | `/api/v1/printers/{id}`         | Обновить принтер                | Admin  |
| `DELETE` | `/api/v1/printers/{id}`         | Удалить принтер                 | Admin  |
| `POST`   | `/api/v1/printers/{id}/poll`    | Опросить один принтер по SNMP   | Auth   |
| `POST`   | `/api/v1/printers/poll-all`     | Опросить все принтеры параллельно | Auth |

### Система

| Метод | Путь       | Описание        |
|-------|------------|-----------------|
| `GET` | `/health`  | Health check    |
| `GET` | `/docs`    | Swagger UI      |

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

1. Проверить, что SNMP включён на принтере (см. раздел [Настройка SNMP](#настройка-snmp-на-принтерах))
2. Проверить доступность UDP 161 с сервера:
   ```bash
   # На Linux/Mac
   nc -vzu <IP-принтера> 161
   ```
3. Убедиться, что community string в приложении совпадает с настройкой принтера (по умолчанию `public`)

### Принтер онлайн, но тонер не показывается (`—`)

- Принтер не поддерживает Printer MIB (RFC 3805) — только базовый SNMP
- Для Brother: убедитесь, что версия прошивки актуальная — старые версии иногда не отдают тонер по стандартному MIB
- Проверить логи backend: `docker compose logs backend | grep <IP-принтера>`

### Backend не запускается в режиме production

```
ValueError: SECRET_KEY must be set to a secure value in production
```
Необходимо задать `SECRET_KEY` в `.env`. Сгенерировать:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### SNMP работает с хоста, но не из Docker

По умолчанию Docker использует bridge-сеть с NAT. Если SNMP не работает из контейнера, добавьте в `docker-compose.yml` для backend:
```yaml
backend:
  network_mode: host   # только для Linux
```
На macOS и Windows Docker Desktop работает через виртуальную машину — `network_mode: host` недоступен. Принтеры в локальной сети будут доступны через Gateway хоста автоматически.

### Пересборка и перезапуск

```bash
docker compose down
docker compose up -d --build
```

### Просмотр логов

```bash
docker compose logs backend --tail=100 -f    # бэкенд
docker compose logs frontend --tail=50       # nginx
docker compose logs db --tail=30             # postgres
```
