from __future__ import annotations

from django.core.cache import cache
from django.db import transaction

from home.constants import HOME_SERIES_ENGAGEMENT_CACHE_TIMEOUT
from home.exceptions import SeriesAccessDeniedException
from home.repositories.series_repository import SeriesRepository
from home.selectors.comment_selector import CommentSelector
from home.selectors.course_selector import CourseSelector
from home.tasks.series_tasks import send_series_notifications
from home.utils import build_series_engagement_cache_key, format_duration
from account.tasks.dispatch import dispatch_task


class SeriesService:
    def __init__(self, repository: SeriesRepository | None = None):
        self.repository = repository or SeriesRepository()

    @staticmethod
    def has_access(*, user, series) -> bool:
        return CourseSelector.get_user_has_access(user=user, series=series)

    @staticmethod
    def get_active_comments_for_series(series):
        return CommentSelector.get_active_comments_for_series(series)

    def get_engagement_metrics(self, series) -> dict:
        cache_key = build_series_engagement_cache_key(series.pk)
        cached_metrics = cache.get(cache_key)
        if cached_metrics is not None:
            return cached_metrics
        metrics = CourseSelector.get_engagement_metrics(series)
        cache.set(cache_key, metrics, HOME_SERIES_ENGAGEMENT_CACHE_TIMEOUT)
        return metrics

    @staticmethod
    def format_duration(total_seconds):
        return format_duration(total_seconds)

    @staticmethod
    def get_course_detail_context(series, *, user) -> dict:
        from home.forms import ReplyForm

        related_items = CourseSelector.get_related_courses(series)
        metrics = SeriesService().get_engagement_metrics(series)
        return {
            "series_object": series,
            "items": related_items,
            "reply_form": ReplyForm(),
            "show_start_learning": CourseSelector.get_user_has_access(user=user, series=series),
            "active_comments": CommentSelector.get_active_comments_for_series(series),
            **metrics,
        }

    @staticmethod
    def get_series_episode_context(series, *, user) -> dict:
        total_duration_seconds = 0
        total_episodes_count = 0
        seasons = list(series.seasons.all())
        for season in seasons:
            season_episodes = list(season.episodes.all())
            total_duration_seconds += sum(episode.get_duration_in_seconds() for episode in season_episodes)
            total_episodes_count += len(season_episodes)

        from home.forms import ReplyForm

        metrics = SeriesService().get_engagement_metrics(series)
        context = {
            "seasons": seasons,
            "total_duration": format_duration(total_duration_seconds),
            "total_episodes": total_episodes_count,
            "series_object": series,
            "active_comments": CommentSelector.get_active_comments_for_series(series),
            "reply_form": ReplyForm(),
            "show_start_learning": CourseSelector.get_user_has_access(user=user, series=series),
        }
        context.update(metrics)
        return context

    @transaction.atomic
    def add_free_course_to_profile(self, *, user, series):
        return self.repository.get_or_create_user_course(user=user, series=series)

    def create_series_notifications_on_commit(self, *, series, previous_state=None):
        if previous_state is not None and previous_state.is_compeleted != series.is_compeleted and series.is_compeleted:
            title = "دوره تکمیل شد"
            message = f"دوره {series.title} تکمیل شده است!"
        elif previous_state is None:
            title = "دوره جدید اضافه شد"
            message = f"دوره جدید {series.title} به سایت اضافه شد."
        else:
            return

        transaction.on_commit(lambda: dispatch_task(send_series_notifications, title, message))
