from datetime import datetime
import re

import jdatetime
from django import template
from django.core.files.storage import default_storage
from django.utils.safestring import mark_safe

from home.rich_text import is_safe_article_url, sanitize_rich_text

register = template.Library()

_BLANK_CMS_VALUES = frozenset({"none", "null", "undefined", "-", "—"})


def _is_blank_cms_value(value) -> bool:
    if value is None:
        return True
    text = str(value).strip()
    if not text:
        return True
    return text.casefold() in _BLANK_CMS_VALUES


def format_duration(total_seconds):
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours > 0:
        return f"{int(hours)}:{int(minutes):02d}:{int(seconds):02d}"
    return f"{int(minutes)}:{int(seconds):02d}"


@register.simple_tag
def calculate_episodes_and_duration(series):
    cached = getattr(series, "_episode_summary_cache", None)
    if cached is not None:
        return cached

    total_duration_seconds = 0
    total_episodes_count = 0

    for season in series.seasons.all():
        episodes = list(season.episodes.all())
        total_episodes_count += len(episodes)
        total_duration_seconds += sum(episode.get_duration_in_seconds() for episode in episodes)

    summary = {
        "total_duration": format_duration(total_duration_seconds),
        "total_episodes": total_episodes_count,
    }
    series._episode_summary_cache = summary
    return summary


@register.filter
def to_jalali(date):
    if date:
        jalali_date = jdatetime.datetime.fromgregorian(datetime=date)
        return jalali_date.strftime("%Y/%m/%d")
    return ""


@register.filter
def extract_discount_amount(message):
    parts = (message or "").split()
    if len(parts) >= 2:
        return parts[1]
    return message or ""


@register.filter
def public_media_url(file_field):
    if not file_field:
        return ""

    file_name = getattr(file_field, "name", "")
    if not file_name:
        return ""

    if str(file_name).startswith(("http://", "https://")):
        return file_name

    try:
        storage = getattr(file_field, "storage", None) or default_storage
        return storage.url(file_name)
    except Exception:
        try:
            return file_field.url
        except Exception:
            return ""


@register.filter
def default_cms(value, fallback):
    if _is_blank_cms_value(value):
        return fallback
    return value


@register.filter
def split_paragraphs(value):
    if not value:
        return []

    normalized = str(value).replace("\r\n", "\n").strip()
    if not normalized:
        return []

    paragraphs = [part.strip() for part in re.split(r"\n\s*\n+", normalized) if part.strip()]
    if paragraphs:
        return paragraphs

    return [line.strip() for line in normalized.split("\n") if line.strip()]


@register.filter
def article_content(value):
    return mark_safe(sanitize_rich_text(value))


@register.filter
def article_link_url(value):
    value = str(value or "").strip()
    return value if is_safe_article_url(value) else ""
