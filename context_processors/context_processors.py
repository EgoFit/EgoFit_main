from __future__ import annotations

import logging

from django.core.cache import cache
from django.db.models import Prefetch

from home.models import ArticleBlogModel, Category, CategoryBlog, Footer, NavigationLink, SeriesModel, SiteSettings

CATEGORY_CACHE_TTL = 60 * 30
FOOTER_CACHE_TTL = 60 * 15
HOME_LISTING_CACHE_TTL = 60 * 10
SITE_SETTINGS_CACHE_TTL = 60 * 15
NAVIGATION_CACHE_TTL = 60 * 30
CONTEXT_CACHE_VERSION = 1

logger = logging.getLogger(__name__)


def _cache_key(name: str) -> str:
    return f"context:v{CONTEXT_CACHE_VERSION}:{name}"


def _get_cached_value(name: str, loader, timeout: int, default):
    cache_key = _cache_key(name)
    try:
        cached_value = cache.get(cache_key)
        if cached_value is not None:
            return cached_value
        value = loader()
        cache.set(cache_key, value, timeout)
        return value
    except Exception as exc:
        logger.exception("Context processor cache miss failed for %s: %s", name, exc)
        return default


def blogs_processor(request):
    article_categories = _get_cached_value(
        "article_categories",
        lambda: list(
            CategoryBlog.objects.prefetch_related(
                Prefetch(
                    "article_categories",
                    queryset=ArticleBlogModel.objects.only("id", "title", "slug", "language_kinds_id").order_by("title"),
                )
            )
            .only("id", "title", "slug")
            .order_by("id")[:12]
        ),
        CATEGORY_CACHE_TTL,
        [],
    )
    return {"article": article_categories}


def article_blog(request):
    return _get_cached_value(
        "article_blog",
        lambda: {
            "blog": list(
                ArticleBlogModel.objects.select_related("author", "language_kinds").order_by("-id")[:8]
            ),
            "course": list(
                SeriesModel.objects.select_related("author", "language_kinds").prefetch_related("seasons__episodes").order_by("-id")[:8]
            ),
        },
        HOME_LISTING_CACHE_TTL,
        {"blog": [], "course": []},
    )


def footer_context_processor(request):
    footer = _get_cached_value("footer", lambda: Footer.objects.first(), FOOTER_CACHE_TTL, None)
    return {"footer": footer}


def site_settings(request):
    def _load():
        settings_obj, _ = SiteSettings.objects.get_or_create(slug="default")
        return settings_obj

    return {"site_settings": _get_cached_value("site_settings", _load, SITE_SETTINGS_CACHE_TTL, None)}


def navigation_links(request):
    return {
        "nav_links": _get_cached_value(
            "navigation_links",
            lambda: list(NavigationLink.objects.all()),
            NAVIGATION_CACHE_TTL,
            [],
        )
    }


def categories(request):
    cached_categories = _get_cached_value(
        "categories",
        lambda: list(
            Category.objects.prefetch_related(
                Prefetch(
                    "categories",
                    queryset=SeriesModel.objects.only("id", "title", "language_kinds_id").order_by("title"),
                )
            )
            .only("id", "title", "slug")
            .order_by("id")[:24]
        ),
        CATEGORY_CACHE_TTL,
        [],
    )
    return {"categories": cached_categories}
