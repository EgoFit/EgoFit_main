from __future__ import annotations

from typing import Any, Callable

from account.repositories.user_repository import UserRepository
from account.services.notification_service import NotificationService
from account.services.otp_service import OTPService
from account.services.password_service import PasswordService
from account.services.profile_account_service import ProfileAccountService
from account.services.profile_analysis_service import ProfileAnalysisService
from account.services.profile_dashboard_service import ProfileDashboardService
from account.services.session_service import SessionService


class ProfileService:
    """Compatibility facade for the focused profile services.

    Dashboard, body-composition analysis, and account mutations live in
    dedicated services. This facade preserves the existing public API while
    callers migrate gradually.
    """

    CIRCUMFERENCE_FIELD_LABELS = ProfileAnalysisService.CIRCUMFERENCE_FIELD_LABELS
    CALIPER_FIELD_LABELS = ProfileAnalysisService.CALIPER_FIELD_LABELS
    ANALYSIS_METRIC_OPTIONS = ProfileAnalysisService.ANALYSIS_METRIC_OPTIONS
    BODY_FAT_FORMULA_OPTIONS = ProfileAnalysisService.BODY_FAT_FORMULA_OPTIONS

    def __init__(
        self,
        *,
        otp_service: OTPService | None = None,
        session_service: SessionService | None = None,
        user_repository: UserRepository | None = None,
        notification_service: NotificationService | None = None,
        password_service: PasswordService | None = None,
    ):
        self.otp_service = otp_service or OTPService()
        self.session_service = session_service or SessionService()
        self.user_repository = user_repository or UserRepository()
        self.notification_service = notification_service or NotificationService()
        self.password_service = password_service or PasswordService()
        self.dashboard_service = ProfileDashboardService(notification_service=self.notification_service)
        self.analysis_service = ProfileAnalysisService()
        self.account_service = ProfileAccountService(
            otp_service=self.otp_service,
            session_service=self.session_service,
            user_repository=self.user_repository,
            notification_service=self.notification_service,
            password_service=self.password_service,
        )
    def get_dashboard_context(self, user: Any) -> dict[str, Any]:
        """Return the dashboard payload produced by the dashboard service."""
        return self.dashboard_service.get_dashboard_context(user)

    def get_dashboard_feed(
        self,
        user: Any,
        *,
        recent_notifications: list[Any] | None = None,
    ) -> dict[str, Any] | None:
        """Return the dashboard feed produced by the dashboard service."""
        return self.dashboard_service.get_dashboard_feed(
            user,
            recent_notifications=recent_notifications,
        )

    def get_profile_metrics(self, user: Any) -> list[dict[str, Any]]:
        """Return editable profile metrics and derived values."""
        return self.dashboard_service.get_profile_metrics(user)

    def get_profile_overview_cards(self, user: Any) -> list[dict[str, Any]]:
        """Return the compact profile overview cards."""
        return self.dashboard_service.get_profile_overview_cards(user)

    @staticmethod
    def _parse_birth_date_jalali(birth_date: str | None) -> int | None:
        """Keep the former private helper available during service migration."""
        return ProfileDashboardService._parse_birth_date_jalali(birth_date)

    def get_analysis_metric_series(
        self,
        user: Any,
        *,
        body_fat_formula: str | None = None,
    ) -> dict[str, Any]:
        """Return body-composition trend data for the profile analysis page."""
        return self.analysis_service.get_analysis_metric_series(
            user,
            body_fat_formula=body_fat_formula,
        )

    def get_analysis_context(
        self,
        user: Any,
        *,
        metric: str | None = None,
        start: str | None = None,
        end: str | None = None,
        date: str | None = None,
        circ_date: str | None = None,
        body_fat_formula: str | None = None,
        caliper_date: str | None = None,
        use_full_chart_range: bool = False,
    ) -> dict[str, Any]:
        """Return the selected body-composition analysis context."""
        return self.analysis_service.get_analysis_context(
            user,
            metric=metric,
            start=start,
            end=end,
            date=date,
            circ_date=circ_date,
            body_fat_formula=body_fat_formula,
            caliper_date=caliper_date,
            use_full_chart_range=use_full_chart_range,
        )

    def get_analysis_dashboard_data(
        self,
        user: Any,
        *,
        body_fat_formula: str | None = None,
    ) -> dict[str, Any]:
        """Return analysis cards, history rows, and gauges."""
        return self.analysis_service.get_analysis_dashboard_data(
            user,
            body_fat_formula=body_fat_formula,
        )

    def get_learning_courses(self, user: Any):
        """Return courses currently available to the user."""
        return self.account_service.get_learning_courses(user)

    def get_paid_orders(self, user: Any):
        """Return paid orders belonging to the user."""
        return self.account_service.get_paid_orders(user)

    def get_comments(self, user: Any):
        """Return the user's course comments."""
        return self.account_service.get_comments(user)

    def get_notifications_feed(self, user: Any):
        """Return notifications for the profile notifications page."""
        return self.account_service.get_notifications_feed(user)

    def request_phone_change(
        self,
        *,
        user: Any,
        new_phone: str,
        session: Any,
        otp_creator: Callable[[str], str] | None = None,
    ) -> str:
        """Create an OTP-backed pending phone change."""
        return self.account_service.request_phone_change(
            user=user,
            new_phone=new_phone,
            session=session,
            otp_creator=otp_creator,
        )

    def confirm_phone_change(
        self,
        *,
        user: Any,
        token: str,
        code: int,
        session: Any,
    ):
        """Confirm a pending phone change."""
        return self.account_service.confirm_phone_change(
            user=user,
            token=token,
            code=code,
            session=session,
        )

    def request_password_reset(
        self,
        *,
        phone: str,
        session: Any,
        otp_creator: Callable[[str], str] | None = None,
    ) -> str:
        """Create a password-reset OTP."""
        return self.account_service.request_password_reset(
            phone=phone,
            session=session,
            otp_creator=otp_creator,
        )

    def confirm_password_reset(
        self,
        *,
        token: str,
        code: int,
        new_password: str,
        session: Any,
    ):
        """Confirm a password reset and update the account password."""
        return self.account_service.confirm_password_reset(
            token=token,
            code=code,
            new_password=new_password,
            session=session,
        )

    def update_profile(self, *, form: Any):
        """Persist a validated profile form."""
        return self.account_service.update_profile(form=form)

    def update_profile_metric(self, *, user: Any, field_name: str, value: Any):
        """Persist one allowlisted profile metric."""
        return self.account_service.update_profile_metric(
            user=user,
            field_name=field_name,
            value=value,
        )

    def add_free_course_to_profile(
        self,
        *,
        user: Any,
        series_id: int,
        series: Any = None,
    ):
        """Grant a free course to a user idempotently."""
        return self.account_service.add_free_course_to_profile(
            user=user,
            series_id=series_id,
            series=series,
        )

    def create_course_request_notification(self, *, user: Any, course: Any):
        """Create the notification generated by a course request."""
        return self.account_service.create_course_request_notification(
            user=user,
            course=course,
        )
