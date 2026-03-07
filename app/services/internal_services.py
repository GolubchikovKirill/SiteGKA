from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException

from app.core.config import settings
from app.observability.metrics import observe_service_edge

_SAFE_RETRY_METHODS = {"GET", "HEAD", "OPTIONS"}
_RETRYABLE_STATUS_CODES = {502, 503, 504}


def _headers() -> dict[str, str]:
    if settings.INTERNAL_SERVICE_TOKEN:
        return {"X-Internal-Token": settings.INTERNAL_SERVICE_TOKEN}
    return {}


async def _proxy_request(
    *,
    base_url: str,
    method: str,
    path: str,
    timeout: float | None = None,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
    files: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}{path}"
    target = (urlparse(base_url).hostname or "unknown").strip() or "unknown"
    normalized_method = method.upper().strip()
    request_timeout = timeout if timeout is not None else settings.INTERNAL_HTTP_TIMEOUT_SECONDS
    retries = settings.INTERNAL_HTTP_RETRIES if normalized_method in _SAFE_RETRY_METHODS else 0
    backoff = max(settings.INTERNAL_HTTP_RETRY_BACKOFF_SECONDS, 0.0)
    attempts = max(0, retries) + 1

    for attempt in range(1, attempts + 1):
        try:
            with observe_service_edge(
                source="backend",
                target=target,
                transport="http",
                operation=f"{normalized_method} {path}",
            ):
                async with httpx.AsyncClient(timeout=request_timeout) as client:
                    response = await client.request(
                        method=normalized_method,
                        url=url,
                        params=params,
                        json=json_body,
                        data=data,
                        files=files,
                        headers=_headers(),
                    )
            response.raise_for_status()
            data = response.json()
            if isinstance(data, dict):
                return data
            raise HTTPException(status_code=502, detail="internal service returned invalid payload")
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code if exc.response is not None else None
            should_retry = status in _RETRYABLE_STATUS_CODES and attempt < attempts
            if should_retry:
                await asyncio.sleep(backoff * attempt)
                continue
            detail = exc.response.text if exc.response is not None else "internal service status error"
            raise HTTPException(status_code=502, detail=detail) from exc
        except httpx.HTTPError as exc:
            if attempt < attempts:
                await asyncio.sleep(backoff * attempt)
                continue
            raise HTTPException(status_code=502, detail=f"internal service unavailable: {exc}") from exc
    raise HTTPException(status_code=502, detail="internal service unavailable")


async def maybe_proxy(
    *,
    enabled: bool,
    call: Callable[[], Any],
) -> Any:
    if enabled:
        return await call()
    return None
