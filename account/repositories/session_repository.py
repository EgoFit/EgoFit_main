from __future__ import annotations

from account.models import UserSession, User


class SessionRepository:
    def upsert_login_session(
        self,
        *,
        user: User,
        session_key: str,
        ip_address: str,
        user_agent: str,
    ) -> UserSession:
        session, _ = UserSession.objects.update_or_create(
            user=user,
            session_key=session_key,
            defaults={
                "ip_address": ip_address,
                "user_agent": user_agent[:255],
            },
        )
        return session

