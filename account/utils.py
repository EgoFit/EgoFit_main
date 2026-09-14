from __future__ import annotations

import re
from itertools import islice
from typing import Iterable, Iterator, TypeVar

from django.http import HttpRequest

_DIGIT_TRANSLATION_TABLE = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
T = TypeVar("T")


def normalize_digits(value: str | None) -> str:
    if value is None:
        return ""
    return str(value).translate(_DIGIT_TRANSLATION_TABLE)


def normalize_phone_number(value: str | None) -> str:
    normalized = normalize_digits(value)
    normalized = re.sub(r"[^\d]", "", normalized)
    if normalized.startswith("0098") and len(normalized) >= 13:
        normalized = "0" + normalized[4:]
    elif normalized.startswith("98") and len(normalized) == 12:
        normalized = "0" + normalized[2:]
    elif len(normalized) == 10 and normalized.startswith("9"):
        normalized = "0" + normalized
    return normalized.strip()


def to_international_phone(value: str | None) -> str:
    normalized = normalize_phone_number(value)
    if len(normalized) == 11 and normalized.startswith("0"):
        return "98" + normalized[1:]
    return normalized


def is_valid_mobile_phone(value: str | None) -> bool:
    normalized = normalize_phone_number(value)
    return len(normalized) == 11 and normalized.isdigit() and normalized.startswith("09")


def iter_chunks(values: Iterable[T], chunk_size: int) -> Iterator[list[T]]:
    iterator = iter(values)
    while True:
        chunk = list(islice(iterator, chunk_size))
        if not chunk:
            return
        yield chunk


def build_notification_sms_message(notification, *, recipient_name: str | None = None) -> str:
    recipient = (recipient_name or "").strip()
    message = (getattr(notification, "message", "") or "").strip()
    if recipient:
        greeting = f"کاربر {recipient} عزیز"
    else:
        greeting = "کاربر عزیز"
    if message:
        return f"{greeting}\n\n{message}"
    return greeting


def get_client_ip(request: HttpRequest) -> str:
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "") or ""


def format_phone_display(phone: str | None) -> str:
    normalized = normalize_phone_number(phone)
    if len(normalized) == 11:
        return f"{normalized[:4]} {normalized[4:7]} {normalized[7:]}"
    return normalized


def combine_fullname(first_name: str | None, last_name: str | None) -> str:
    return f"{(first_name or '').strip()} {(last_name or '').strip()}".strip()


def calculate_age_from_jalali(birth_date_jalali: str | None) -> int | None:
    if not birth_date_jalali:
        return None
    import jdatetime

    parts = birth_date_jalali.replace("-", "/").split("/")
    if len(parts) != 3:
        return None
    try:
        year, month, day = (int(part) for part in parts)
        birth_date = jdatetime.date(year, month, day)
    except ValueError:
        return None
    today = jdatetime.date.today()
    age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
    return age if age >= 0 else None


def is_birthday_today(birth_date_jalali: str | None) -> bool:
    if not birth_date_jalali:
        return False
    import jdatetime

    parts = birth_date_jalali.replace("-", "/").split("/")
    if len(parts) != 3:
        return False
    today = jdatetime.date.today()
    return parts[1].zfill(2) == f"{today.month:02d}" and parts[2].zfill(2) == f"{today.day:02d}"


def ensure_session_key(request: HttpRequest) -> str:
    if request.session.session_key:
        return request.session.session_key
    request.session.modified = True
    return request.session.session_key or ""
