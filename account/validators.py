from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _

from account.utils import normalize_phone_number

PHONE_NUMBER_VALIDATOR = RegexValidator(
    regex=r"^\d{11}$",
    message=_("شماره تلفن باید 11 رقم باشد."),
    code="invalid_phone_number",
)

OTP_CODE_VALIDATOR = RegexValidator(
    regex=r"^\d{5}$",
    message=_("لطفا کد 5 رقمی وارد کنید."),
    code="invalid_otp_code",
)

IMAGE_UPLOAD_TYPES = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
    "gif": "image/gif",
}
VIDEO_UPLOAD_TYPES = {
    "mp4": {"video/mp4"},
    "webm": {"video/webm"},
    "mov": {"video/quicktime"},
    "m4v": {"video/x-m4v", "video/mp4"},
    "ogv": {"video/ogg"},
}
AUDIO_UPLOAD_TYPES = {
    "mp3": {"audio/mpeg", "audio/mp3"},
    "wav": {"audio/wav", "audio/x-wav"},
    "ogg": {"audio/ogg"},
    "m4a": {"audio/mp4", "audio/x-m4a"},
    "aac": {"audio/aac"},
}


def validate_upload(
    uploaded_file,
    *,
    allowed_extensions,
    allowed_content_types,
    extension_content_types=None,
    max_bytes=None,
    message=None,
):
    """Validate an upload using an extension and an exact MIME allowlist."""
    if not uploaded_file:
        return uploaded_file

    if max_bytes is None:
        max_bytes = int(getattr(settings, "MAX_UPLOAD_SIZE", 100 * 1024 * 1024))
    if getattr(uploaded_file, "size", 0) > max_bytes:
        raise ValidationError(_("حجم فایل از حد مجاز بیشتر است."))

    filename = str(getattr(uploaded_file, "name", "") or "")
    if "\x00" in filename:
        raise ValidationError(_("نام فایل نامعتبر است."))
    extension = Path(filename).suffix.lower().lstrip(".")
    content_type = (getattr(uploaded_file, "content_type", "") or "").lower().strip()

    # Do not rely solely on client-controlled MIME metadata. Reject obvious
    # markup payloads even when an attacker spoofs an image MIME type.
    try:
        current_position = uploaded_file.tell()
        sample = uploaded_file.read(4096)
        uploaded_file.seek(current_position)
    except (AttributeError, OSError):
        sample = b""
    if sample.lstrip().lower().startswith(
        (b"<!doctype html", b"<html", b"<script", b"<svg", b"<?xml")
    ):
        raise ValidationError(_("فایل‌های HTML یا محتوای نشانه‌گذاری‌شده مجاز نیستند."))

    allowed_extensions = {item.lower().lstrip(".") for item in allowed_extensions}
    allowed_content_types = {item.lower() for item in allowed_content_types}
    if extension not in allowed_extensions or content_type not in allowed_content_types:
        raise ValidationError(message or _("نوع فایل مجاز نیست."))
    if extension_content_types and content_type not in extension_content_types.get(extension, set()):
        raise ValidationError(message or _("نوع فایل مجاز نیست."))
    return uploaded_file


def validate_image_upload(uploaded_file):
    return validate_upload(
        uploaded_file,
        allowed_extensions=IMAGE_UPLOAD_TYPES,
        allowed_content_types=set(IMAGE_UPLOAD_TYPES.values()),
        extension_content_types={extension: {mime} for extension, mime in IMAGE_UPLOAD_TYPES.items()},
        message=_("فقط تصاویر JPG، PNG، WEBP یا GIF مجاز هستند."),
    )


def validate_video_upload(uploaded_file):
    allowed_content_types = {mime for mimes in VIDEO_UPLOAD_TYPES.values() for mime in mimes}
    return validate_upload(
        uploaded_file,
        allowed_extensions=VIDEO_UPLOAD_TYPES,
        allowed_content_types=allowed_content_types,
        extension_content_types=VIDEO_UPLOAD_TYPES,
        message=_("فقط فایل‌های ویدیویی MP4، WEBM، MOV، M4V یا OGV مجاز هستند."),
    )


def validate_media_upload(uploaded_file):
    allowed_extensions = set(IMAGE_UPLOAD_TYPES) | set(VIDEO_UPLOAD_TYPES)
    allowed_content_types = set(IMAGE_UPLOAD_TYPES.values()) | {
        mime for mimes in VIDEO_UPLOAD_TYPES.values() for mime in mimes
    }
    return validate_upload(
        uploaded_file,
        allowed_extensions=allowed_extensions,
        allowed_content_types=allowed_content_types,
        extension_content_types={
            **{extension: {mime} for extension, mime in IMAGE_UPLOAD_TYPES.items()},
            **VIDEO_UPLOAD_TYPES,
        },
        message=_("فقط فایل‌های تصویری یا ویدیویی مجاز هستند."),
    )


def validate_pdf_upload(uploaded_file):
    return validate_upload(
        uploaded_file,
        allowed_extensions={"pdf"},
        allowed_content_types={"application/pdf"},
        extension_content_types={"pdf": {"application/pdf"}},
        message=_("فقط فایل PDF مجاز است."),
    )


def validate_phone_number(value: str | None) -> str:
    phone = normalize_phone_number(value)
    if not re.match(r"^\d{11}$", phone):
        raise ValidationError(_("لطفا یک شماره تماس 11 رقمی وارد کنید."))
    return phone


def validate_fullname(value: str | None) -> str:
    fullname = (value or "").strip()
    if not fullname:
        raise ValidationError(_("لطفا نام کاربری خود را وارد کنید."))
    if not fullname.isalnum():
        raise ValidationError(_("نام کاربری باید فقط شامل حروف و اعداد باشد."))
    return fullname


def validate_strong_password(value: str | None) -> str:
    password = value or ""
    if len(password) < 8:
        raise ValidationError(_("رمز عبور باید حداقل 8 کاراکتر داشته باشد."))
    if not re.match(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).+$", password):
        raise ValidationError(_("رمز عبور باید شامل حرف کوچک، حرف بزرگ و عدد باشد."))
    return password
