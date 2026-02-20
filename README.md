# InfraScope

IT infrastructure monitoring and administration platform. Built with FastAPI, React, PostgreSQL.

## Features

- **Printer Monitoring** — SNMP-based polling of HP, Ricoh, Kyocera and other corporate printers. Track online status and CMYK toner levels across all locations.
- **User Management** — JWT authentication, role-based access (admin/user).
- **Extensible** — designed to grow with new monitoring modules (network, servers, etc).

## Tech Stack

| Layer      | Technology                                                    |
|------------|---------------------------------------------------------------|
| Backend    | FastAPI, SQLModel, PostgreSQL, Alembic, SNMP (pysnmp)         |
| Frontend   | React, TypeScript, Vite, Tailwind CSS, TanStack Query         |
| Infra      | Docker Compose, Nginx, GitHub Actions CI/CD                   |

## Quick Start

### Full stack (Docker)

```bash
cp .env.example .env
# Edit .env — set SECRET_KEY, POSTGRES_PASSWORD, FIRST_SUPERUSER_PASSWORD

docker compose up -d --build
# App available at http://localhost
```

### Development

```bash
# 1. Start PostgreSQL
docker compose -f docker-compose.yml -f docker-compose.dev.yml up db -d

# 2. Backend (port 8000)
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload

# 3. Frontend (port 5173, proxies /api → backend)
cd frontend && npm install && npm run dev
```

## Project Structure

```
├── app/
│   ├── main.py              # FastAPI entrypoint
│   ├── models.py            # SQLModel models (User, Printer)
│   ├── schemas.py           # Pydantic request/response schemas
│   ├── crud.py              # User CRUD operations
│   ├── core/
│   │   ├── config.py        # Settings (pydantic-settings, .env)
│   │   ├── db.py            # Engine, init_db
│   │   └── security.py      # JWT + bcrypt
│   ├── services/
│   │   └── snmp.py          # Printer SNMP polling
│   └── api/
│       ├── deps.py          # Auth dependencies
│       └── routes/
│           ├── auth.py      # Register, login
│           ├── users.py     # User management
│           └── printers.py  # Printer CRUD + SNMP
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── auth.tsx         # Auth context
│   │   ├── client.ts        # API client (axios)
│   │   ├── components/      # Layout, PrinterCard, TonerBar, PrinterForm
│   │   └── pages/           # Login, Dashboard
│   ├── Dockerfile           # Multi-stage (Node build → Nginx)
│   └── nginx.conf           # Serve SPA + proxy API
├── alembic/                 # Database migrations
├── scripts/
│   └── prestart.sh          # Run migrations + seed on startup
├── Dockerfile               # Backend image (Python 3.14 + uv)
├── docker-compose.yml       # Production stack
├── docker-compose.dev.yml   # Dev overrides
├── .env.example             # Configuration template
└── .github/workflows/ci.yml # CI/CD pipeline
```

## API Endpoints

### Auth
| Method | Path                       | Description        | Access     |
|--------|----------------------------|--------------------|------------|
| POST   | `/api/v1/auth/register`    | Register           | Public     |
| POST   | `/api/v1/auth/login`       | Login (get JWT)    | Public     |
| POST   | `/api/v1/auth/test-token`  | Verify token       | Auth       |

### Users
| Method | Path                          | Description        | Access     |
|--------|-------------------------------|--------------------|------------|
| GET    | `/api/v1/users/me`            | Current user       | Auth       |
| PATCH  | `/api/v1/users/me`            | Update profile     | Auth       |
| PATCH  | `/api/v1/users/me/password`   | Change password    | Auth       |
| GET    | `/api/v1/users/`              | List users         | Admin      |
| GET    | `/api/v1/users/{id}`          | User by ID         | Admin      |
| PATCH  | `/api/v1/users/{id}`          | Update user        | Admin      |
| DELETE | `/api/v1/users/{id}`          | Delete user        | Admin      |

### Printers
| Method | Path                              | Description          | Access     |
|--------|-----------------------------------|----------------------|------------|
| GET    | `/api/v1/printers/`               | List printers        | Auth       |
| POST   | `/api/v1/printers/`               | Add printer          | Admin      |
| GET    | `/api/v1/printers/{id}`           | Printer by ID        | Auth       |
| PATCH  | `/api/v1/printers/{id}`           | Update printer       | Admin      |
| DELETE | `/api/v1/printers/{id}`           | Delete printer       | Admin      |
| POST   | `/api/v1/printers/{id}/poll`      | Poll single printer  | Auth       |
| POST   | `/api/v1/printers/poll-all`       | Poll all printers    | Auth       |

## CI/CD

GitHub Actions pipeline on every push/PR to `main`:
1. **Backend Lint** — Ruff check + format
2. **Backend Test** — Pytest against PostgreSQL service
3. **Frontend Build** — TypeScript check + Vite production build
4. **Docker Build** — Build backend + frontend images (on push to main)

## License

Private / Proprietary
