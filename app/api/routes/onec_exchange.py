from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_current_active_superuser
from app.schemas import OneCExchangeByBarcodeRequest, OneCExchangeByBarcodeResponse
from app.services.onec_exchange import exchange_product_docs_by_barcode

router = APIRouter(tags=["1c-exchange"])


@router.post(
    "/by-barcode",
    response_model=OneCExchangeByBarcodeResponse,
    dependencies=[Depends(get_current_active_superuser)],
)
async def run_exchange_by_barcode(payload: OneCExchangeByBarcodeRequest) -> OneCExchangeByBarcodeResponse:
    result = await exchange_product_docs_by_barcode(
        target=payload.target,
        barcode=payload.barcode,
        cash_register_hostnames=payload.cash_register_hostnames,
        source=payload.source,
    )
    return OneCExchangeByBarcodeResponse(**result)
