from __future__ import annotations

from django.db import transaction

from account.models import Otp


class OTPRepository:
    @transaction.atomic
    def create(self, *, phone: str, code: int, token: str) -> Otp:
        return Otp.objects.create(phone=phone, code=code, token=token)

    def delete_existing_for_phone(self, phone: str) -> int:
        deleted_count, _ = Otp.objects.filter(phone=phone).delete()
        return deleted_count

    def get_by_token_and_code(self, *, token: str, code: int) -> Otp:
        return Otp.objects.get(token=token, code=code)

    def get_by_token_and_code_for_update(self, *, token: str, code: int) -> Otp:
        return Otp.objects.select_for_update().get(token=token, code=code)

    def get_by_token(self, token: str) -> Otp:
        return Otp.objects.get(token=token)

    def delete(self, otp: Otp) -> None:
        otp.delete()

    def get_latest_for_phone(self, phone: str) -> Otp | None:
        return Otp.objects.filter(phone=phone).order_by("-created_at").first()
