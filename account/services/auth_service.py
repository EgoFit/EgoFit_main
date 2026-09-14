from __future__ import annotations

from django.contrib.auth import authenticate
from django.db import transaction

from account.exceptions import AuthenticationException, PhoneAlreadyExistsException
from account.repositories.user_repository import UserRepository


class AuthService:
    def __init__(self, user_repository: UserRepository | None = None):
        self.user_repository = user_repository or UserRepository()

    @transaction.atomic
    def register_user(self, *, fullname: str, phone: str, password: str):
        if self.user_repository.fullname_exists(fullname):
            raise AuthenticationException("این نام کاربری قبلا ثبت شده است.")
        if self.user_repository.phone_exists(phone):
            raise PhoneAlreadyExistsException("این شماره تماس قبلا ثبت شده است.")
        return self.user_repository.create_user(fullname=fullname, phone=phone, password=password)

    def authenticate_user(self, *, fullname: str, password: str):
        user = authenticate(username=fullname, password=password)
        if user is None:
            raise AuthenticationException("نام کاربری یا کلمه عبور اشتباه است.")
        return user

    def get_or_create_otp_user(self, *, phone: str):
        return self.user_repository.get_or_create_by_phone(phone, defaults={"fullname": phone})

