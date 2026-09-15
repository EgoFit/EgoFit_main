from __future__ import annotations

from django.urls import reverse

from account.models import ClientDocument, Notification, WorkoutProgram
from api.tests_shared import ApiTestCase
from cart.models import Order


class ApiOwnershipTests(ApiTestCase):
    def test_notification_listing_and_mark_read_are_user_scoped(self):
        own = Notification.objects.create(user=self.user, title="Own", message="Own message")
        other = Notification.objects.create(user=self.other_user, title="Other", message="Other message")

        response = self.client.get(reverse("api:notifications"), **self.headers)

        self.assertEqual(response.status_code, 200)
        ids = {item["id"] for item in response.json()["data"]["items"]}
        self.assertIn(own.pk, ids)
        self.assertNotIn(other.pk, ids)

        forbidden = self.client.post(
            reverse("api:notification_read", kwargs={"pk": other.pk}),
            **self.headers,
        )
        self.assertEqual(forbidden.status_code, 404)

        allowed = self.client.post(
            reverse("api:notification_read", kwargs={"pk": own.pk}),
            **self.headers,
        )
        self.assertEqual(allowed.status_code, 200)
        own.refresh_from_db()
        self.assertTrue(own.read)

    def test_program_listing_and_performance_are_user_scoped(self):
        foreign_program = WorkoutProgram.objects.create(
            user=self.other_user,
            title="Foreign program",
            is_published=True,
        )

        listing = self.client.get(reverse("api:programs"), **self.headers)
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.json()["data"]["items"], [])

        performance = self.post_json(
            "api:program_performance",
            {"records": []},
            url_kwargs={"pk": foreign_program.pk},
            **self.headers,
        )
        self.assertEqual(performance.status_code, 404)

    def test_document_download_and_payment_are_user_scoped(self):
        foreign_document = ClientDocument.objects.create(
            user=self.other_user,
            uploaded_by=self.other_user,
            title="Foreign document",
            file="client_media/documents/foreign.txt",
        )
        private_document = ClientDocument.objects.create(
            user=self.user,
            uploaded_by=self.user,
            title="Paid document",
            file="client_media/documents/paid.txt",
            requires_payment=True,
            price=1000,
        )

        forbidden_download = self.client.get(
            reverse("api:document_download", kwargs={"pk": foreign_document.pk}),
            **self.headers,
        )
        self.assertEqual(forbidden_download.status_code, 404)

        payment_required = self.client.get(
            reverse("api:document_download", kwargs={"pk": private_document.pk}),
            **self.headers,
        )
        self.assertEqual(payment_required.status_code, 403)
        self.assertEqual(payment_required.json()["error"]["code"], "payment_required")

    def test_order_discount_and_payment_are_user_scoped(self):
        foreign_order = Order.objects.create(
            user=self.other_user,
            subtotal_price=1000,
            total_price=1000,
        )

        discount = self.post_json(
            "api:order_discount",
            {"discount_code": "NOT-MINE"},
            url_kwargs={"pk": foreign_order.pk},
            **self.headers,
        )
        payment = self.post_json(
            "api:order_payment",
            {},
            url_kwargs={"pk": foreign_order.pk},
            **self.headers,
        )

        self.assertEqual(discount.status_code, 404)
        self.assertEqual(payment.status_code, 404)
