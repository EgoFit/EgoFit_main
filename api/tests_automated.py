"""Focused automated coverage for API authentication, validation and writes."""

import json

from django.test import TestCase
from django.urls import reverse

from account.models import User
from api.auth import issue_token_pair


class ApiEndpointTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            fullname="کاربر API",
            phone="09120000201",
            password="StrongPass123",
        )
        self.tokens = issue_token_pair(user=self.user, name="automated-tests")
        self.headers = {"HTTP_AUTHORIZATION": f"Bearer {self.tokens['access_token']}"}

    def post_json(self, name, payload, **extra):
        return self.client.post(
            reverse(name),
            data=json.dumps(payload),
            content_type="application/json",
            **extra,
        )

    def test_health_allows_get_and_rejects_other_methods(self):
        response = self.client.get(reverse("api:health"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["status"], "ok")

        response = self.client.post(reverse("api:health"), data="{}", content_type="application/json")
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response["Allow"], "GET")

    def test_login_issues_bearer_token_pair(self):
        response = self.post_json(
            "api:login",
            {"fullname": self.user.fullname, "password": "StrongPass123", "device_name": "phone"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("access_token", response.json()["data"])
        self.assertIn("refresh_token", response.json()["data"])

    def test_browser_session_cannot_authenticate_api(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("api:me"))

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["code"], "authentication_required")

    def test_bearer_user_can_update_own_profile(self):
        response = self.client.patch(
            reverse("api:me"),
            data=json.dumps({"first_name": "نام جدید"}),
            content_type="application/json",
            **self.headers,
        )

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "نام جدید")

    def test_api_rejects_unknown_fields_and_invalid_metrics(self):
        response = self.post_json(
            "api:login",
            {"fullname": self.user.fullname, "password": "StrongPass123", "is_admin": True},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "validation_error")

        response = self.client.patch(
            reverse("api:metric", kwargs={"metric_name": "weight"}),
            data=json.dumps({"weight": 1}),
            content_type="application/json",
            **self.headers,
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "validation_error")
