from __future__ import annotations

from django.db import transaction

from account.exceptions import AuthenticationException


class PasswordService:
    @transaction.atomic
    def change_password(self, *, user, old_password: str, new_password: str):
        if not user.check_password(old_password):
            raise AuthenticationException("کلمه عبور فعلی اشتباه است.")
        user.set_password(new_password)
        user.save(update_fields=["password"])
        return user

    @transaction.atomic
    def reset_password(self, *, user, new_password: str):
        user.set_password(new_password)
        user.save(update_fields=["password"])
        return user

