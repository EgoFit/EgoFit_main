from __future__ import annotations

from django import template

register = template.Library()


@register.filter
def extract_discount_amount(message):
    if not message:
        return ""
    parts = str(message).split()
    if len(parts) < 2:
        return ""
    return parts[1]
