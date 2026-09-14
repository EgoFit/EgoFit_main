from __future__ import annotations

from django.contrib.auth.models import AnonymousUser

from api.auth import authenticate_bearer


class ApiBearerAuthenticationMiddleware:
    """Authenticate only API requests from an explicit bearer token.

    Session-authenticated browser users are intentionally not accepted here;
    this prevents CSRF/session confusion for API writes.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith("/api/"):
            # Never inherit a browser session into the API namespace.
            request.user = AnonymousUser()
            authorization = (request.headers.get("Authorization") or "").strip()
            if authorization:
                scheme, _, value = authorization.partition(" ")
                if scheme.lower() != "bearer" or not value.strip():
                    request.api_token = None
                else:
                    token = authenticate_bearer(value.strip())
                    request.api_token = token
                    request.user = token.user if token else request.user
            else:
                request.api_token = None
        return self.get_response(request)
