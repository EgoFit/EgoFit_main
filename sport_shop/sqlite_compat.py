from __future__ import annotations

import json

from django.db import connection
from django.db.backends.signals import connection_created


def _json_valid(value) -> int:
    if value in (None, ""):
        return 0
    if isinstance(value, bytes):
        try:
            value = value.decode("utf-8")
        except UnicodeDecodeError:
            return 0

    try:
        json.loads(value)
    except (TypeError, ValueError):
        return 0
    return 1


def _register_sqlite_functions(sender, connection, **kwargs):
    if connection.vendor != "sqlite" or connection.connection is None:
        return
    connection.connection.create_function("JSON_VALID", 1, _json_valid)


def register_sqlite_functions() -> None:
    connection_created.connect(_register_sqlite_functions, dispatch_uid="sport_shop.sqlite_json_valid")
    if connection.vendor == "sqlite" and connection.connection is not None:
        _register_sqlite_functions(sender=None, connection=connection)
