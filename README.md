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
  - дашборды Grafana (`overview`, `operations`, `worker`, `ml`);
  - SLO/error-budget и эксплуатационные алерты Prometheus.
- ML (self-learning foundation):
  - daily retrain и scoring в отдельном `ml-service`;
  - прогноз `days_to_replacement` по картриджам;
  - prediction риска offline (low/medium/high).
- Безопасность:
  - JWT + blacklist в Redis;
  - Argon2id;
  - rate-limit логина;
  - CORS whitelist;
  - HTTPS через Nginx.
- Frontend:
  - сортировка online выше offline;
  - фиксированное глобальное автообновление всех устройств раз в 15 минут (без переключателей).
- Kafka:
  - event-stream operational логов в топик `infrascope.events`;
  - UI для просмотра топиков и сообщений (`kafka-ui`).
- Service Flow UI:
  - интерактивная карта связей сервисов (как n8n-style canvas);
  - live node/edge статусы, timeline, deep links в Jaeger/Kafka.

---

## Технологический стек

- Backend: `FastAPI`, `SQLModel`, `Alembic`, `PostgreSQL 17`, `Redis`, `Celery`
- Network: `pysnmp-lextudio`, `paramiko`, `httpx`
- Frontend: `React`, `TypeScript`, `Vite`, `TanStack Query`
- Monitoring: `Prometheus`, `Grafana`, `prometheus-fastapi-instrumentator`
- Tracing: `OpenTelemetry`, `Jaeger`
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
./scripts/deploy.sh
```

Для Linux host-network режима (максимум точности ARP/MAC):

```bash
./scripts/deploy.sh --prod-network
```

### 3) Доступ

- Приложение: `https://infrascope.local` или `https://localhost`
- Swagger/OpenAPI: `https://localhost/docs`
- Prometheus: `http://127.0.0.1:9090` (по умолчанию bind на localhost)
- Grafana: `http://127.0.0.1:3000` (по умолчанию bind на localhost)
  - default: `admin` / `admin`
- Kafka UI: `http://127.0.0.1:8080`
- Jaeger (trace UI): `http://127.0.0.1:16686`
- Service Flow Map: `https://localhost/service-flow-map`

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
- `backend` — API gateway/orchestration, `/metrics`
- `worker` — Celery worker для тяжёлых фоновых задач
- `ml-service` — отдельный сервис обучения/скоринга ML + `/metrics`
- `polling-service` — отдельный runtime polling устройств + `/metrics`
- `discovery-service` — отдельный runtime discovery/scan + `/metrics`
- `network-control-service` — отдельный runtime control операций (Iconbit, switch write ops) + `/metrics`
- `kafka` — event bus для operational событий
- `kafka-ui` — web-интерфейс Kafka
- `jaeger` — distributed tracing (цепочки вызовов между сервисами)
- `db` — PostgreSQL
- `redis` — cache/locks/broker/backend
- `prometheus` — сбор метрик
- `grafana` — визуализация

### Plug-and-play service platform

Сервисная платформа переведена на descriptor-подход:

- каждый сервис описывается в `services/<service>/service.yaml`;
- topology для Service Flow берется из `services/catalog.yaml` (без hardcode);
- есть scaffold-генератор нового сервиса: `tools/scaffold/new_service.py`;
- есть schema validation: `tools/scaffold/validate_service_descriptors.py`;
- observability-артефакты (Prometheus targets/alerts + Grafana dashboard) автогенерируются из descriptor-ов: `tools/scaffold/generate_observability_assets.py`.

Добавление нового сервиса:

```bash
uv run python tools/scaffold/new_service.py --name inventory-service --port 8020
uv run python tools/scaffold/validate_service_descriptors.py
uv run python tools/scaffold/generate_observability_assets.py
```

Kubernetes-first артефакты:

- `infra/helm/base-service` — базовый chart;
- `infra/helm/services/*.values.yaml` — values по сервисам;
- `infra/k8s/overlays/{dev,staging,prod}` — env overlays;
- `infra/gitops/argocd-app.yaml` — gitops application example.

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
- ML:
  - `ML_ENABLED`, `ML_SERVICE_URL`
  - `POLLING_SERVICE_ENABLED`, `POLLING_SERVICE_URL`
  - `DISCOVERY_SERVICE_ENABLED`, `DISCOVERY_SERVICE_URL`
  - `NETWORK_CONTROL_SERVICE_ENABLED`, `NETWORK_CONTROL_SERVICE_URL`
  - `INTERNAL_SERVICE_TOKEN`
  - `KAFKA_ENABLED`, `KAFKA_BOOTSTRAP_SERVERS`, `KAFKA_EVENT_TOPIC`
  - `OTEL_ENABLED`, `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_SERVICE_NAMESPACE`
  - `PROMETHEUS_API_URL`, `JAEGER_API_URL`, `JAEGER_UI_URL`, `KAFKA_UI_URL`
  - `ML_MIN_TRAIN_ROWS`, `ML_RETRAIN_HOUR_UTC`, `ML_SCORE_INTERVAL_MINUTES`
