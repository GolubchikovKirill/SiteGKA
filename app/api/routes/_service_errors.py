from __future__ import annotations

from fastapi import HTTPException


def to_http_error(exc: Exception, *, operation: str) -> HTTPException:
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc))
    return HTTPException(status_code=502, detail=f"Не удалось {operation}: {exc}")
