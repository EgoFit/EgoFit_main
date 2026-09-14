from unittest.mock import Mock, patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from account.exceptions import WhatsAppUnavailableException
from account.models import ClientDocument, ClientMedia, Notification, User, WorkoutProgram
from account.services.notification_service import NotificationService
from account.services.whatsapp_service import (
    STATUS_FAILED,
    STATUS_SENT,
    STATUS_SKIPPED_DISABLED,
    STATUS_SKIPPED_NO_WHATSAPP,
    MetaCloudWhatsAppProvider,
    WhatsAppService,
)


class FakeWhatsAppProvider:
    def __init__(self, *, configured=True, result=True, error=None):
        self.configured = configured
        self.result = result
        self.error = error
        self.calls = []

    def is_configured(self):
        return self.configured

    def send_text_message(self, phone, message):
        self.calls.append((phone, message))
        if self.error:
            raise self.error
        return self.result


class WhatsAppServiceTests(TestCase):
    def test_skips_when_provider_is_not_configured(self):
        service = WhatsAppService(provider=FakeWhatsAppProvider(configured=False))
        status = service.send_news_if_available("09123456789", "سلام")
        self.assertEqual(status, STATUS_SKIPPED_DISABLED)

    def test_sends_when_number_is_valid(self):
        provider = FakeWhatsAppProvider()
        service = WhatsAppService(provider=provider)
        status = service.send_news_if_available("09123456789", "برنامه جدید")
        self.assertEqual(status, STATUS_SENT)
        self.assertEqual(provider.calls[0][0], "09123456789")

    def test_skips_when_number_is_not_on_whatsapp(self):
        provider = FakeWhatsAppProvider(error=WhatsAppUnavailableException("no wa"))
        service = WhatsAppService(provider=provider)
        status = service.send_news_if_available("09123456789", "برنامه جدید")
        self.assertEqual(status, STATUS_SKIPPED_NO_WHATSAPP)

    def test_failed_send_does_not_raise(self):
        provider = FakeWhatsAppProvider(result=False)
        service = WhatsAppService(provider=provider)
        status = service.send_news_if_available("09123456789", "برنامه جدید")
        self.assertEqual(status, STATUS_FAILED)

    @override_settings(
        WHATSAPP_ENABLED=True,
        WHATSAPP_TOKEN="token",
        WHATSAPP_PHONE_NUMBER_ID="123",
        WHATSAPP_API_VERSION="v21.0",
        WHATSAPP_TEMPLATE_NAME="",
    )
    @patch("account.services.whatsapp_service.requests.post")
    def test_meta_provider_posts_international_number(self, mocked_post):
        mocked_post.return_value = Mock(
            status_code=200,
            json=lambda: {"messages": [{"id": "wamid.1"}]},
        )
        provider = MetaCloudWhatsAppProvider()
        self.assertTrue(provider.send_text_message("09123456789", "سلام ورزشکار"))
        args, kwargs = mocked_post.call_args
        self.assertEqual(args[0], "https://graph.facebook.com/v21.0/123/messages")
        self.assertEqual(kwargs["json"]["to"], "989123456789")
        self.assertEqual(kwargs["json"]["type"], "text")

    @override_settings(
        WHATSAPP_ENABLED=True,
        WHATSAPP_TOKEN="token",
        WHATSAPP_PHONE_NUMBER_ID="123",
        WHATSAPP_TEMPLATE_NAME="",
    )
    @patch("account.services.whatsapp_service.requests.post")
    def test_meta_provider_treats_undeliverable_as_unavailable(self, mocked_post):
        mocked_post.return_value = Mock(
            status_code=400,
            json=lambda: {"error": {"code": 131026, "message": "undeliverable"}},
        )
        provider = MetaCloudWhatsAppProvider()
        with self.assertRaises(WhatsAppUnavailableException):
            provider.send_text_message("09123456789", "سلام")


