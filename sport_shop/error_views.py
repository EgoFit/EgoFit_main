from __future__ import annotations

import logging

from django.shortcuts import render
from django.utils.translation import gettext_lazy as _


logger = logging.getLogger(__name__)


def _render_error(request, status_code: int, title: str, message: str, code_label: str):
    context = {
        "error_code": status_code,
        "error_title": title,
        "error_message": message,
        "error_label": code_label,
    }
    return render(request, "error_page.html", context, status=status_code)


def custom_page_not_found(request, exception):
    logger.warning("404 Not Found: %s", getattr(request, "path", "unknown"))
    return _render_error(
        request,
        404,
        _("این صفحه پیدا نشد"),
        _("ممکن است آدرس اشتباه وارد شده باشد، صفحه جابه‌جا شده باشد یا دسترسی آن دیگر فعال نباشد."),
        _("خطای ۴۰۴"),
    )


def custom_bad_request(request, exception):
    logger.warning("400 Bad Request: %s", getattr(request, "path", "unknown"))
    return _render_error(
        request,
        400,
        _("درخواست معتبر نیست"),
        _("درخواست شما به‌درستی پردازش نشد. لطفاً صفحه را دوباره بارگذاری کنید و مجدداً تلاش کنید."),
        _("خطای ۴۰۰"),
    )


def custom_permission_denied(request, exception):
    logger.warning("403 Permission Denied: %s", getattr(request, "path", "unknown"))
    return _render_error(
        request,
        403,
        _("دسترسی غیرمجاز"),
        _("شما اجازه دسترسی به این بخش را ندارید یا باید دوباره وارد حساب خود شوید."),
        _("خطای ۴۰۳"),
    )


def custom_server_error(request):
    logger.exception("500 Server Error: %s", getattr(request, "path", "unknown"))
    return _render_error(
        request,
        500,
        _("خطای داخلی سرور"),
        _("در پردازش درخواست مشکلی رخ داد. تیم فنی از این خطا مطلع شده است."),
        _("خطای ۵۰۰"),
    )
