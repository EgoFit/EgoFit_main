from __future__ import annotations

from django.http import JsonResponse

from api.utils import json_value


def ok(data=None, *, status=200):
    return JsonResponse({"data": json_value(data)}, status=status)


def error(code: str, message: str, *, status=400, details=None):
    payload = {"error": {"code": code, "message": message}}
    if details:
        payload["error"]["details"] = json_value(details)
    return JsonResponse(payload, status=status)
