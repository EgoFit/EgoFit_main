from __future__ import annotations

from sport_shop.task_queue import shared_task

from account.services.notification_service import NotificationService
from account.services.sms_service import SmsService


@shared_task(name="account.send_verification_sms")
def send_verification_sms(phone: str, code: str | int):
    return SmsService().send_verification_sms(phone, code)


@shared_task(name="account.send_notification_sms_broadcast")
def send_notification_sms_broadcast(notification_id: int):
    return NotificationService().send_sms_broadcast_by_id(notification_id)
