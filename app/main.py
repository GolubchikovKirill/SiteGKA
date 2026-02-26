import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator, metrics
from slowapi.errors import RateLimitExceeded
from sqlmodel import Session

from app.api.main import api_router
from app.core.config import settings
from app.core.db import engine, init_db
from app.core.limiter import limiter
from app.core.redis import close_redis
from app.services.event_log import write_event_log

logging.basicConfig(level=logging.INFO)
logging.getLogger("app").setLevel(logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    with Session(engine) as session:
        init_db(session)
    yield
    await close_redis()


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

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
    with Session(engine) as session:
        write_event_log(
            session,
            severity="critical",
            category="system",
            event_type="unhandled_exception",
            message=f"{request.method} {request.url.path}: {exc}",
        )
        session.commit()
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
