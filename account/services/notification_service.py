from __future__ import annotations

from django.db import transaction

from account.constants import SMS_BROADCAST_CHUNK_SIZE
from account.exceptions import SMSProviderException
from account.interfaces import PersonalizedSmsMessage
from account.models import ClientDocument, ClientMedia, WorkoutProgram
from account.repositories.notification_repository import NotificationRepository
from account.selectors.notification_selector import NotificationSelector
from account.selectors.user_selector import UserSelector
from account.services.sms_service import SmsService
from account.services.whatsapp_service import WhatsAppService
from account.utils import build_notification_sms_message, iter_chunks, normalize_phone_number


class NotificationService:
    def __init__(
        self,
        *,
        repository: NotificationRepository | None = None,
        sms_service: SmsService | None = None,
        whatsapp_service: WhatsAppService | None = None,
    ):
        self.repository = repository or NotificationRepository()
        self.sms_service = sms_service or SmsService()
        self.whatsapp_service = whatsapp_service or WhatsAppService()

    def create_course_request_notification(self, *, user, course_title: str):
        return self.repository.create_course_request_notification(user=user, course_title=course_title)

    def notify_athlete_news(self, user, *, title: str, message: str):
        notification = self.repository.create(user=user, title=title, message=message)
        whatsapp_message = build_notification_sms_message(
            notification,
            recipient_name=(getattr(user, "fullname", "") or "").strip(),
        )
        self.whatsapp_service.send_news_if_available(getattr(user, "phone", None), whatsapp_message)
        return notification

    def notify_program_registered(self, program_id: int):
        program = (
            WorkoutProgram.objects.select_related("user")
            .filter(pk=program_id, is_published=True)
            .first()
        )
        if program is None or program.user_id is None:
            return None
        title = "برنامه بدنسازی جدید"
        message = f"برنامه بدنسازی «{program.title}» برای شما ثبت شد. از پنل کاربری می‌توانید آن را مشاهده کنید."
        return self.notify_athlete_news(program.user, title=title, message=message)

    def notify_document_uploaded(self, document_id: int):
        document = ClientDocument.objects.select_related("user").filter(pk=document_id).first()
        if document is None or document.user_id is None:
            return None
        title = "فایل جدید"
        document_title = (document.title or "").strip() or "فایل"
        message = f"فایل «{document_title}» برای شما بارگذاری شد. از پنل کاربری می‌توانید آن را مشاهده کنید."
        return self.notify_athlete_news(document.user, title=title, message=message)

    def notify_media_uploaded(self, media_id: int):
        media = ClientMedia.objects.select_related("user").filter(pk=media_id).first()
        if media is None or media.user_id is None:
            return None
        title = "فایل جدید"
        message = "یک فایل تصویر یا ویدیو برای شما بارگذاری شد. از پنل کاربری می‌توانید آن را مشاهده کنید."
        return self.notify_athlete_news(media.user, title=title, message=message)

    @staticmethod
    def schedule_program_registered(program) -> None:
        if program is None or not getattr(program, "is_published", False) or not program.pk:
            return
        program_id = program.pk
        transaction.on_commit(lambda: NotificationService().notify_program_registered(program_id))

    @staticmethod
    def schedule_document_uploaded(document) -> None:
        if document is None or not document.pk:
            return
        document_id = document.pk
        transaction.on_commit(lambda: NotificationService().notify_document_uploaded(document_id))

    @staticmethod
    def schedule_media_uploaded(media) -> None:
        if media is None or not media.pk:
            return
        media_id = media.pk
        transaction.on_commit(lambda: NotificationService().notify_media_uploaded(media_id))

    def get_profile_notifications(self, user, *, limit: int = 20):
        return NotificationSelector.get_profile_notifications(user, limit=limit)

    def get_dashboard_notifications(self, user, *, limit: int = 3):
        return NotificationSelector.get_dashboard_notifications(user, limit=limit)

    def get_notifications_count(self, user) -> int:
        return NotificationSelector.get_notifications_count(user)

    def send_sms_broadcast(self, notification):
        if not notification.is_global or not notification.send_sms_to_all:
            self.repository.mark_sms_not_requested(notification)
            return 0

        recipients_queryset = UserSelector.get_active_sms_recipients()
        if not recipients_queryset.exists():
            self.repository.mark_sms_failed(
                notification,
                recipients_count=0,
                error="کاربر فعالی با شماره تماس ثبت‌شده برای ارسال پیامک پیدا نشد.",
            )
            return 0

        recipients: list[PersonalizedSmsMessage] = []
        for user in recipients_queryset.iterator(chunk_size=SMS_BROADCAST_CHUNK_SIZE):
            phone = normalize_phone_number(getattr(user, "phone", None))
            if len(phone) != 11 or not phone.isdigit():
                continue

            recipient_name = (getattr(user, "fullname", "") or "").strip()
            recipients.append(
                PersonalizedSmsMessage(
                    receptor=phone,
                    message=build_notification_sms_message(notification, recipient_name=recipient_name),
                )
            )

        if not recipients:
            self.repository.mark_sms_failed(
                notification,
                recipients_count=0,
                error="کاربر فعالی با شماره تماس معتبر برای ارسال پیامک پیدا نشد.",
            )
            return 0

        self.repository.mark_sms_pending(notification)

        sent_count = 0
        try:
            for chunk in iter_chunks(recipients, SMS_BROADCAST_CHUNK_SIZE):
                is_sent = self.sms_service.send_personalized_bulk_sms(chunk)
                if not is_sent:
                    raise SMSProviderException("پنل پیامکی پاسخ موفق برای ارسال گروهی برنگرداند.")
                sent_count += len(chunk)
        except Exception as exc:
            self.repository.mark_sms_failed(notification, recipients_count=sent_count, error=str(exc))
            raise

        self.repository.mark_sms_sent(notification, recipients_count=sent_count)
        return sent_count

    def send_sms_broadcast_by_id(self, notification_id: int):
        notification = self.repository.get_by_id(notification_id)
        return self.send_sms_broadcast(notification)
