from __future__ import annotations

from django.core.cache import cache
from django.http import HttpRequest

from account.exceptions import OTPRateLimitExceededException


WEB_OTP_REQUEST_LIMIT = 5
WEB_OTP_REQUEST_WINDOW_SECONDS = 15 * 60


def _client_ip(request: HttpRequest) -> str:
    """Use the proxy-normalized peer address; never trust raw X-Forwarded-For."""
    return request.META.get("REMOTE_ADDR", "unknown") or "unknown"


def _consume(key: str, *, limit: int, window: int) -> bool:
    """Atomically consume one cache-backed quota slot when possible."""
    try:
        if cache.add(key, 1, timeout=window):
            return True
        count = cache.incr(key)
        return count <= limit
    except (ValueError, NotImplementedError):
        # Backends without incr support still get a bounded counter.
        try:
            current = int(cache.get(key, 0)) + 1
            cache.set(key, current, timeout=window)
            return current <= limit
        except Exception:
            return True
    except Exception:
        # OTPService's per-phone cooldown remains available if cache is down.
        return True


def enforce_web_otp_rate_limit(request: HttpRequest, phone: str) -> None:
    """Apply both IP and phone quotas to browser OTP issuance flows."""
    normalized_phone = str(phone or "").strip()
    checks = (
        (f"account:web-otp:ip:{_client_ip(request)}", WEB_OTP_REQUEST_LIMIT),
        (f"account:web-otp:phone:{normalized_phone}", WEB_OTP_REQUEST_LIMIT),
    )
    if all(_consume(key, limit=limit, window=WEB_OTP_REQUEST_WINDOW_SECONDS) for key, limit in checks):
        return
    raise OTPRateLimitExceededException(
        "تعداد درخواست‌های کد تأیید بیش از حد مجاز است. لطفاً بعداً دوباره تلاش کنید."
    )
