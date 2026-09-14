from __future__ import annotations

import re
from itertools import islice
from typing import Iterable, Iterator

from django.db.models import Case, IntegerField, Value, When

ARABIC_TO_PERSIAN_MAP = str.maketrans(
    {
        "\u064a": "\u06cc",
        "\u0643": "\u06a9",
        "\u0629": "\u0647",
        "\u0623": "\u0627",
        "\u0625": "\u0627",
        "\u0624": "\u0648",
    }
)


def normalize_search_query(raw_query: str) -> str:
    normalized = (raw_query or "").translate(ARABIC_TO_PERSIAN_MAP)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def tokenize_search_query(raw_query: str) -> list[str]:
    normalized = normalize_search_query(raw_query)
    if not normalized:
        return []
    return [token for token in re.split(r"[^\w\u0600-\u06FF]+", normalized) if token]


def build_score_expression(tokens: list[str], fields: list[tuple[str, int]]):
    score = Value(0, output_field=IntegerField())
    for token in tokens:
        normalized_token = normalize_search_query(token)
        if not normalized_token:
            continue
        for field_name, weight in fields:
            score += Case(
                When(**{f"{field_name}__iexact": normalized_token}, then=Value(weight * 4)),
                When(**{f"{field_name}__istartswith": normalized_token}, then=Value(weight * 2)),
                When(**{f"{field_name}__icontains": normalized_token}, then=Value(weight)),
                default=Value(0),
                output_field=IntegerField(),
            )
    return score


def iter_chunks(values: Iterable, chunk_size: int) -> Iterator[list]:
    iterator = iter(values)
    while True:
        chunk = list(islice(iterator, chunk_size))
        if not chunk:
            return
        yield chunk


def format_duration(total_seconds: int) -> str:
    hours, remainder = divmod(int(total_seconds or 0), 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def build_series_engagement_cache_key(series_id: int) -> str:
    from home.constants import HOME_SERIES_ENGAGEMENT_CACHE_PREFIX

    return f"{HOME_SERIES_ENGAGEMENT_CACHE_PREFIX}:{series_id}"