- Monitoring:
  - `PROMETHEUS_BIND`, `PROMETHEUS_PORT`, `PROMETHEUS_RETENTION`
  - `GRAFANA_BIND`, `GRAFANA_PORT`, `GRAFANA_ADMIN_USER`, `GRAFANA_ADMIN_PASSWORD`
  - `KAFKA_UI_BIND`, `KAFKA_UI_PORT`
  - `JAEGER_BIND`, `JAEGER_PORT`

---

## API

Базовый префикс: `/api/v1`

- Auth/User: `/auth/*`, `/users/*`
- Printers: `/printers/*`, `/scanner/*` (printer discovery)
- Media Players: `/media-players/*`, `/media-players/discover/*`
- Switches: `/switches/*`, `/switches/discover/*`
- Tasks/Worker: `/tasks/*`
- ML API: `/ml/*`
- Observability API: `/observability/service-map`, `/observability/service-map/timeseries`
- System: `/health`, `/metrics`

Актуальная спецификация API: `https://localhost/docs`

---

## Наблюдаемость

- Grafana dashboards:
  - `infrascope-overview`
  - `infrascope-operations`
  - `infrascope-worker`
  - `infrascope-services-catalog` (generated from `services/*/service.yaml`)
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
- Для предсказуемого апдейта на сервере используйте `./scripts/deploy.sh` (с флагами `--prod-network`, `--no-pull` при необходимости).

### Kafka: как смотреть и пользоваться

После `./scripts/deploy.sh` Kafka уже поднята автоматически, отдельной ручной настройки не требуется.

1. Откройте UI: `http://127.0.0.1:8080`.
2. Выберите кластер `infrascope`.
3. Откройте топик `infrascope.events` — там operational события (offline/online, IP changes, critical errors и т.д.).

Важно: Kafka UI показывает топики/сообщения/consumer lag, но не полноценную карту связей сервисов.
Для визуализации цепочек "кто кого вызвал" используйте Jaeger.

CLI-проверка из контейнера Kafka:

```bash
docker compose exec kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:9092 --list
docker compose exec kafka /opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server kafka:9092 --topic infrascope.events --from-beginning
```

Создать тестовое сообщение:

```bash
docker compose exec kafka /opt/kafka/bin/kafka-console-producer.sh --bootstrap-server kafka:9092 --topic infrascope.events
```

### Tracing: карта связей между сервисами

После деплоя откройте `http://127.0.0.1:16686`:

1. Выберите сервис (`backend`, `polling-service`, `discovery-service`, `network-control-service`, `ml-service`).
2. Нажмите **Find Traces** и посмотрите end-to-end цепочку запроса.
3. Для переходов между API и Kafka используйте поле `trace_id` в сообщениях `infrascope.events`.

`trace_id` теперь публикуется в Kafka payload и может быть использован для склейки событий и трейсов.

Спецификация event-контракта: `docs/asyncapi.yml`.

### NetSupport Manager (автозапуск по hostname)

Для кнопки подключения к неттопу из UI нужен локальный Windows helper на ПК оператора.

1. Скопируйте папку `tools/windows/netsupport-helper` на рабочий Windows ПК.
2. Откройте PowerShell и запустите:

```powershell
powershell -ExecutionPolicy Bypass -File .\Install-InfraScopeNetSupportHelper.ps1
```

3. Проверьте протокол вручную (`Win + R`):

```text
infrascope-nsm://NETTOP-01
```

4. Если открылся NetSupport Manager, кнопка в интерфейсе InfraScope будет работать автоматически.

Удаление helper:

```powershell
powershell -ExecutionPolicy Bypass -File .\Uninstall-InfraScopeNetSupportHelper.ps1
```

---

## Обновление

```bash
git pull
docker compose up -d --build
```

Production smoke/contract check:

```bash
./scripts/smoke-contract.sh
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
