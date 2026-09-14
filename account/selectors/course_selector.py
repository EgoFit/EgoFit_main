from __future__ import annotations

from django.db.models import Q

from account.models import User
from home.models import SeriesModel


class CourseSelector:
    @staticmethod
    def get_learning_courses(user: User):
        return (
            SeriesModel.objects.filter(
                Q(order_items__order__is_paid=True, order_items__order__user=user)
                | Q(series_users__user=user, free=True)
            )
            .select_related("author", "language_kinds")
            .distinct()
        )

    @staticmethod
    def get_free_series(series_id: int):
        return SeriesModel.objects.select_related("author", "language_kinds").filter(id=series_id, free=True).first()

