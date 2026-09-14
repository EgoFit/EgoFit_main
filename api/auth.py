from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta
from uuid import uuid4

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from api.models import ApiToken


ACCESS_TOKEN_TTL_MINUTES = 15
REFRESH_TOKEN_TTL_DAYS = 30


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def issue_token(*, user, name: str = "", token_type: str = ApiToken.TokenType.ACCESS, family_id: str | None = None) -> tuple[ApiToken, str]:
    raw_token = secrets.token_urlsafe(48)
    if token_type == ApiToken.TokenType.ACCESS:
        expires_at = timezone.now() + timedelta(minutes=max(5, int(getattr(settings, "API_ACCESS_TOKEN_TTL_MINUTES", ACCESS_TOKEN_TTL_MINUTES))))
    else:
        ttl_days = max(1, int(getattr(settings, "API_REFRESH_TOKEN_TTL_DAYS", REFRESH_TOKEN_TTL_DAYS)))
        expires_at = timezone.now() + timedelta(days=ttl_days)
    token = ApiToken.objects.create(
        user=user,
        token_hash=_hash_token(raw_token),
        token_type=token_type,
        family_id=family_id or uuid4().hex,
        name=(name or "").strip()[:80],
        expires_at=expires_at,
    )
    return token, raw_token


def authenticate_bearer(raw_token: str | None):
    if not raw_token:
        return None
    token = (
        ApiToken.objects.select_related("user")
        .filter(token_hash=_hash_token(raw_token), token_type=ApiToken.TokenType.ACCESS, revoked_at__isnull=True, expires_at__gt=timezone.now(), user__is_active=True)
        .first()
    )
    if token is None:
        return None
    token.last_used_at = timezone.now()
    token.save(update_fields=["last_used_at"])
    return token


def issue_token_pair(*, user, name: str = "") -> dict:
    family_id = uuid4().hex
    _, access_token = issue_token(user=user, name=name, token_type=ApiToken.TokenType.ACCESS, family_id=family_id)
    _, refresh_token = issue_token(user=user, name=name, token_type=ApiToken.TokenType.REFRESH, family_id=family_id)
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "Bearer", "expires_in": max(5, int(getattr(settings, "API_ACCESS_TOKEN_TTL_MINUTES", ACCESS_TOKEN_TTL_MINUTES))) * 60}


def revoke_user_tokens(user) -> None:
    ApiToken.objects.filter(user=user, revoked_at__isnull=True).update(revoked_at=timezone.now())


@transaction.atomic
def rotate_token_pair(raw_refresh_token: str | None) -> dict | None:
    if not raw_refresh_token:
        return None
    token = ApiToken.objects.select_for_update().select_related("user").filter(
        token_hash=_hash_token(raw_refresh_token),
        token_type=ApiToken.TokenType.REFRESH,
        revoked_at__isnull=True,
        expires_at__gt=timezone.now(),
        user__is_active=True,
    ).first()
    if token is None:
        return None
    now = timezone.now()
    ApiToken.objects.filter(family_id=token.family_id, revoked_at__isnull=True).update(revoked_at=now)
    return issue_token_pair(user=token.user, name=token.name)
