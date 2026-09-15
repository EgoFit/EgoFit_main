from __future__ import annotations

import json

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from account.models import User
from api.auth import issue_token_pair


class ApiTestCase(TestCase):
    """Shared authenticated API client and user fixtures for endpoint tests."""

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            fullname="api-test-user",
            phone="09120000301",
            password="StrongPass123",
        )
        self.other_user = User.objects.create_user(
            fullname="api-other-user",
            phone="09120000302",
            password="StrongPass123",
        )
        self.tokens = issue_token_pair(user=self.user, name="api-tests")
        self.headers = {"HTTP_AUTHORIZATION": f"Bearer {self.tokens['access_token']}"}

    def post_json(self, name: str, payload: dict, url_kwargs: dict | None = None, **extra):
        return self.client.post(
            reverse(name, kwargs=url_kwargs or {}),
            data=json.dumps(payload),
            content_type="application/json",
            **extra,
        )

    def patch_json(self, name: str, payload: dict, url_kwargs: dict | None = None, **extra):
        return self.client.patch(
            reverse(name, kwargs=url_kwargs or {}),
            data=json.dumps(payload),
            content_type="application/json",
            **extra,
        )
