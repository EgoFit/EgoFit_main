from __future__ import annotations

from django.db.models import Prefetch

from home.models import Reply


class CommentSelector:
    @staticmethod
    def get_active_comments_for_series(series):
        return list(
            series.comments.filter(is_active=True)
            .select_related("user", "series")
            .prefetch_related(
                Prefetch(
                    "reply_set",
                    queryset=Reply.objects.filter(is_active=True).select_related("user"),
                    to_attr="active_replies",
                )
            )
            .order_by("-created_at")
        )
