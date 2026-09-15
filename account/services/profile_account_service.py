from __future__ import annotations

from typing import Any, Callable

from django.db import transaction
from django.utils.translation import gettext_lazy as _

from account.exceptions import AuthenticationException, PasswordResetException, PhoneAlreadyExistsException
from account.models import User
from account.repositories.user_repository import UserRepository
from account.selectors.course_selector import CourseSelector
from account.selectors.user_selector import UserSelector
from account.services.notification_service import NotificationService
from account.services.otp_service import OTPService
from account.services.password_service import PasswordService
from account.services.session_service import SessionService


class ProfileAccountService:
    """Account mutations and profile-related read selectors."""

    def __init__(
        self,
        *,
        otp_service: OTPService,
        session_service: SessionService,
        user_repository: UserRepository,
        notification_service: NotificationService,
        password_service: PasswordService,
    ):
        self.otp_service = otp_service
        self.session_service = session_service
        self.user_repository = user_repository
        self.notification_service = notification_service
        self.password_service = password_service

    def get_learning_courses(self, user: Any):
        """Return courses currently available to the user."""
        return UserSelector.get_learning_courses(user)

    def get_paid_orders(self, user: Any):
        """Return paid orders belonging to the user."""
        return UserSelector.get_paid_orders(user)

    def get_comments(self, user: Any):
        """Return the user's course comments."""
        return UserSelector.get_user_comments(user)

    def get_notifications_feed(self, user: Any):
        """Return notifications for the profile notifications page."""
        return self.notification_service.get_profile_notifications(user)

    def request_phone_change(
        self,
        *,
        user: Any,
        new_phone: str,
        session: Any,
        otp_creator: Callable[[str], str] | None = None,
    ) -> str:
        """Create an OTP-backed pending phone change without mutating the user."""
        if self.user_repository.phone_exists(new_phone, exclude_user_id=user.pk):
            raise PhoneAlreadyExistsException(_("این شماره تماس قبلا ثبت شده است."))

        if otp_creator is None:
            from account.services import create_and_send_otp as otp_creator

        token = otp_creator(new_phone)
        self.session_service.set_pending_phone_change(session, token=token, phone=new_phone)
        return token

    @transaction.atomic
    def confirm_phone_change(self, *, user: Any, token: str, code: int, session: Any):
        """Validate the pending OTP and atomically update the user's phone."""
        pending_token, pending_phone = self.session_service.get_pending_phone_change(session)
        if token != pending_token or not pending_phone:
            raise AuthenticationException(_("درخواست تغییر شماره معتبر نیست."))

        otp = self.otp_service.validate_otp(token=token, code=code)
        if otp.phone != pending_phone or self.user_repository.phone_exists(pending_phone, exclude_user_id=user.pk):
            self.otp_service.consume_otp(otp)
            raise PhoneAlreadyExistsException(_("شماره تماس جدید معتبر نیست."))

        user.phone = pending_phone
        user.save(update_fields=["phone"])
        self.otp_service.consume_otp(otp)
        self.session_service.clear_pending_phone_change(session)
        return user

    def request_password_reset(
        self,
        *,
        phone: str,
        session: Any,
        otp_creator: Callable[[str], str] | None = None,
    ) -> str:
        """Create a password-reset OTP only for an existing account."""
        try:
            self.user_repository.get_by_phone(phone)
        except User.DoesNotExist as exc:
            raise PasswordResetException(_("حسابی با این شماره تماس پیدا نشد.")) from exc
        if otp_creator is None:
            from account.services import create_and_send_otp as otp_creator

        token = otp_creator(phone)
        self.session_service.set_password_reset_token(session, token=token)
        return token

    @transaction.atomic
    def confirm_password_reset(self, *, token: str, code: int, new_password: str, session: Any):
        """Validate the reset OTP, set the new password, and clear its session token."""
        session_token = self.session_service.get_password_reset_token(session)
        if token != session_token:
            raise AuthenticationException(_("درخواست بازیابی رمز عبور معتبر نیست."))

        otp = self.otp_service.validate_otp(token=token, code=code)
        try:
            user = self.user_repository.get_by_phone(otp.phone)
        except User.DoesNotExist as exc:
            self.otp_service.consume_otp(otp)
            raise PasswordResetException(_("حساب کاربری یافت نشد.")) from exc
        self.password_service.reset_password(user=user, new_password=new_password)
        self.otp_service.consume_otp(otp)
        self.session_service.clear_password_reset_token(session)
        return user

    @transaction.atomic
    def update_profile(self, *, form: Any):
        """Persist a validated profile form."""
        return form.save()

    def update_profile_metric(self, *, user: Any, field_name: str, value: Any):
        """Persist one allowlisted profile metric selected by the view."""
        setattr(user, field_name, value)
        user.save(update_fields=[field_name])
        return user

    @transaction.atomic
    def add_free_course_to_profile(self, *, user: Any, series_id: int, series: Any = None):
        """Grant a free course to a user idempotently."""
        from home.models import UserCourse

        series = series or CourseSelector.get_free_series(series_id)
        if series is None:
            raise AuthenticationException(_("دوره مورد نظر یافت نشد."))
        return UserCourse.objects.get_or_create(user=user, series=series)

    def create_course_request_notification(self, *, user: Any, course: Any):
        """Create the notification generated by a course request."""
        return self.notification_service.create_course_request_notification(user=user, course_title=course.title)
