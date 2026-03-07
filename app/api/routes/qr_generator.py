from __future__ import annotations

import datetime
import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.api.deps import get_current_active_superuser
from app.core.config import settings
from app.schemas import QRGeneratorRequest
from app.services.qr_generator import QRGeneratorParams, generate_qr_docs_zip

router = APIRouter(tags=["qr-generator"])


@router.post("/export", dependencies=[Depends(get_current_active_superuser)])
def export_qr_docs(payload: QRGeneratorRequest) -> StreamingResponse:
    both_databases = payload.db_mode == "both"
    server = (
        "DC1-SRV-KC02.regstaer.local"
        if payload.db_mode == "duty_paid"
        else "DC1-SRV-KC01.regstaer.local"
    )
    try:
        zip_bytes = generate_qr_docs_zip(
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
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Не удалось сформировать выгрузку: {exc}") from exc

    filename = f"qr_export_{datetime.date.today().isoformat()}.zip"
    return StreamingResponse(
        io.BytesIO(zip_bytes),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
