from __future__ import annotations

from functools import wraps

from django.core.cache import cache
from django.http import HttpRequest

from api.responses import error


def _client_ip(request: HttpRequest) -> str:
    # Do not trust X-Forwarded-For here; the reverse proxy should normalize
    # REMOTE_ADDR before Django receives the request.
    return request.META.get("REMOTE_ADDR", "unknown") or "unknown"


def rate_limit(*, name: str, limit: int, window: int):
    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            identity = getattr(getattr(request, "user", None), "pk", None) or _client_ip(request)
            key = f"api:rate:{name}:{identity}"
            try:
                count = cache.get(key, 0)
                if count >= limit:
                    response = error("rate_limited", "Too many requests. Please try again later.", status=429)
                    response["Retry-After"] = str(window)
                    return response
                cache.set(key, count + 1, window)
            except Exception:
                # Availability of the cache must not make authentication fail.
                pass
            return view(request, *args, **kwargs)

        return wrapped

    return decorator
