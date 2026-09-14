from __future__ import annotations

from django.core.cache import cache
from django.db.models import Count, Q

from cart.models import OrderItem
from home.constants import HOME_FEATURED_COURSE_LIMIT
from home.models import Category, SeriesModel, UserCourse


SERIES_COUNT_CACHE_KEY = "home:series:counts:v1"
SERIES_COUNT_CACHE_TTL = 60 * 10


class CourseSelector:
    @staticmethod
    def get_featured_courses(limit: int = HOME_FEATURED_COURSE_LIMIT):
        return (
            SeriesModel.objects.select_related("author", "language_kinds")
            .prefetch_related("seasons__episodes")
            .order_by("-id")[:limit]
        )

    @staticmethod
    def get_series_queryset():
        return SeriesModel.objects.select_related("author", "language_kinds").order_by("-id")

    @staticmethod
    def get_series_filtered_queryset(*, free: str | None = None, category: str | None = None):
        queryset = CourseSelector.get_series_queryset()
        if free is not None:
            if free.lower() == "true":
                queryset = queryset.filter(free=True)
            elif free.lower() == "false":
                queryset = queryset.filter(free=False)
        if category:
            queryset = queryset.filter(language_kinds__title=category)
        return queryset

    @staticmethod
    def get_series_counts():
        cached_counts = cache.get(SERIES_COUNT_CACHE_KEY)
        if cached_counts is not None:
            return cached_counts

        counts = SeriesModel.objects.aggregate(
            free_courses=Count("id", filter=Q(free=True)),
            not_free_courses=Count("id", filter=Q(free=False)),
        )
        result = (counts.get("free_courses") or 0, counts.get("not_free_courses") or 0)
        cache.set(SERIES_COUNT_CACHE_KEY, result, SERIES_COUNT_CACHE_TTL)
        return result

    @staticmethod
    def get_related_courses(series, limit: int = HOME_FEATURED_COURSE_LIMIT):
        return (
            SeriesModel.objects.select_related("author", "language_kinds")
            .prefetch_related("seasons__episodes")
            .exclude(pk=series.pk)
            .order_by("-id")[:limit]
        )

    @staticmethod
    def get_user_has_access(*, user, series) -> bool:
        if series.free:
            return True
        if not user.is_authenticated:
            return False
        if getattr(user, "is_admin", False):
            return True
        return OrderItem.objects.filter(order__user=user, order__is_paid=True, product=series).exists()

    @staticmethod
    def get_engagement_metrics(series) -> dict:
        purchased_users_count = (
            OrderItem.objects.filter(order__is_paid=True, product=series)
            .values_list("order__user", flat=True)
            .distinct()
            .count()
        )
        added_users_count = UserCourse.objects.filter(series=series).values_list("user", flat=True).distinct().count()
        total_users_count = purchased_users_count + added_users_count + 50
        return {
            "purchased_users_count": purchased_users_count,
            "added_users_count": added_users_count,
            "total_users_count": total_users_count,
        }

    @staticmethod
    def get_course_detail_queryset():
        return SeriesModel.objects.select_related("author", "language_kinds").prefetch_related("seasons__episodes")

    @staticmethod
    def get_episode_queryset():
        return SeriesModel.objects.select_related("author", "language_kinds").prefetch_related("seasons__episodes")

    @staticmethod
    def get_series_categories(limit: int = 12):
        return Category.objects.order_by("id")[:limit]
