from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from django.urls import reverse
from django.utils import timezone

from api.auth import _hash_token, issue_token_pair
from api.models import ApiToken
from api.tests_shared import ApiTestCase


class ApiAuthenticationFlowTests(ApiTestCase):
    def test_register_creates_user_and_returns_token_pair(self):
        response = self.post_json(
            "api:register",
            {
                "fullname": "newapiuser",
                "phone": "09120000303",
                "password": "StrongPass456",
                "device_name": "test-device",
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertIn("access_token", response.json()["data"])
        self.assertIn("refresh_token", response.json()["data"])
        self.assertTrue(self.user.__class__.objects.filter(phone="09120000303").exists())

    def test_register_rejects_duplicate_phone(self):
        response = self.post_json(
            "api:register",
            {
                "fullname": "anotherapiuser",
                "phone": self.user.phone,
                "password": "StrongPass456",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "request_rejected")

    def test_login_rejects_invalid_credentials(self):
        response = self.post_json(
            "api:login",
            {"fullname": self.user.fullname, "password": "WrongPass123"},
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["code"], "invalid_credentials")

    def test_otp_verify_issues_tokens_and_consumes_otp(self):
        otp = SimpleNamespace(phone=self.user.phone)
        with (
            patch("api.views.otp_service.validate_otp", return_value=otp) as validate_otp,
            patch("api.views.otp_service.consume_otp") as consume_otp,
        ):
            response = self.post_json(
                "api:otp_verify",
                {"verification_token": "verification-token", "code": "12345"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("access_token", response.json()["data"])
        validate_otp.assert_called_once_with(token="verification-token", code=12345)
        consume_otp.assert_called_once_with(otp)

    def test_revoked_access_token_cannot_authenticate(self):
        access_token = self.tokens["access_token"]
        ApiToken.objects.filter(token_hash=_hash_token(access_token)).update(revoked_at=timezone.now())

        response = self.client.get(reverse("api:me"), **self.headers)

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["code"], "authentication_required")

    def test_logout_revokes_the_authenticated_token_family(self):
        access = ApiToken.objects.get(token_hash=_hash_token(self.tokens["access_token"]))

        response = self.post_json(
            "api:logout",
            {"refresh_token": self.tokens["refresh_token"]},
            **self.headers,
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(ApiToken.objects.filter(family_id=access.family_id, revoked_at__isnull=True).exists())

    def test_password_change_revokes_existing_tokens(self):
        response = self.post_json(
            "api:password_change",
            {"old_password": "StrongPass123", "new_password": "NewStrongPass456"},
            **self.headers,
        )

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NewStrongPass456"))
        self.assertFalse(ApiToken.objects.filter(user=self.user, revoked_at__isnull=True).exists())

    def test_password_reset_does_not_disclose_unknown_phone(self):
        result = SimpleNamespace(token="reset-token")
        with patch("api.views.otp_service.create_otp", return_value=result):
            existing = self.post_json("api:password_reset_request", {"phone": self.user.phone})
            unknown = self.post_json("api:password_reset_request", {"phone": "09129999999"})

        self.assertEqual(existing.status_code, 200)
        self.assertIn("verification_token", existing.json()["data"])
        self.assertEqual(unknown.status_code, 202)
        self.assertNotIn("verification_token", unknown.json()["data"])

    def test_malformed_json_returns_validation_error(self):
        response = self.client.post(
            reverse("api:login"),
            data="{invalid",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "validation_error")
