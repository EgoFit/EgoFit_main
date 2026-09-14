from __future__ import annotations

from django.core.cache import cache
from django.db.models.signals import post_delete, post_save

from home.constants import HOME_PAGE_CACHE_PREFIX
from home.models import (
    Advantage,
    ArticleBlogImage,
    ArticleBlogLink,
    ArticleBlogModel,
    Category,
    CategoryBlog,
    Counseling,
    DownContent,
    Footer,
    HomePage,
    HomePageFeaturePoint,
    HomePageHighlightCard,
    HomePageMetric,
    HomePageTrustItem,
    SeriesModel,
)


def _invalidate_home_cache(**kwargs):
    cache.delete(f"{HOME_PAGE_CACHE_PREFIX}:home:v1")


for model in (
    HomePage,
    HomePageMetric,
    HomePageTrustItem,
    HomePageFeaturePoint,
    HomePageHighlightCard,
    Advantage,
    ArticleBlogModel,
    ArticleBlogImage,
    ArticleBlogLink,
    Category,
    CategoryBlog,
    Counseling,
    DownContent,
    Footer,
    SeriesModel,
):
    post_save.connect(_invalidate_home_cache, sender=model, dispatch_uid=f"home_cache_save_{model.__name__}")
    post_delete.connect(_invalidate_home_cache, sender=model, dispatch_uid=f"home_cache_delete_{model.__name__}")
