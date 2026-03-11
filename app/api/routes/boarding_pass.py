from __future__ import annotations

import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.api.deps import get_current_active_superuser
from app.schemas import BoardingPassRequest
from app.services.boarding_pass import generate_boarding_pass_file

router = APIRouter(tags=["boarding-pass"])


@router.post("/export", dependencies=[Depends(get_current_active_superuser)])
def export_boarding_pass(payload: BoardingPassRequest) -> StreamingResponse:
    try:
        generated = generate_boarding_pass_file(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Не удалось сформировать boarding pass: {exc}") from exc

    return StreamingResponse(
        io.BytesIO(generated.content),
        media_type=generated.content_type,
        headers={"Content-Disposition": f'attachment; filename="{generated.filename}"'},
    )
