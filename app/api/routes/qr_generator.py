from __future__ import annotations

import datetime
import io

from fastapi import APIRouter, Depends
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
        zip_bytes = qr_export_service.generate_zip(
            QRGeneratorParams(
                server=server,
                database=settings.QR_SQL_DATABASE,
                sql_login=settings.QR_SQL_LOGIN,
                sql_password=settings.QR_SQL_PASSWORD,
                airport_code=payload.airport_code,
                surnames=payload.surnames,
                add_login=payload.add_login,
                both_databases=both_databases,
            )
        )
    except Exception as exc:
        raise to_http_error(exc, operation="сформировать выгрузку") from exc

    filename = f"qr_export_{datetime.date.today().isoformat()}.zip"
    return StreamingResponse(
        io.BytesIO(zip_bytes),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
