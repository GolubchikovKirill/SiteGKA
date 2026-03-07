from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings


async def exchange_product_docs_by_barcode(
    *,
    target: str = "duty_free",
    barcode: str,
    cash_register_hostnames: list[str] | None = None,
    source: str = "infrascope",
) -> dict[str, Any]:
    target_to_url = {
        "duty_free": settings.ONEC_DUTY_FREE_API_URL or settings.ONEC_EXCHANGE_API_URL,
        "duty_paid": settings.ONEC_DUTY_PAID_API_URL or settings.ONEC_EXCHANGE_API_URL,
    }
    target_to_token = {
        "duty_free": settings.ONEC_DUTY_FREE_API_TOKEN or settings.ONEC_EXCHANGE_API_TOKEN,
        "duty_paid": settings.ONEC_DUTY_PAID_API_TOKEN or settings.ONEC_EXCHANGE_API_TOKEN,
    }
    api_url = target_to_url.get(target, "")
    api_token = target_to_token.get(target, "")

    if not api_url:
        target_human = "Duty Free" if target == "duty_free" else "Duty Paid"
        return {
            "target": target,
            "ok": False,
            "message": f"Не настроен URL API 1С для {target_human}. Укажите ONEC_DUTY_*_API_URL в .env.",
            "status_code": None,
            "request_id": None,
            "payload": None,
        }

    headers: dict[str, str] = {"Content-Type": "application/json"}
    if api_token:
        headers["Authorization"] = f"Bearer {api_token}"

    body = {
        "barcode": barcode,
        "cash_register_hostnames": cash_register_hostnames or [],
        "source": source,
        "target": target,
    }

    try:
        async with httpx.AsyncClient(timeout=settings.ONEC_EXCHANGE_TIMEOUT_SECONDS) as client:
            response = await client.post(api_url, json=body, headers=headers)
            request_id = response.headers.get("X-Request-ID") or response.headers.get("x-request-id")
            content_type = response.headers.get("content-type", "")
            payload: dict[str, Any] | None = None
            if "application/json" in content_type.lower():
                parsed = response.json()
                payload = parsed if isinstance(parsed, dict) else {"value": parsed}

            if response.is_success:
                return {
                    "target": target,
                    "ok": True,
                    "message": "Обмен с 1С выполнен успешно.",
                    "status_code": response.status_code,
                    "request_id": request_id,
                    "payload": payload,
                }

            detail = payload.get("detail") if isinstance(payload, dict) else None
            return {
                "target": target,
                "ok": False,
                "message": f"1С вернула ошибку ({response.status_code})" + (f": {detail}" if detail else ""),
                "status_code": response.status_code,
                "request_id": request_id,
                "payload": payload,
            }
    except httpx.HTTPError as exc:
        return {
            "target": target,
            "ok": False,
            "message": f"Не удалось выполнить запрос к 1С: {exc}",
            "status_code": None,
            "request_id": None,
            "payload": None,
        }
