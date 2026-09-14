from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from secrets import randbelow
from uuid import uuid4

from django.db import transaction
from django.utils import timezone

from account.constants import OTP_CODE_LENGTH, OTP_EXPIRATION_MINUTES, OTP_REQUEST_COOLDOWN_SECONDS
from account.exceptions import ExpiredOtpException, InvalidOtpException, OTPRateLimitExceededException, SMSProviderException
from account.tasks.dispatch import dispatch_task
from account.tasks.sms_tasks import send_verification_sms
from account.repositories.otp_repository import OTPRepository


@dataclass(frozen=True)
class OTPCreationResult:
    token: str
    code: int


@dataclass(frozen=True)
class OTPVerificationStatus:
    phone: str
    expires_in_seconds: int
    resend_cooldown_seconds: int
    can_resend: bool


class OTPService:
    def __init__(self, repository: OTPRepository | None = None, sms_service=None):
        self.repository = repository or OTPRepository()
        self.sms_service = sms_service

    def _generate_code(self) -> int:
        lower_bound = 10 ** (OTP_CODE_LENGTH - 1)
        upper_bound = (10**OTP_CODE_LENGTH) - 1
        return lower_bound + randbelow(upper_bound - lower_bound + 1)

    def _seconds_since_latest_otp(self, phone: str) -> int | None:
        latest_otp = self.repository.get_latest_for_phone(phone)
        if latest_otp is None:
            return None
        return int((timezone.now() - latest_otp.created_at).total_seconds())

    def _can_request_otp(self, phone: str) -> bool:
        if OTP_REQUEST_COOLDOWN_SECONDS <= 0:
            return True
        elapsed = self._seconds_since_latest_otp(phone)
        if elapsed is None:
            return True
        return elapsed >= OTP_REQUEST_COOLDOWN_SECONDS

    def _resend_cooldown_remaining(self, phone: str) -> int:
        if OTP_REQUEST_COOLDOWN_SECONDS <= 0:
            return 0
        elapsed = self._seconds_since_latest_otp(phone)
        if elapsed is None:
            return 0
        return max(0, OTP_REQUEST_COOLDOWN_SECONDS - elapsed)

    def get_verification_status(self, token: str) -> OTPVerificationStatus:
        otp = self.repository.get_by_token(token)
        now = timezone.now()
        expiration_at = otp.created_at + timedelta(minutes=OTP_EXPIRATION_MINUTES)
        expires_in_seconds = max(0, int((expiration_at - now).total_seconds()))
        resend_cooldown_seconds = self._resend_cooldown_remaining(otp.phone)
        return OTPVerificationStatus(
            phone=otp.phone,
            expires_in_seconds=expires_in_seconds,
            resend_cooldown_seconds=resend_cooldown_seconds,
            can_resend=resend_cooldown_seconds == 0,
        )

    def create_otp(self, phone: str) -> OTPCreationResult:
        if not self._can_request_otp(phone):
            remaining = self._resend_cooldown_remaining(phone)
            minutes = max(1, (remaining + 59) // 60)
            raise OTPRateLimitExceededException(f"لطفاً {minutes} دقیقه دیگر برای دریافت کد جدید صبر کنید.")

        with transaction.atomic():
            self.repository.delete_existing_for_phone(phone)
            token = uuid4().hex
            code = self._generate_code()
            self.repository.create(phone=phone, code=code, token=token)

        if self.sms_service is not None:
            try:
                self.sms_service.send_verification_sms(phone, code)
            except SMSProviderException:
                self.repository.delete_existing_for_phone(phone)
                raise
        else:
            dispatch_task(send_verification_sms, phone, code)

        return OTPCreationResult(token=token, code=code)

    @transaction.atomic
    def validate_otp(self, *, token: str, code: int, consume: bool = False):
        try:
            otp = self.repository.get_by_token_and_code_for_update(token=token, code=code)
        except Exception as exc:
            raise InvalidOtpException("کد وارد شده نادرست یا منقضی شده است.") from exc

        expiration_at = otp.created_at + timedelta(minutes=OTP_EXPIRATION_MINUTES)
        if timezone.now() > expiration_at:
            self.repository.delete(otp)
            raise ExpiredOtpException("کد وارد شده منقضی شده است.")

        if consume:
            self.repository.delete(otp)
        return otp

    def consume_otp(self, otp) -> None:
        self.repository.delete(otp)

    @transaction.atomic
    def resend_otp(self, *, token: str) -> str:
        otp = self.repository.get_by_token(token)
        return self.create_otp(otp.phone).token
