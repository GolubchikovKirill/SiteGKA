"""Client for Iconbit media player HTTP API (port 8081).

The device exposes a minimal HTML-based interface with Basic Auth.
Endpoints:
  GET /now        – currently playing track name (HTML fragment)
  GET /play       – start playback (302 redirect)
  GET /stop       – stop playback (302 redirect)
  GET /           – main page with file list table
  GET /delete?file=NAME  – delete a file
  GET /playlink?link=URL – play a URL/stream
  POST /upload    – upload a media file (multipart)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger(__name__)

ICONBIT_PORT = 8081
TIMEOUT = 8

AUTH_VARIANTS = [("Admin", "Admin"), ("admin", "admin")]


@dataclass
class IconbitStatus:
    now_playing: str | None = None
    is_playing: bool = False
    files: list[str] = field(default_factory=list)
    free_space: str | None = None


def _base_url(ip: str) -> str:
    return f"http://{ip}:{ICONBIT_PORT}"


def _try_get(url: str, **kwargs) -> httpx.Response | None:
    """Try GET with each auth variant, return first successful response."""
    for creds in AUTH_VARIANTS:
        try:
            resp = httpx.get(url, auth=creds, timeout=TIMEOUT, follow_redirects=True, **kwargs)
            if resp.status_code != 401:
                return resp
        except Exception:
            continue
    return None


def _try_post(url: str, **kwargs) -> httpx.Response | None:
    """Try POST with each auth variant, return first successful response."""
    for creds in AUTH_VARIANTS:
        try:
            resp = httpx.post(url, auth=creds, follow_redirects=True, **kwargs)
            if resp.status_code != 401:
                return resp
        except Exception:
            continue
    return None


def get_status(ip: str) -> IconbitStatus:
    """Fetch current playback status and file list."""
    status = IconbitStatus()
    base = _base_url(ip)

    now_resp = _try_get(f"{base}/now")
    if now_resp and now_resp.status_code == 200:
        text = now_resp.text.strip()
        match = re.search(r"<b>(.*?)</b>", text, re.IGNORECASE | re.DOTALL)
        if match:
            track = match.group(1).strip()
            if track and track.lower() not in ("", "none", "нет"):
                status.now_playing = track
                status.is_playing = True

    main_resp = _try_get(base)
    if main_resp and main_resp.status_code == 200:
        html = main_resp.text
        file_matches = re.findall(r'delete\?file=([^"&]+)', html, re.IGNORECASE)
        status.files = [f.strip() for f in file_matches if f.strip()]

        space_match = re.search(
            r"(\d+[\.,]?\d*\s*[GMKT]B)\s+available", html, re.IGNORECASE
        )
        if space_match:
            status.free_space = space_match.group(1)

    return status


def play(ip: str) -> bool:
    resp = _try_get(f"{_base_url(ip)}/play")
    return resp is not None and resp.status_code in (200, 302)


def stop(ip: str) -> bool:
    resp = _try_get(f"{_base_url(ip)}/stop")
    return resp is not None and resp.status_code in (200, 302)


def play_file(ip: str, filename: str) -> bool:
    resp = _try_get(f"{_base_url(ip)}/playlink", params={"link": filename})
    return resp is not None and resp.status_code in (200, 302)


def delete_file(ip: str, filename: str) -> bool:
    resp = _try_get(f"{_base_url(ip)}/delete", params={"file": filename})
    return resp is not None and resp.status_code in (200, 302)


def upload_file(ip: str, filename: str, content: bytes) -> bool:
    resp = _try_post(f"{_base_url(ip)}/upload", files={"file": (filename, content)}, timeout=60)
    return resp is not None and resp.status_code in (200, 302)


def delete_all_files(ip: str) -> bool:
    """Delete all files from the device."""
    status = get_status(ip)
    ok = True
    for f in status.files:
        if not delete_file(ip, f):
            ok = False
    return ok
