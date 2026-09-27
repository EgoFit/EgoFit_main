from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from django.core.cache import cache
from django.db.models import Q

from account.constants import GLOBAL_NOTIFICATION_CACHE_KEY, GLOBAL_NOTIFICATION_CACHE_TIMEOUT
from account.models import Notification, NotificationDismissal
from account.selectors.user_selector import UserSelector


@dataclass(frozen=True)
class NotificationFeedItem:
    title: str
    message: str
    created_at: object
    read: bool = False
    key: str = ""


class NotificationSelector:
    @staticmethod
    def get_user_notifications(user, *, limit: int | None = None):
        queryset = Notification.objects.filter(user=user).order_by("-created_at")
        if limit is not None:
            return queryset[:limit]
        return queryset

    @staticmethod
    def get_global_notifications(*, limit: int = 20):
        cache_key = f"{GLOBAL_NOTIFICATION_CACHE_KEY}:{limit}"
        notifications = cache.get(cache_key)
        if notifications is None:
            notifications = list(Notification.objects.filter(is_global=True).order_by("-created_at")[:limit])
            cache.set(cache_key, notifications, GLOBAL_NOTIFICATION_CACHE_TIMEOUT)
        return notifications

    @staticmethod
    def get_dashboard_notifications(user, *, limit: int = 3):
        return Notification.objects.filter(Q(user=user) | Q(is_global=True)).order_by("-created_at")[:limit]

    @staticmethod
    def get_notifications_count(user) -> int:
        return Notification.objects.filter(Q(user=user) | Q(is_global=True)).count()

    @staticmethod
    def build_course_notifications(user, *, limit: int = 20) -> list[NotificationFeedItem]:
        course_notifications: list[NotificationFeedItem] = []
        orders = UserSelector.get_paid_orders(user)[:limit]
        for order in orders:
            if order.course:
                course_title = order.course.title
            else:
                course_title = ", ".join(
                    item.product.title for item in order.items.all()[:2] if item.product
                )
            if not course_title:
                continue
            course_notifications.append(
                NotificationFeedItem(
                    title="خرید موفق",
                    message=f"خرید شما با موفقیت انجام شد: {course_title}",
                    created_at=order.created_at,
                    key=f"course-order:{order.pk}",
                )
            )
        return course_notifications

    @staticmethod
    def _to_feed_item(notification: Notification) -> NotificationFeedItem:
        return NotificationFeedItem(
            title=notification.title,
            message=notification.message,
            created_at=notification.created_at,
            read=notification.read,
            key=f"notification:{notification.pk}",
        )

    @staticmethod
    def get_profile_notifications(user, *, limit: int = 20):
        user_notifications = [
            NotificationSelector._to_feed_item(notification)
            for notification in NotificationSelector.get_user_notifications(user, limit=limit)
        ]
        global_notifications = [
            NotificationSelector._to_feed_item(notification)
            for notification in NotificationSelector.get_global_notifications(limit=limit)
        ]
        course_notifications = NotificationSelector.build_course_notifications(user, limit=limit)

        notifications = user_notifications + global_notifications + course_notifications
        notifications = sorted(
            notifications,
            key=lambda item: item.created_at,
            reverse=True,
        )
        dismissed_keys = set(
            NotificationDismissal.objects.filter(
                user=user,
                notification_key__in=[notification.key for notification in notifications],
            ).values_list("notification_key", flat=True)
        )
        return [notification for notification in notifications if notification.key not in dismissed_keys]

    @staticmethod
    def dismiss_profile_notification(user, notification_key: str) -> bool:
        notification_key = (notification_key or "").strip()
        if not notification_key:
            return False
        _, created = NotificationDismissal.objects.get_or_create(
            user=user,
            notification_key=notification_key,
        )
        return created