class AthleteNewsNotificationTests(TestCase):
    def setUp(self):
        self.athlete = User.objects.create(phone="09121112233", fullname="athlete_news")
        self.admin = User.objects.create(phone="09121112234", fullname="coach_news", is_admin=True)

    def test_program_notification_is_created_and_whatsapp_is_attempted(self):
        program = WorkoutProgram.objects.create(
            user=self.athlete,
            prescribed_by=self.admin,
            title="برنامه حجم",
            is_published=True,
        )
        provider = FakeWhatsAppProvider()
        service = NotificationService(whatsapp_service=WhatsAppService(provider=provider))

        notification = service.notify_program_registered(program.pk)

        self.assertIsNotNone(notification)
        self.assertEqual(notification.user, self.athlete)
        self.assertEqual(notification.title, "برنامه بدنسازی جدید")
        self.assertIn("برنامه حجم", notification.message)
        self.assertEqual(len(provider.calls), 1)
        self.assertIn("برنامه حجم", provider.calls[0][1])

    def test_unpublished_program_does_not_notify(self):
        program = WorkoutProgram.objects.create(
            user=self.athlete,
            prescribed_by=self.admin,
            title="پیش‌نویس",
            is_published=False,
        )
        provider = FakeWhatsAppProvider()
        service = NotificationService(whatsapp_service=WhatsAppService(provider=provider))

        notification = service.notify_program_registered(program.pk)

        self.assertIsNone(notification)
        self.assertEqual(provider.calls, [])
        self.assertFalse(Notification.objects.filter(user=self.athlete).exists())

    def test_document_upload_creates_news_and_sends_whatsapp(self):
        document = ClientDocument.objects.create(
            user=self.athlete,
            uploaded_by=self.admin,
            title="برنامه غذایی",
            file=SimpleUploadedFile("diet.pdf", b"%PDF-1.4", content_type="application/pdf"),
        )
        provider = FakeWhatsAppProvider()
        service = NotificationService(whatsapp_service=WhatsAppService(provider=provider))

        notification = service.notify_document_uploaded(document.pk)

        self.assertEqual(notification.user, self.athlete)
        self.assertEqual(notification.title, "فایل جدید")
        self.assertIn("برنامه غذایی", notification.message)
        self.assertEqual(provider.calls[0][0], "09121112233")


class AthleteNewsPortalHookTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create(phone="09120000051", fullname="alert_admin", is_admin=True)
        self.admin.set_password("StrongPass123")
        self.admin.save()
        self.athlete = User.objects.create(phone="09120000052", fullname="alert_athlete")

    @patch("account.services.whatsapp_service.WhatsAppService.send_news_if_available", return_value="sent")
    def test_admin_document_upload_creates_notification(self, mocked_send):
        self.client.force_login(self.admin)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse("register:admin_upload", args=[self.athlete.pk]),
                {
                    "upload_kind": "document",
                    "title": "برنامه هفته یک",
                    "file": SimpleUploadedFile("week1.pdf", b"%PDF-1.4", content_type="application/pdf"),
                },
            )

        self.assertRedirects(response, reverse("register:admin_user_hub", args=[self.athlete.pk]))
        self.assertTrue(ClientDocument.objects.filter(user=self.athlete, title="برنامه هفته یک").exists())
        notification = Notification.objects.get(user=self.athlete)
        self.assertEqual(notification.title, "فایل جدید")
        mocked_send.assert_called_once()

    @patch("account.services.whatsapp_service.WhatsAppService.send_news_if_available", return_value="sent")
    def test_admin_media_upload_creates_notification(self, mocked_send):
        self.client.force_login(self.admin)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse("register:admin_upload", args=[self.athlete.pk]),
                {
                    "upload_kind": "media",
                    "image": SimpleUploadedFile("progress.png", b"image-bytes", content_type="image/png"),
                },
            )

        self.assertRedirects(response, reverse("register:admin_search"))
        self.assertTrue(ClientMedia.objects.filter(user=self.athlete).exists())
        notification = Notification.objects.get(user=self.athlete)
        self.assertEqual(notification.title, "فایل جدید")
        mocked_send.assert_called_once()
