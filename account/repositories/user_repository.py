from __future__ import annotations

from django.db import transaction

from account.models import User


class UserRepository:
    def phone_exists(self, phone: str, *, exclude_user_id: int | None = None) -> bool:
        queryset = User.objects.filter(phone=phone)
        if exclude_user_id is not None:
            queryset = queryset.exclude(pk=exclude_user_id)
        return queryset.exists()

    def fullname_exists(self, fullname: str, *, exclude_user_id: int | None = None) -> bool:
        queryset = User.objects.filter(fullname=fullname)
        if exclude_user_id is not None:
            queryset = queryset.exclude(pk=exclude_user_id)
        return queryset.exists()

    def email_exists(self, email: str, *, exclude_user_id: int | None = None) -> bool:
        queryset = User.objects.filter(email=email)
        if exclude_user_id is not None:
            queryset = queryset.exclude(pk=exclude_user_id)
        return queryset.exists()

    def get_by_phone(self, phone: str) -> User:
        return User.objects.get(phone=phone)

    def get_or_create_by_phone(self, phone: str, *, defaults: dict | None = None) -> tuple[User, bool]:
        defaults = defaults or {}
        return User.objects.get_or_create(phone=phone, defaults=defaults)

    @transaction.atomic
    def create_user(self, fullname: str, phone: str, password: str | None = None, **extra_fields) -> User:
        user = User(fullname=fullname, phone=phone, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save()
        return user

    def save(self, user: User, *, update_fields: list[str] | tuple[str, ...] | None = None) -> User:
        user.save(update_fields=update_fields)
        return user

