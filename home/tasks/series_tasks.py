from __future__ import annotations

from sport_shop.task_queue import shared_task

from home.repositories.series_repository import SeriesRepository


@shared_task(name="home.send_series_notifications")
def send_series_notifications(title: str, message: str) -> int:
    return SeriesRepository().bulk_notify_users(title=title, message=message)
