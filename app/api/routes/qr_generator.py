from __future__ import annotations

import datetime
import io
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.api.deps import get_current_active_superuser
from app.api.routes._service_errors import to_http_error
from app.core.config import settings
from app.schemas import QRGeneratorRequest
from app.services.qr_generator import QRGeneratorParams, QrExportService

router = APIRouter(tags=["qr-generator"])
qr_export_service = QrExportService()


@router.post("/export", dependencies=[Depends(get_current_active_superuser)])
def export_qr_docs(payload: QRGeneratorRequest) -> StreamingResponse:
    both_databases = payload.db_mode == "both"
    server = (
        "DC1-SRV-KC02.regstaer.local"
        if payload.db_mode == "duty_paid"
        else "DC1-SRV-KC01.regstaer.local"
    )
    try:
        params = QRGeneratorParams(
            server=server,
            database=settings.QR_SQL_DATABASE,
            sql_login=settings.QR_SQL_LOGIN,
            sql_password=settings.QR_SQL_PASSWORD,
            airport_code=payload.airport_code,
            surnames=payload.surnames,
            add_login=payload.add_login,
            both_databases=both_databases,
        )
        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(qr_export_service.generate_zip, params)
        try:
            zip_bytes = future.result(timeout=settings.QR_SQL_TIMEOUT_SECONDS)
        finally:
            executor.shutdown(wait=False, cancel_futures=True)
    except FuturesTimeoutError as exc:
        raise HTTPException(
            status_code=504,
            detail=(
                "Выгрузка QR превысила таймаут SQL. "
                "Проверьте доступность MSSQL и уменьшите объем выборки."
            ),
        ) from exc
    except Exception as exc:
        raise to_http_error(exc, operation="сформировать выгрузку") from exc

    filename = f"qr_export_{datetime.date.today().isoformat()}.zip"
    return StreamingResponse(
        io.BytesIO(zip_bytes),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
