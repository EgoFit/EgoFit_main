from __future__ import annotations

from unittest.mock import patch

from django.urls import reverse

from account.models import ClientDocument, ClientDocumentPayment
from api.tests_shared import ApiTestCase
from cart.models import DiscountCode, Order
from cart.providers.base import PaymentInitiationResult, PaymentVerificationResult


class ApiPaymentTests(ApiTestCase):
    def make_order(self):
        return Order.objects.create(
            user=self.user,
            subtotal_price=1000,
            total_price=1000,
        )

    def test_order_payment_starts_provider_payment_without_network(self):
        order = self.make_order()
        provider_result = PaymentInitiationResult(
            redirect_url="https://sandbox.zarinpal.com/pg/StartPay/AUTH-ORDER",
            authority="AUTH-ORDER",
            raw_response={},
        )

        with patch("api.views.payment_service.provider.request_payment", return_value=provider_result) as request_payment:
            response = self.client.post(
                reverse("api:order_payment", kwargs={"pk": order.pk}),
                **self.headers,
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["redirect_url"], provider_result.redirect_url)
        request_payment.assert_called_once()
        order.refresh_from_db()
        self.assertEqual(order.authority, "AUTH-ORDER")
        self.assertEqual(order.status, Order.PaymentStatus.PAYMENT_INITIATED)

    def test_order_payment_callback_marks_order_paid(self):
        order = self.make_order()
        order.mark_payment_initiated("AUTH-VERIFY")
        verification = PaymentVerificationResult(
            success=True,
            ref_id="REF-123",
            message=None,
            raw_response={},
        )

        with patch("api.views.payment_service.provider.verify_payment", return_value=verification) as verify_payment:
            response = self.client.get(
                reverse("api:payment_verify"),
                {"Authority": "AUTH-VERIFY", "Status": "OK"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["state"], "paid")
        self.assertEqual(response.json()["data"]["ref_id"], "REF-123")
        verify_payment.assert_called_once_with(amount=1000, authority="AUTH-VERIFY")
        order.refresh_from_db()
        self.assertTrue(order.is_paid)
        self.assertEqual(order.ref_id, "REF-123")

    def test_order_payment_callback_marks_cancelled_payment_failed(self):
        order = self.make_order()
        order.mark_payment_initiated("AUTH-CANCEL")

        response = self.client.get(
            reverse("api:payment_verify"),
            {"Authority": "AUTH-CANCEL", "Status": "CANCEL"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["state"], "failed")
        order.refresh_from_db()
        self.assertEqual(order.status, Order.PaymentStatus.FAILED)

    def test_document_payment_starts_and_verifies_with_mock_provider(self):
        document = ClientDocument.objects.create(
            user=self.user,
            uploaded_by=self.user,
            title="Paid report",
            file="client_media/documents/report.pdf",
            requires_payment=True,
            price=2500,
        )
        provider_result = PaymentInitiationResult(
            redirect_url="https://sandbox.zarinpal.com/pg/StartPay/AUTH-DOC",
            authority="AUTH-DOC",
            raw_response={},
        )

        with patch("api.views.access_payment_service.provider.request_payment", return_value=provider_result):
            response = self.client.post(
                reverse("api:document_payment", kwargs={"pk": document.pk}),
                **self.headers,
            )

        self.assertEqual(response.status_code, 200)
        payment_id = response.json()["data"]["payment_id"]
        payment = ClientDocumentPayment.objects.get(pk=payment_id)
        self.assertEqual(payment.authority, "AUTH-DOC")
        self.assertEqual(payment.status, ClientDocumentPayment.Status.INITIATED)

        verification = PaymentVerificationResult(
            success=True,
            ref_id="DOC-REF",
            message=None,
            raw_response={},
        )
        with patch("api.views.access_payment_service.provider.verify_payment", return_value=verification):
            verified = self.client.get(
                reverse("api:document_payment_verify"),
                {"Authority": "AUTH-DOC", "Status": "OK"},
            )

        self.assertEqual(verified.status_code, 200)
        self.assertEqual(verified.json()["data"]["state"], "paid")
        payment.refresh_from_db()
        self.assertEqual(payment.status, ClientDocumentPayment.Status.PAID)
        self.assertEqual(payment.ref_id, "DOC-REF")

    def test_document_payment_rejects_free_document(self):
        document = ClientDocument.objects.create(
            user=self.user,
            uploaded_by=self.user,
            title="Free report",
            file="client_media/documents/report.txt",
        )

        response = self.client.post(
            reverse("api:document_payment", kwargs={"pk": document.pk}),
            **self.headers,
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "payment_not_required")

    def test_discount_code_is_applied_and_invalid_code_is_rejected(self):
        order = self.make_order()
        discount = DiscountCode.objects.create(name="SAVE20", percentage=20, quantity=1)

        response = self.post_json(
            "api:order_discount",
            {"discount_code": "save20"},
            url_kwargs={"pk": order.pk},
            **self.headers,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["discount_amount"], 200)
        order.refresh_from_db()
        discount.refresh_from_db()
        self.assertEqual(order.total_price, 800)
        self.assertEqual(discount.quantity, 0)

        another_order = self.make_order()
        invalid = self.post_json(
            "api:order_discount",
            {"discount_code": "DOES-NOT-EXIST"},
            url_kwargs={"pk": another_order.pk},
            **self.headers,
        )
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid.json()["error"]["code"], "validation_error")
