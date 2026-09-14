from __future__ import annotations

import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


def normalize_phone_number(value: str) -> str:
    return re.sub(r"[\s\-()+]", "", (value or "").strip())


def validate_comment_name(value: str) -> str:
    name = (value or "").strip()
    if len(name) < 3:
        raise ValidationError(_("نام باید حداقل ۳ کاراکتر باشد."))
    return name


def validate_comment_text(value: str) -> str:
    comment = (value or "").strip()
    if len(comment) < 10:
        raise ValidationError(_("متن پیام باید حداقل ۱۰ کاراکتر باشد."))
    return comment


def validate_phone_number(value: str) -> str:
    phone = normalize_phone_number(value)
    if not phone:
        return ""
    if not phone.isdigit() or len(phone) < 8:
        raise ValidationError(_("شماره تماس معتبر نیست."))
    return phone


def validate_series_comment_text(value: str) -> str:
    text = (value or "").strip()
    if len(text) < 5:
        raise ValidationError(_("متن دیدگاه باید حداقل ۵ کاراکتر باشد."))
    return text


def validate_reply_text(value: str) -> str:
    text = (value or "").strip()
    if len(text) < 3:
        raise ValidationError(_("متن پاسخ باید حداقل ۳ کاراکتر باشد."))
    return text
