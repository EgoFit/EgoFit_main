from __future__ import annotations

from django.conf import settings
from django.db import models


class ApiToken(models.Model):
    """A revocable, hashed bearer token for API clients.

    The raw token is never persisted. It is returned only when the token is
    created and clients must store it securely.
    """

    class TokenType(models.TextChoices):
        ACCESS = "access", "Access"
        REFRESH = "refresh", "Refresh"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="api_tokens")
    token_hash = models.CharField(max_length=64, unique=True, db_index=True)
    token_type = models.CharField(max_length=8, choices=TokenType.choices, default=TokenType.ACCESS, db_index=True)
    family_id = models.CharField(max_length=32, db_index=True)
    name = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(db_index=True)
    revoked_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "revoked_at", "expires_at"], name="api_apitoke_user_id_9a44a5_idx"),
            models.Index(fields=["family_id", "revoked_at"], name="api_apitoke_family__b5d394_idx"),
        ]

    @property
    def is_active(self) -> bool:
        from django.utils import timezone

        return self.revoked_at is None and self.expires_at > timezone.now() and self.user.is_active
