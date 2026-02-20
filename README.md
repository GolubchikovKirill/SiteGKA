# SiteGKA

SaaS-проект на FastAPI + PostgreSQL, построенный по архитектуре [full-stack-fastapi-template](https://github.com/fastapi/full-stack-fastapi-template).

## Стек

- **FastAPI** — API-фреймворк
- **SQLModel** — ORM (SQLAlchemy + Pydantic)
- **PostgreSQL 17** — база данных
- **Alembic** — миграции
- **JWT (PyJWT)** — аутентификация
- **bcrypt** — хеширование паролей
- **Docker Compose** — контейнеризация БД

## Быстрый старт

```bash
# 1. Поднять PostgreSQL
docker compose up -d

# 2. Применить миграции
uv run alembic upgrade head

# 3. Запустить сервер
uv run uvicorn app.main:app --reload

# Swagger UI доступен по адресу:
# http://localhost:8000/docs
```

## Структура проекта

```
app/
├── main.py              # Entrypoint FastAPI
├── models.py            # SQLModel модели (User)
├── schemas.py           # Pydantic-схемы запросов/ответов
├── crud.py              # CRUD-операции
├── initial_data.py      # Seed первого суперюзера
├── core/
│   ├── config.py        # Настройки (pydantic-settings)
│   ├── db.py            # Database engine + init_db
│   └── security.py      # JWT + bcrypt
└── api/
    ├── main.py          # Главный роутер
    ├── deps.py          # Зависимости (сессия, текущий пользователь)
    └── routes/
        ├── auth.py      # /login, /register, /test-token
        └── users.py     # CRUD пользователей
alembic/                 # Миграции Alembic
docker-compose.yml       # PostgreSQL
.env                     # Переменные окружения (не коммитится)
```

## API эндпоинты

| Метод   | Путь                          | Описание                  | Доступ          |
|---------|-------------------------------|---------------------------|-----------------|
| POST    | `/api/v1/auth/register`       | Регистрация               | Публичный       |
| POST    | `/api/v1/auth/login`          | Получение JWT-токена      | Публичный       |
| POST    | `/api/v1/auth/test-token`     | Проверка токена           | Авторизованный  |
| GET     | `/api/v1/users/me`            | Текущий пользователь      | Авторизованный  |
| PATCH   | `/api/v1/users/me`            | Обновить свой профиль     | Авторизованный  |
| PATCH   | `/api/v1/users/me/password`   | Сменить пароль            | Авторизованный  |
| GET     | `/api/v1/users/`              | Список пользователей      | Суперюзер       |
| GET     | `/api/v1/users/{id}`          | Пользователь по ID        | Суперюзер       |
| PATCH   | `/api/v1/users/{id}`          | Обновить пользователя     | Суперюзер       |
| DELETE  | `/api/v1/users/{id}`          | Удалить пользователя      | Суперюзер       |
| GET     | `/health`                     | Healthcheck               | Публичный       |

## Переменные окружения

Задаются в `.env`:

```
SECRET_KEY=your-secret-key
POSTGRES_SERVER=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=sitegka
FIRST_SUPERUSER_EMAIL=admin@sitegka.com
FIRST_SUPERUSER_PASSWORD=changethis
```
