from unittest.mock import patch

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase

from account.exceptions import OTPRateLimitExceededException
from account.limits import enforce_web_otp_rate_limit
from account.models import ClientDocument, ClientDocumentPayment, User, WorkoutProgram, WorkoutProgramPayment
from account.services.access_payment_service import AccessPaymentService
from account.services.otp_service import OTPService
from cart.providers.base import PaymentInitiationResult, PaymentVerificationResult


class FakePaymentProvider:
    def __init__(self):
        self.request_calls = 0
        self.verify_calls = 0

    def build_startpay_url(self, authority):
        return f"https://pay.example/start/{authority}"

    def request_payment(self, **kwargs):
        self.request_calls += 1
        authority = f"AUTH-{self.request_calls}"
        return PaymentInitiationResult(
            redirect_url=self.build_startpay_url(authority),
            authority=authority,
            raw_response={"code": 100},
        )

    def verify_payment(self, **kwargs):
        self.verify_calls += 1
        return PaymentVerificationResult(
            success=True,
            ref_id="REF-1",
            message=None,
            raw_response={"code": 100},
        )


class AccessPaymentSecurityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            fullname="Payment Security User",
            phone="09306612130",
            password="StrongPass123",
        )
        self.document = ClientDocument.objects.create(
            user=self.user,
            uploaded_by=self.user,
            title="Paid file",
            file=SimpleUploadedFile("paid.txt", b"protected"),
            requires_payment=True,
            price=120000,
        )
        self.program = WorkoutProgram.objects.create(
            user=self.user,
            title="Paid program",
            is_published=True,
            requires_payment=True,
            price=240000,
        )

    def test_document_initiation_is_idempotent_and_reuses_authority(self):
        provider = FakePaymentProvider()
        service = AccessPaymentService(provider=provider)

        first = service.initiate_document(
            document_id=self.document.pk,
            user=self.user,
            callback_url="https://egofit.ir/document/callback/",
        )
        second = service.initiate_document(
            document_id=self.document.pk,
            user=self.user,
            callback_url="https://egofit.ir/document/callback/",
        )

        self.assertEqual(provider.request_calls, 1)
        self.assertEqual(first.payment_id, second.payment_id)
        self.assertEqual(first.redirect_url, second.redirect_url)
        self.assertEqual(ClientDocumentPayment.objects.filter(document=self.document).count(), 1)

    def test_program_callback_is_idempotent_and_verifies_provider_once(self):
        provider = FakePaymentProvider()
        service = AccessPaymentService(provider=provider)
        initiated = service.initiate_program(
            program_id=self.program.pk,
            user=self.user,
            callback_url="https://egofit.ir/program/callback/",
        )

        first = service.verify_program(authority="AUTH-1", status="OK")
        second = service.verify_program(authority="AUTH-1", status="OK")

        self.assertEqual(initiated.redirect_url, "https://pay.example/start/AUTH-1")
        self.assertEqual(provider.verify_calls, 1)
        self.assertEqual(first.state, "paid")
        self.assertEqual(second.state, "already_paid")
        self.assertEqual(
            WorkoutProgramPayment.objects.filter(program=self.program, status=WorkoutProgramPayment.Status.PAID).count(),
            1,
        )


class OtpSecurityTests(TestCase):
    def test_otp_code_uses_secure_random_source(self):
        service = OTPService(sms_service=type("Sms", (), {"send_verification_sms": lambda *_: True})())
        with patch("account.services.otp_service.randbelow", return_value=0) as secure_random:
            result = service.create_otp("09306612131")

        self.assertEqual(result.code, 10000)
        secure_random.assert_called_once_with(90000)

    def test_web_otp_has_ip_and_phone_quota(self):
        cache.clear()
        request = RequestFactory().post("/accounts/register/", REMOTE_ADDR="198.51.100.20")

        for _ in range(5):
            enforce_web_otp_rate_limit(request, "09306612132")

        with self.assertRaises(OTPRateLimitExceededException) as raised:
            enforce_web_otp_rate_limit(request, "09306612132")

        self.assertIn("تعداد درخواست", str(raised.exception))
        cache.clear()
