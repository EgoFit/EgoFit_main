from __future__ import annotations

from account.constants import (
    SESSION_PASSWORD_RESET_TOKEN_KEY,
    SESSION_PHONE_CHANGE_TOKEN_KEY,
    SESSION_PHONE_CHANGE_VALUE_KEY,
)
from account.exceptions import SessionValidationException
from account.repositories.session_repository import SessionRepository
from account.utils import ensure_session_key, get_client_ip
from account.tasks.dispatch import dispatch_task
from account.tasks.session_tasks import log_user_session


class SessionService:
    def __init__(self, repository: SessionRepository | None = None):
        self.repository = repository or SessionRepository()

    def log_login_session(self, *, user, request) -> None:
        session_key = ensure_session_key(request)
        self.repository.upsert_login_session(
            user=user,
            session_key=session_key,
            ip_address=get_client_ip(request),
            user_agent=(request.META.get("HTTP_USER_AGENT") or "")[:255],
        )

    def schedule_login_session_log(self, *, user_id: int, session_key: str, ip_address: str, user_agent: str) -> None:
        dispatch_task(log_user_session, user_id, session_key, ip_address, user_agent)

    def queue_login_session_log(self, *, user, request) -> None:
        session_key = request.session.session_key
        if not session_key:
            return
        dispatch_task(
            log_user_session,
            user.pk,
            session_key,
            get_client_ip(request),
            (request.META.get("HTTP_USER_AGENT") or "")[:255],
        )

    def set_pending_phone_change(self, session, *, token: str, phone: str) -> None:
        session[SESSION_PHONE_CHANGE_TOKEN_KEY] = token
        session[SESSION_PHONE_CHANGE_VALUE_KEY] = phone

    def get_pending_phone_change(self, session) -> tuple[str | None, str | None]:
        return (
            session.get(SESSION_PHONE_CHANGE_TOKEN_KEY),
            session.get(SESSION_PHONE_CHANGE_VALUE_KEY),
        )

    def clear_pending_phone_change(self, session) -> None:
        session.pop(SESSION_PHONE_CHANGE_TOKEN_KEY, None)
        session.pop(SESSION_PHONE_CHANGE_VALUE_KEY, None)

    def set_password_reset_token(self, session, *, token: str) -> None:
        session[SESSION_PASSWORD_RESET_TOKEN_KEY] = token

    def get_password_reset_token(self, session) -> str | None:
        return session.get(SESSION_PASSWORD_RESET_TOKEN_KEY)

    def clear_password_reset_token(self, session) -> None:
        session.pop(SESSION_PASSWORD_RESET_TOKEN_KEY, None)

    def validate_session_token(self, session, *, expected_token: str | None, session_key_name: str) -> None:
        current_token = session.get(session_key_name)
        if not current_token or current_token != expected_token:
            raise SessionValidationException("درخواست معتبر نیست.")
