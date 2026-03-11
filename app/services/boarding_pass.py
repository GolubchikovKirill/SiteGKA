from __future__ import annotations

import datetime as dt
import io
import textwrap
from dataclasses import dataclass

from PIL import Image, ImageDraw

from app.schemas import BoardingPassRequest


@dataclass(frozen=True)
class GeneratedBoardingPassFile:
    filename: str
    content_type: str
    payload: str
    content: bytes


def _normalize_token(value: str | None, *, field_name: str, upper: bool = False) -> str:
    normalized = (value or "").strip()
    if not normalized:
        raise ValueError(f"{field_name} is required")
    return normalized.upper() if upper else normalized


def _resolve_day_in_year(payload: BoardingPassRequest) -> str:
    if payload.day_in_year:
        day = payload.day_in_year.strip()
        if not day.isdigit() or len(day) > 3:
            raise ValueError("day_in_year must contain up to 3 digits")
        return day.zfill(3)

    if not payload.flight_date:
        raise ValueError("flight_date or day_in_year is required")

    try:
        parsed = dt.date.fromisoformat(payload.flight_date)
    except ValueError as exc:
        raise ValueError("flight_date must use YYYY-MM-DD format") from exc
    return f"{parsed.timetuple().tm_yday:03d}"


def build_boarding_pass_payload(payload: BoardingPassRequest) -> str:
    if payload.raw_data:
        return payload.raw_data

    last_name = _normalize_token(payload.last_name, field_name="last_name", upper=True)
    first_name = _normalize_token(payload.first_name, field_name="first_name", upper=True)
    booking_ref = _normalize_token(payload.booking_ref, field_name="booking_ref", upper=True)
    from_code = _normalize_token(payload.from_code, field_name="from_code", upper=True)
    to_code = _normalize_token(payload.to_code, field_name="to_code", upper=True)
    flight_operator = _normalize_token(payload.flight_operator, field_name="flight_operator", upper=True)
    flight_number = _normalize_token(payload.flight_number, field_name="flight_number", upper=True)
    travel_class = _normalize_token(payload.travel_class, field_name="travel_class", upper=True)
    seat = _normalize_token(payload.seat, field_name="seat", upper=True)
    boarding_index = _normalize_token(payload.boarding_index, field_name="boarding_index", upper=True)
    day_in_year = _resolve_day_in_year(payload)

    # Compact BCBP-style text payload that is deterministic and easy to validate in tests.
    return (
        f"M1{last_name}/{first_name} "
        f"{booking_ref} "
        f"{from_code}{to_code}"
        f"{flight_operator}{flight_number}"
        f"{day_in_year}"
        f"{travel_class}"
        f"{seat}"
        f"{boarding_index}"
    )


def _render_payload_png(*, barcode_format: str, payload_text: str) -> bytes:
    image = Image.new("RGB", (1200, 500), "white")
    draw = ImageDraw.Draw(image)

    draw.rectangle((40, 40, 1160, 460), outline="black", width=4)
    draw.text((70, 70), f"BOARDING PASS {barcode_format.upper()}", fill="black")

    wrapped_lines = textwrap.wrap(payload_text, width=72) or [payload_text]
    for index, line in enumerate(wrapped_lines[:10]):
        draw.text((70, 140 + index * 30), line, fill="black")

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def generate_boarding_pass_file(payload: BoardingPassRequest) -> GeneratedBoardingPassFile:
    payload_text = build_boarding_pass_payload(payload)
    today = dt.date.today().isoformat()
    filename = f"boarding_pass_{payload.format}_{today}.png"
    content = _render_payload_png(barcode_format=payload.format, payload_text=payload_text)
    return GeneratedBoardingPassFile(
        filename=filename,
        content_type="image/png",
        payload=payload_text,
        content=content,
    )
