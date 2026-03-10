# InfraScope — Agent Context

## Project Overview
IT infrastructure monitoring and administration platform.

## Stack
- **Backend**: Python 3.13, FastAPI, SQLModel, PostgreSQL, Redis, Celery, OpenTelemetry
- **Frontend**: React 19, TypeScript, Vite, TailwindCSS v4, React Router v7, TanStack Query v5
- **Infra**: Docker Compose, Prometheus, Grafana, Jaeger (OTLP tracing)
- **Package managers**: `uv` (Python), `npm` (JS)

## Project Structure
```
app/         → FastAPI backend (Python)
├── api/     → Route handlers
├── core/    → Config, DB, Redis, auth, security
├── models/  → SQLModel ORM models
├── services/→ Business logic services
├── worker/  → Celery tasks
├── ml/      → ML services
└── observability/ → Tracing setup

frontend/    → React frontend (TypeScript)
├── src/
│   ├── api/         → API client (axios)
│   ├── components/  → UI components
│   └── pages/       → Route pages

alembic/     → DB migrations
tests/       → pytest tests
```

## Conventions
- **Python**: Use Ruff for linting + formatting. All imports organized by isort. Type annotations required.
- **TypeScript**: Strict mode. Prettier for formatting.
- **API**: FastAPI with Pydantic v2 schemas. REST API under `/api/v1/`.
- **DB**: SQLModel (SQLAlchemy 2.0 syntax). Migrations via Alembic.
- **Auth**: JWT tokens (PyJWT). Argon2 password hashing.
- **Tests**: pytest + pytest-asyncio for backend, vitest + playwright for frontend.

## Local Setup
```bash
uv sync          # Install Python deps
cd frontend && npm install  # Install JS deps
docker compose up -d db redis  # Start DB + Redis
uv run alembic upgrade head    # Run migrations
uv run uvicorn app.main:app --reload  # Start API
```

## Key Files
- `app/core/config.py` — all settings (loaded from `.env`)
- `app/core/db.py` — DB engine + session
- `app/core/redis.py` — Redis client
- `app/services/event_log.py` — audit event logging
- `pyproject.toml` — Python deps + Ruff config
