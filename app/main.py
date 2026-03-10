import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator, metrics
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from sqlmodel import Session

from app.api.main import api_router
from app.core.config import settings
from app.core.db import engine, init_db
from app.core.limiter import limiter
from app.core.redis import close_redis, get_redis
from app.observability.tracing import setup_tracing
from app.services.event_log import write_event_log

logging.basicConfig(level=logging.INFO)
logging.getLogger("app").setLevel(logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    def _init_db_sync():
        with Session(engine) as session:
            init_db(session)

    await run_in_threadpool(_init_db_sync)
    yield
    await close_redis()


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)
setup_tracing(app, service_name="backend")

# Expose Prometheus metrics for service monitoring and alerting.
instrumentator = Instrumentator(
    should_group_status_codes=True,
    should_ignore_untemplated=True,
    excluded_handlers=["/metrics", "/health"],
)
instrumentator.add(metrics.requests())
instrumentator.add(metrics.latency())
instrumentator.add(metrics.request_size())
instrumentator.add(metrics.response_size())
instrumentator.instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Слишком много попыток. Повторите позже."},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    def _log_unhandled_exception():
        try:
            with Session(engine) as session:
                write_event_log(
                    session,
                    severity="critical",
                    category="system",
                    event_type="unhandled_exception",
                    message=f"{request.method} {request.url.path}: {exc}",
                )
                session.commit()
        except Exception:
            # Never fail the exception handler itself.
            logging.getLogger("app").exception("Failed to persist unhandled exception")

    await run_in_threadpool(_log_unhandled_exception)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/ready")
async def readiness_check():
    """Readiness probe for orchestrators and load balancers."""
    checks: dict[str, bool] = {"database": False, "redis": False}

    try:
        with Session(engine) as session:
            session.exec(text("SELECT 1")).one()
        checks["database"] = True
    except Exception:
        checks["database"] = False

    try:
        redis = await get_redis()
        await redis.ping()
        checks["redis"] = True
    except Exception:
        checks["redis"] = False

    if all(checks.values()):
        return {"status": "ready", "checks": checks}
    return JSONResponse(
        status_code=503,
        content={"status": "degraded", "checks": checks},
    )
