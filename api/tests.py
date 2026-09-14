from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from account.models import User
from api.auth import issue_token_pair
from api.models import ApiToken
from cart.card_models import Cart
from cart.models import Order
from home.models import SeriesModel


class ApiSecurityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            fullname="apiuser",
            phone="09120000001",
            password="StrongPass1",
        )
        self.other_user = User.objects.create_user(
            fullname="otheruser",
            phone="09120000002",
            password="StrongPass1",
        )
        self.access = issue_token_pair(user=self.user, name="test")
        self.headers = {"HTTP_AUTHORIZATION": f"Bearer {self.access['access_token']}"}

    def test_api_does_not_accept_browser_session_without_bearer_token(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("api:me"))
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["code"], "authentication_required")

    def test_refresh_rotation_revokes_old_token_family(self):
        response = self.client.post(
            reverse("api:refresh"),
            data={"refresh_token": self.access["refresh_token"]},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        rotated = response.json()["data"]
        self.assertNotEqual(rotated["refresh_token"], self.access["refresh_token"])

        replay = self.client.post(
            reverse("api:refresh"),
            data={"refresh_token": self.access["refresh_token"]},
            content_type="application/json",
        )
        self.assertEqual(replay.status_code, 401)

    def test_user_can_only_read_own_orders(self):
        own = Order.objects.create(user=self.user, subtotal_price=100, total_price=100, is_paid=True, status=Order.PaymentStatus.PAID)
        other = Order.objects.create(user=self.other_user, subtotal_price=200, total_price=200, is_paid=True, status=Order.PaymentStatus.PAID)
        response = self.client.get(reverse("api:orders"), **self.headers)
        self.assertEqual(response.status_code, 200)
        ids = {item["id"] for item in response.json()["data"]["items"]}
        self.assertIn(own.pk, ids)
        self.assertNotIn(other.pk, ids)

    def test_order_uses_current_catalog_price_not_session_price(self):
        course = SeriesModel.objects.create(
            title="Secure Course",
            author=self.user,
            main_price="1000",
            discount_price="800",
            free=False,
        )
        session = self.client.session
        session["cart"] = {str(course.pk): {"id": str(course.pk), "quantity": 1, "price": "1"}}
        session.save()
        response = self.client.post(reverse("api:order_create"), **self.headers)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["data"]["order"]["subtotal_price"], 800)

    @patch("api.views.otp_service.create_otp")
    def test_otp_request_does_not_expose_code(self, create_otp):
        class Result:
            token = "verification-token"

        Result.code = 12345
        create_otp.return_value = Result()
        response = self.client.post(
            reverse("api:otp_request"),
            data={"phone": "09120000003"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("code", response.json()["data"])
