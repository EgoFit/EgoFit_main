from __future__ import annotations

from django.utils import timezone

from account.models import Notification


class NotificationRepository:
    def create(
        self,
        *,
        user=None,
        title: str,
        message: str,
        is_global: bool = False,
        read: bool = False,
        send_sms_to_all: bool = False,
    ) -> Notification:
        return Notification.objects.create(
            user=user,
            title=title,
            message=message,
            is_global=is_global,
            read=read,
            send_sms_to_all=send_sms_to_all,
        )

    def get_by_id(self, notification_id: int) -> Notification:
        return Notification.objects.get(pk=notification_id)

    def mark_sms_pending(self, notification: Notification) -> None:
        notification.sms_status = Notification.SmsStatus.PENDING
        notification.sms_error = ""
        notification.sms_recipients_count = 0
        notification.sms_sent_at = None
        notification.save(update_fields=["sms_status", "sms_error", "sms_recipients_count", "sms_sent_at"])

    def mark_sms_not_requested(self, notification: Notification) -> None:
        notification.sms_status = Notification.SmsStatus.NOT_REQUESTED
        notification.sms_error = ""
        notification.sms_recipients_count = 0
        notification.sms_sent_at = None
        notification.save(update_fields=["sms_status", "sms_error", "sms_recipients_count", "sms_sent_at"])

    def mark_sms_sent(self, notification: Notification, *, recipients_count: int) -> None:
        notification.sms_status = Notification.SmsStatus.SENT
        notification.sms_error = ""
        notification.sms_recipients_count = recipients_count
        notification.sms_sent_at = timezone.now()
        notification.save(update_fields=["sms_status", "sms_error", "sms_recipients_count", "sms_sent_at"])

    def mark_sms_failed(self, notification: Notification, *, recipients_count: int, error: str) -> None:
        notification.sms_status = Notification.SmsStatus.FAILED
        notification.sms_error = error
        notification.sms_recipients_count = recipients_count
        notification.sms_sent_at = None
        notification.save(update_fields=["sms_status", "sms_error", "sms_recipients_count", "sms_sent_at"])

    def create_course_request_notification(self, *, user, course_title: str) -> Notification:
        return self.create(
            user=user,
            title="درخواست خرید",
            message=f"درخواست بررسی خرید برای دوره {course_title} ثبت شد.",
        )
