from __future__ import annotations

from django.conf import settings
from django.http import HttpResponse


class ApiCorsMiddleware:
    """Optional strict CORS for API clients; disabled unless allowlisted."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        origin = (request.headers.get("Origin") or "").strip()
        allowed = set(getattr(settings, "API_CORS_ALLOWED_ORIGINS", ()))
        is_secure_origin = origin.startswith("https://") or origin.startswith("http://localhost") or origin.startswith("http://127.0.0.1")
        if request.path.startswith("/api/") and origin and origin in allowed and is_secure_origin:
            response = HttpResponse(status=204) if request.method == "OPTIONS" else self.get_response(request)
            response["Access-Control-Allow-Origin"] = origin
            response["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
            response["Access-Control-Allow-Methods"] = "GET, POST, PATCH, DELETE, OPTIONS"
            response["Access-Control-Max-Age"] = "600"
            response["Vary"] = "Origin"
            return response
        return self.get_response(request)
