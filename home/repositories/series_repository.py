from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from account.models import Notification
from home.models import SeriesModel, UserCourse

User = get_user_model()


class SeriesRepository:
    def get_previous_state(self, series_id: int):
        return SeriesModel.objects.only("id", "title", "is_compeleted").get(pk=series_id)

    @transaction.atomic
    def bulk_notify_users(self, *, title: str, message: str, batch_size: int = 500) -> int:
        total_created = 0
        created_at = timezone.now()
        last_user_id = 0
        while True:
            chunk = list(
                User.objects.filter(id__gt=last_user_id)
                .order_by("id")
                .values_list("id", flat=True)[:batch_size]
            )
            if not chunk:
                break
            Notification.objects.bulk_create(
                [Notification(user_id=user_id, title=title, message=message, created_at=created_at) for user_id in chunk],
                batch_size=batch_size,
            )
            total_created += len(chunk)
            last_user_id = chunk[-1]
        return total_created

    def get_or_create_user_course(self, *, user, series: SeriesModel):
        return UserCourse.objects.get_or_create(user=user, series=series)
