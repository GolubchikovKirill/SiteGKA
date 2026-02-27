from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(tags=["support-tools"])

_TOOLS_DIR = Path(__file__).resolve().parents[3] / "tools" / "windows" / "netsupport-helper"
_ALLOWED_FILES = {
    "Install-InfraScopeNetSupportHelper.ps1",
    "NetSupportUriHandler.ps1",
    "Uninstall-InfraScopeNetSupportHelper.ps1",
}


@router.get("/netsupport-helper/{filename}")
def download_netsupport_helper(filename: str) -> FileResponse:
    if filename not in _ALLOWED_FILES:
        raise HTTPException(status_code=404, detail="File not found")
    file_path = _TOOLS_DIR / filename
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        path=file_path,
        media_type="text/plain; charset=utf-8",
        filename=filename,
    )
