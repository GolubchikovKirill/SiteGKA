# InfraScope

InfraScope — платформа мониторинга инфраструктуры магазинов: принтеры, медиаплееры (Iconbit/неттопы), сетевые свитчи, сетевой discovery, массовые операции, наблюдаемость и алерты.

Проект ориентирован на production: отказоустойчивый polling, Redis/worker, ограничение параллелизма, мониторинг через Prometheus + Grafana.

## Возможности

- Мониторинг принтеров:
  - лазерные (SNMP, тонер K/C/M/Y, MAC-верификация, DHCP-resilience);
  - этикеточные (IP или USB-режим).
- Мониторинг медиаплееров:
  - Iconbit (порт `8081`, статус, плейлист/файлы, remote и bulk операции);
  - неттопы/Twix (онлайн/офлайн и сетевые данные).
- Мониторинг свитчей:
  - универсально через SNMP (online, hostname, uptime, порты где доступно);
  - Cisco-дополнения через SSH (AP/PoE/reboot, управление портами).
- Discovery по сети:
  - отдельные режимы для принтеров, медиаплееров, свитчей;
  - умная фильтрация типов устройств, чтобы уменьшить ложные совпадения.
- Отказоустойчивость:
  - lock от дублирующих `poll-all`;
  - state machine подтверждения офлайна;
  - circuit breaker;
  - jitter;
  - MAC/IP rediscovery.
- Наблюдаемость:
  - `/metrics` на backend и worker;
  - дашборды Grafana (`overview`, `operations`, `worker`);
  - SLO/error-budget и эксплуатационные алерты Prometheus.
- Безопасность:
  - JWT + blacklist в Redis;
  - Argon2id;
  - rate-limit логина;
  - CORS whitelist;
  - HTTPS через Nginx.
- Frontend:
  - сортировка online выше offline;
  - фиксированное глобальное автообновление всех устройств раз в 15 минут (без переключателей).

---

## Технологический стек

- Backend: `FastAPI`, `SQLModel`, `Alembic`, `PostgreSQL 17`, `Redis`, `Celery`
- Network: `pysnmp-lextudio`, `paramiko`, `httpx`
- Frontend: `React`, `TypeScript`, `Vite`, `TanStack Query`
- Monitoring: `Prometheus`, `Grafana`, `prometheus-fastapi-instrumentator`
- Infra: `Docker Compose`, `Nginx` (TLS termination)

---

## Запуск в production

### 1) Подготовка

```bash
git clone https://github.com/GolubchikovKirill/SiteGKA.git
cd SiteGKA
cp .env.example .env
```

Заполните минимум:

- `SECRET_KEY`
- `POSTGRES_PASSWORD`
- `FIRST_SUPERUSER_PASSWORD`
- `SCAN_SUBNET` (подсети для discovery/scan)

### 2) Старт

```bash
docker compose up -d --build
```

### 3) Доступ

- Приложение: `https://infrascope.local` или `https://localhost`
- Swagger/OpenAPI: `https://localhost/docs`
- Prometheus: `http://127.0.0.1:9090` (по умолчанию bind на localhost)
- Grafana: `http://127.0.0.1:3000` (по умолчанию bind на localhost)
  - default: `admin` / `admin`

> Для доступа по LAN настройте `HOST_IP`, hosts/DNS и при необходимости `PROMETHEUS_BIND` / `GRAFANA_BIND`.

---

## Dev-режим

```bash
docker compose up db redis -d
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload

cd frontend
npm install
npm run dev
```

Локальный frontend: `http://localhost:5173`

Если нужен dev-compose с пробросом портов:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
```

---

## Архитектура сервисов

- `frontend` — SPA + Nginx + HTTPS
- `backend` — API, бизнес-логика, polling/discovery, `/metrics`
- `worker` — Celery worker для тяжёлых фоновых задач
- `db` — PostgreSQL
- `redis` — cache/locks/broker/backend
- `prometheus` — сбор метрик
- `grafana` — визуализация

---

## Ключевые переменные окружения

Полный список в `.env.example`.

- База/безопасность:
  - `ENVIRONMENT`, `SECRET_KEY`
  - `POSTGRES_*`
  - `REDIS_URL`
  - `FIRST_SUPERUSER_*`
- Сканирование/сеть:
  - `SCAN_SUBNET`, `SCAN_PORTS`
  - `SCAN_MAX_HOSTS`, `SCAN_TCP_TIMEOUT`, `SCAN_TCP_RETRIES`, `SCAN_TCP_CONCURRENCY`
- Poll resilience:
  - `POLL_JITTER_MAX_MS`
  - `POLL_OFFLINE_CONFIRMATIONS`
  - `POLL_CIRCUIT_FAILURE_THRESHOLD`
  - `POLL_CIRCUIT_OPEN_SECONDS`
  - `POLL_RESILIENCE_STATE_TTL_SECONDS`
- Worker:
  - `WORKER_CONCURRENCY`, `WORKER_POOL`, `WORKER_METRICS_PORT`
- Monitoring:
  - `PROMETHEUS_BIND`, `PROMETHEUS_PORT`, `PROMETHEUS_RETENTION`
  - `GRAFANA_BIND`, `GRAFANA_PORT`, `GRAFANA_ADMIN_USER`, `GRAFANA_ADMIN_PASSWORD`

---

## API

Базовый префикс: `/api/v1`

- Auth/User: `/auth/*`, `/users/*`
- Printers: `/printers/*`, `/scanner/*` (printer discovery)
- Media Players: `/media-players/*`, `/media-players/discover/*`
- Switches: `/switches/*`, `/switches/discover/*`
- Tasks/Worker: `/tasks/*`
- System: `/health`, `/metrics`

Актуальная спецификация API: `https://localhost/docs`

---

## Наблюдаемость

- Grafana dashboards:
  - `infrascope-overview`
  - `infrascope-operations`
  - `infrascope-worker`
- Алерты Prometheus покрывают:
  - backend/worker down;
  - API 5xx и latency;
  - error-budget burn (fast/slow);
  - high offline ratio / device availability SLO;
  - всплески SNMP/SSH/port-operation ошибок;
  - всплески `circuit_opened`.

---

## Эксплуатационные заметки

- Глобальное автообновление фронта: фиксированные 15 минут для всех устройств.
- Массовые polling-ручки защищены от спама повторными кликами.
- Для Linux можно использовать `docker-compose.prod.yml` (host network), если нужна максимальная точность ARP-сценариев.
- Для macOS/Windows (Docker Desktop VM) больше опирайтесь на SNMP/HTTP fingerprint, чем на ARP.

---

## Обновление

```bash
git pull
docker compose up -d --build
```

## Логи

```bash
docker compose logs backend --tail=200 -f
docker compose logs worker --tail=200 -f
docker compose logs frontend --tail=100 -f
docker compose logs prometheus --tail=100
docker compose logs grafana --tail=100
```

---

## Лицензия

Внутренний проект.
