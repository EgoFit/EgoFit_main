from __future__ import annotations

import logging

from django.conf import settings
from django.contrib.sessions.backends.base import UpdateError
from django.contrib.sessions.exceptions import SessionInterrupted
from django.contrib.sessions.middleware import SessionMiddleware


logger = logging.getLogger(__name__)


class ResilientSessionMiddleware(SessionMiddleware):
    """
    Recover from concurrent session writes instead of returning HTTP 400.

    This happens when login() rotates the session key while another parallel
    request still holds the previous key (common on mobile/homepage loads).
    """

    def process_response(self, request, response):
        try:
            return super().process_response(request, response)
        except SessionInterrupted:
            logger.warning(
                "Session interrupted for %s; preserving in-memory session and saving with a new key.",
                getattr(request, "path", "unknown"),
            )
            return self._retry_session_save(request, response)

    def _retry_session_save(self, request, response):
        if not hasattr(request, "session"):
            raise

        session_data = dict(request.session.items())
        request.session = self.SessionStore()
        if session_data:
            request.session.update(session_data)
        request.session.modified = True

        try:
            return super().process_response(request, response)
        except (SessionInterrupted, UpdateError):
            logger.exception("Unable to recover session for %s", getattr(request, "path", "unknown"))
            request.session = self.SessionStore()
            request.session.modified = False
            return response


class ForceDefaultLanguageMiddleware:
    """
    Drop the browser's Accept-Language header for visitors who haven't made an
    explicit language choice yet, so LocaleMiddleware falls through to
    settings.LANGUAGE_CODE (Persian) instead of auto-detecting English for
    English-locale browsers. Must run before LocaleMiddleware. An explicit
    choice via the language switcher (which sets the django_language cookie)
    always takes priority.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if settings.LANGUAGE_COOKIE_NAME not in request.COOKIES:
            request.META.pop("HTTP_ACCEPT_LANGUAGE", None)
        return self.get_response(request)
