from __future__ import annotations

from decimal import Decimal, InvalidOperation


def normalize_price(value) -> int:
    try:
        return int(Decimal(str(value).replace(",", "")))
    except (InvalidOperation, ValueError, TypeError):
        return 0
