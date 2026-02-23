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


@dataclass
class IconbitStatus:
    now_playing: str | None = None
    is_playing: bool = False
    files: list[str] = field(default_factory=list)
    free_space: str | None = None


def _base_url(ip: str) -> str:
    return f"http://{ip}:{ICONBIT_PORT}"


def _auth() -> tuple[str, str]:
    return ("admin", "admin")


def get_status(ip: str) -> IconbitStatus:
    """Fetch current playback status and file list."""
    status = IconbitStatus()
    base = _base_url(ip)

    try:
        now_resp = httpx.get(
            f"{base}/now", auth=_auth(), timeout=TIMEOUT, follow_redirects=True
        )
        if now_resp.status_code == 200:
            text = now_resp.text.strip()
            match = re.search(r"<b>(.*?)</b>", text, re.IGNORECASE | re.DOTALL)
            if match:
                track = match.group(1).strip()
                if track and track.lower() not in ("", "none", "нет"):
                    status.now_playing = track
                    status.is_playing = True
    except Exception as e:
        logger.debug("Iconbit /now failed for %s: %s", ip, e)

    try:
        main_resp = httpx.get(
            base, auth=_auth(), timeout=TIMEOUT, follow_redirects=True
        )
        if main_resp.status_code == 200:
            html = main_resp.text
            file_matches = re.findall(
                r'delete\?file=([^"&]+)', html, re.IGNORECASE
            )
            status.files = [f.strip() for f in file_matches if f.strip()]

            space_match = re.search(
                r"(\d+[\.,]?\d*\s*[GMKT]B)\s+available", html, re.IGNORECASE
            )
            if space_match:
                status.free_space = space_match.group(1)
    except Exception as e:
        logger.debug("Iconbit main page failed for %s: %s", ip, e)

    return status


def play(ip: str) -> bool:
    """Start playback. Returns True on success."""
    try:
        resp = httpx.get(
            f"{_base_url(ip)}/play",
            auth=_auth(),
            timeout=TIMEOUT,
            follow_redirects=True,
        )
        return resp.status_code in (200, 302)
    except Exception as e:
        logger.warning("Iconbit play failed for %s: %s", ip, e)
        return False


def stop(ip: str) -> bool:
    """Stop playback. Returns True on success."""
    try:
        resp = httpx.get(
            f"{_base_url(ip)}/stop",
            auth=_auth(),
            timeout=TIMEOUT,
            follow_redirects=True,
        )
        return resp.status_code in (200, 302)
    except Exception as e:
        logger.warning("Iconbit stop failed for %s: %s", ip, e)
        return False


def play_file(ip: str, filename: str) -> bool:
    """Play a specific file by name via /playlink."""
    try:
        resp = httpx.get(
            f"{_base_url(ip)}/playlink",
            params={"link": filename},
            auth=_auth(),
            timeout=TIMEOUT,
            follow_redirects=True,
        )
        return resp.status_code in (200, 302)
    except Exception as e:
        logger.warning("Iconbit play_file failed for %s: %s", ip, e)
        return False


def delete_file(ip: str, filename: str) -> bool:
    """Delete a file from the device."""
    try:
        resp = httpx.get(
            f"{_base_url(ip)}/delete",
            params={"file": filename},
            auth=_auth(),
            timeout=TIMEOUT,
            follow_redirects=True,
        )
        return resp.status_code in (200, 302)
    except Exception as e:
        logger.warning("Iconbit delete_file failed for %s: %s", ip, e)
        return False


def upload_file(ip: str, filename: str, content: bytes) -> bool:
    """Upload a media file to the device."""
    try:
        resp = httpx.post(
            f"{_base_url(ip)}/upload",
            files={"file": (filename, content)},
            auth=_auth(),
            timeout=60,
            follow_redirects=True,
        )
        return resp.status_code in (200, 302)
    except Exception as e:
        logger.warning("Iconbit upload failed for %s: %s", ip, e)
        return False
