from pathlib import Path
from tempfile import mkdtemp
from unittest.mock import patch
import shutil

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from account.models import CoachRequest, CoachRequestAttachment, User
from cart.constants import PAYMENT_SESSION_KEY
from cart.models import Order, OrderItem
from cart.providers.base import PaymentInitiationResult, PaymentVerificationResult
from cart.services.payment_service import PaymentService
from home.models import Category, CommentSectionModel, SeriesModel


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class FrontendBackendIntegrationTests(TestCase):
    """Request-level coverage for the main browser-to-Django user journeys."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._media_root = mkdtemp(prefix="egofit-integration-")
        cls._media_override = override_settings(MEDIA_ROOT=cls._media_root)
        cls._media_override.enable()

    @classmethod
    def tearDownClass(cls):
        cls._media_override.disable()
        shutil.rmtree(cls._media_root, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.user = User.objects.create_user(
            fullname="integration_user",
            phone="09125555555",
            password="StrongPass123",
        )
        self.category = Category.objects.create(
            title="Integration Category",
            slug="integration-category",
        )

    def create_series(self, *, free=False):
        with patch("home.services.series_service.SeriesService.create_series_notifications_on_commit"):
            return SeriesModel.objects.create(
                title="Integration Course",
                image=SimpleUploadedFile(
                    "integration-course.png",
                    b"not-an-image-but-a-stored-test-fixture",
                    content_type="image/png",
                ),
                is_compeleted=True,
                language_kinds=self.category,
                author=self.user,
                main_price="150000",
                discount_price="120000",
                free=free,
            )

    def test_password_login_creates_session_and_dashboard_is_available(self):
        response = self.client.post(
            reverse("register:pass_login"),
            {"fullname": self.user.fullname, "password": "StrongPass123"},
        )

        self.assertRedirects(response, reverse("home:home"))
        self.assertEqual(self.client.session.get("_auth_user_id"), str(self.user.pk))

        dashboard = self.client.get(reverse("register:profile"))
        self.assertEqual(dashboard.status_code, 200)
        self.assertContains(dashboard, self.user.fullname)
        self.assertContains(dashboard, "profile-settings-hub")

    def test_coach_form_saves_request_and_uploaded_file_then_renders_it(self):
        self.client.force_login(self.user)
        attachment = SimpleUploadedFile(
            "mobility-guide.pdf",
            b"%PDF-1.4 integration fixture",
            content_type="application/pdf",
        )
        response = self.client.post(
            reverse("register:profile_coach"),
            {
                "sessions_per_week": "3",
                "wants_workout": "on",
                "height_cm": "180",
                "weight_kg": "78",
                "wrist_cm": "17",
                "waist_cm": "82",
                "abdomen_cm": "85",
                "hips_cm": "98",
                "attachments": attachment,
            },
        )

        self.assertRedirects(response, reverse("register:profile_coach"))
        coach_request = CoachRequest.objects.get(user=self.user)
        self.assertEqual(coach_request.sessions_per_week, "3")
        self.assertTrue(coach_request.wants_workout)
        self.assertEqual(coach_request.height_cm, 180)

        saved_attachment = CoachRequestAttachment.objects.get(request=coach_request)
        self.assertIn("mobility-guide", saved_attachment.file.name)
        self.assertEqual(Path(saved_attachment.file.name).suffix, ".pdf")
        self.assertTrue(Path(saved_attachment.file.path).exists())

        page = self.client.get(reverse("register:profile_coach"))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, Path(saved_attachment.file.name).name)

    def test_course_comment_submission_saves_pending_comment_and_returns_course_page(self):
        series = self.create_series(free=True)
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("home:course_detail", args=[series.pk]),
            {"text": "A useful integration comment."},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="tabThree"')
        comment = CommentSectionModel.objects.get(series=series, user=self.user)
        self.assertEqual(comment.text, "A useful integration comment.")
        self.assertFalse(comment.is_active)

    def test_cart_creates_order_payment_callback_marks_order_paid_and_shows_success(self):
        series = self.create_series()
        self.client.force_login(self.user)

        add_response = self.client.post(reverse("cart:cart_add", args=[series.pk]))
        self.assertRedirects(add_response, reverse("cart:cart_detail"))
        self.assertIn("cart", self.client.session)

        order_response = self.client.post(reverse("cart:order_create"))
        order = Order.objects.get(user=self.user)
        self.assertRedirects(order_response, reverse("cart:order_detail", args=[order.pk]))
        self.assertEqual(order.total_price, 120000)
        self.assertEqual(OrderItem.objects.filter(order=order).count(), 1)
        self.assertNotIn("cart", self.client.session)

        class FakePaymentProvider:
            def request_payment(self, **kwargs):
                return PaymentInitiationResult(
                    redirect_url="https://pay.example/start/INTEGRATION-AUTH",
                    authority="INTEGRATION-AUTH",
                    raw_response={"code": 100},
                )

            def verify_payment(self, **kwargs):
                return PaymentVerificationResult(
                    success=True,
                    ref_id="INTEGRATION-REF",
                    message=None,
                    raw_response={"code": 100},
                )

        payment_service = PaymentService(provider=FakePaymentProvider())
        with patch("cart.views.payment_service", payment_service):
            payment_response = self.client.post(
                reverse("cart:request", args=[order.pk])
            )
            self.assertEqual(
                payment_response["Location"],
                "https://pay.example/start/INTEGRATION-AUTH",
            )
            order.refresh_from_db()
            self.assertEqual(order.status, Order.PaymentStatus.PAYMENT_INITIATED)
            self.assertEqual(order.authority, "INTEGRATION-AUTH")
            self.assertEqual(
                self.client.session.get(PAYMENT_SESSION_KEY),
                str(order.pk),
            )

            callback_response = self.client.get(
                reverse("cart:verify") + "?Authority=INTEGRATION-AUTH&Status=OK"
            )

        self.assertEqual(callback_response.status_code, 200)
        order.refresh_from_db()
        self.assertTrue(order.is_paid)
        self.assertEqual(order.status, Order.PaymentStatus.PAID)
        self.assertEqual(order.ref_id, "INTEGRATION-REF")
        self.assertNotIn(PAYMENT_SESSION_KEY, self.client.session)
        self.assertContains(callback_response, "پرداخت")
