from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx
from fastapi import HTTPException

from app.core.config import settings

DEFAULT_TIMEOUT = 180.0


def _headers() -> dict[str, str]:
    if settings.INTERNAL_SERVICE_TOKEN:
        return {"X-Internal-Token": settings.INTERNAL_SERVICE_TOKEN}
    return {}


async def _proxy_request(
    *,
    base_url: str,
    method: str,
    path: str,
    timeout: float = DEFAULT_TIMEOUT,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
    files: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}{path}"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.request(
                method=method,
                url=url,
                params=params,
                json=json_body,
                data=data,
                files=files,
                headers=_headers(),
            )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text if exc.response is not None else "internal service status error"
        raise HTTPException(status_code=502, detail=detail) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"internal service unavailable: {exc}") from exc
    data = response.json()
    if isinstance(data, dict):
        return data
    raise HTTPException(status_code=502, detail="internal service returned invalid payload")


async def maybe_proxy(
    *,
    enabled: bool,
    call: Callable[[], Any],
) -> Any:
    if enabled:
        return await call()
    return None
