from __future__ import annotations

from sport_shop.task_queue import shared_task

from account.models import User
from account.repositories.session_repository import SessionRepository


@shared_task(name="account.log_user_session")
def log_user_session(user_id: int, session_key: str, ip_address: str, user_agent: str):
    user = User.objects.get(pk=user_id)
    return SessionRepository().upsert_login_session(
        user=user,
        session_key=session_key,
        ip_address=ip_address,
        user_agent=user_agent,
    )
