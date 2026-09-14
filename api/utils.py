from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.http import HttpRequest
from django.utils.functional import Promise

def request_data(request: HttpRequest):
    if request.content_type and request.content_type.split(";", 1)[0].strip().lower() == "application/json":
        try:
            value = json.loads(request.body or b"{}")
        except (TypeError, ValueError):
            raise ValueError("Request body must contain valid JSON.")
        if not isinstance(value, dict):
            raise ValueError("Request body must be a JSON object.")
        return value
    return request.POST


def validation_details(exc: ValidationError) -> dict:
    if hasattr(exc, "message_dict"):
        return {str(key): [str(item) for item in value] for key, value in exc.message_dict.items()}
    return {"non_field_errors": [str(item) for item in exc.messages]}


def json_value(value):
    if isinstance(value, Promise):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {str(key): json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_value(item) for item in value]
    return value


def absolute_file_url(request, field):
    if not field:
        return None
    try:
        return request.build_absolute_uri(field.url)
    except (AttributeError, ValueError):
        return None


def parse_int(value, *, field: str):
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field} must be an integer.")
