from __future__ import annotations

import jdatetime
from django.db.models import Count, Q
from django.utils.translation import gettext_lazy as _

from account.interfaces import PersonalizedSmsMessage
from account.admin_forms import AdminBulkCoachAssignForm
from account.models import (
    BirthdaySmsLog,
    BodyCircumferenceMeasurement,
    CaliperMeasurement,
    ClientDocument,
    ClientMedia,
    User,
    WorkoutProgram,
)
from account.services.coach_request_service import CoachRequestService
from account.services.notification_service import NotificationService
from account.services.profile_service import ProfileService
from account.services.sms_service import SmsService
from account.utils import is_birthday_today


class AdminPortalService:
    def __init__(
        self,
        profile_service: ProfileService | None = None,
        coach_request_service: CoachRequestService | None = None,
        sms_service: SmsService | None = None,
    ):
        self.profile_service = profile_service or ProfileService()
        self.coach_request_service = coach_request_service or CoachRequestService()
        self.sms_service = sms_service or SmsService()

    def search_users(self, *, query: str) -> list[User]:
        query = (query or "").strip()
        if not query:
            return []

        filters = Q(fullname__icontains=query) | Q(phone__icontains=query) | Q(display_name__icontains=query)
        if query.isdigit():
            filters |= Q(pk=int(query))
        return list(User.objects.filter(filters).order_by("fullname")[:20])

    def get_dashboard_context(self) -> dict:
        users = User.objects.exclude(is_admin=True)
        today = jdatetime.date.today()
        month_values = {str(today.month), f"{today.month:02d}"}
        day_values = {str(today.day), f"{today.day:02d}"}
        birthday_suffixes = {
            f"{separator}{month}{separator}{day}"
            for separator in ("/", "-")
            for month in month_values
            for day in day_values
        }
        birthday_filters = Q()
        for suffix in birthday_suffixes:
            birthday_filters |= Q(birth_date_jalali__endswith=suffix)

        stats = users.aggregate(
            total=Count("pk"),
            completed=Count(
                "pk",
                filter=Q(height_cm__isnull=False, weight_kg__isnull=False),
            ),
        )
        admin_users = list(User.objects.filter(is_admin=True).order_by("fullname"))
        birthday_candidates = User.objects.exclude(is_admin=True).filter(birthday_filters)
        return {
            "total_users": stats["total"],
            "completed_profiles_count": stats["completed"],
            "recent_users": list(users.order_by("-id")[:6]),
            "admin_users": admin_users,
            "admin_users_count": len(admin_users),
            "pending_coach_requests": list(self.coach_request_service.get_pending_queryset()[:10]),
            "pending_coach_requests_count": self.coach_request_service.get_pending_count(),
            "birthday_users": [
                user
                for user in birthday_candidates
                if is_birthday_today(user.birth_date_jalali)
            ],
        }

    def get_birthday_users(self) -> list[User]:
        today = jdatetime.date.today()
        month_values = {str(today.month), f"{today.month:02d}"}
        day_values = {str(today.day), f"{today.day:02d}"}
        suffixes = {
            f"{separator}{month}{separator}{day}"
            for separator in ("/", "-")
            for month in month_values
            for day in day_values
        }
        birthday_filter = Q()
        for suffix in suffixes:
            birthday_filter |= Q(birth_date_jalali__endswith=suffix)

        candidates = User.objects.exclude(is_admin=True).filter(birthday_filter)
        return [user for user in candidates if is_birthday_today(user.birth_date_jalali)]

    def send_pending_birthday_sms(self) -> list[User]:
        today_jalali = jdatetime.date.today().strftime("%Y/%m/%d")
        sent_to: list[User] = []
        for user in self.get_birthday_users():
            if BirthdaySmsLog.objects.filter(user=user, sent_on=today_jalali).exists():
                continue
            phone = (user.phone or "").strip()
            if len(phone) != 11 or not phone.isdigit():
                continue
            message = f"{user.fullname} عزیز،\nتولدت مبارک! تیم ایگوفیت 🎉"
            try:
                is_sent = self.sms_service.send_personalized_bulk_sms(
                    [PersonalizedSmsMessage(receptor=phone, message=message)]
                )
            except Exception:
                continue
            if not is_sent:
                continue
            BirthdaySmsLog.objects.create(user=user, sent_on=today_jalali)
            sent_to.append(user)
        return sent_to

    def get_target_user(self, user_id: int) -> User:
        return User.objects.get(pk=user_id)

    def create_user(self, *, form) -> User:
        user = form.save(commit=False)
        user.set_password(form.cleaned_data["password"])
        user.save()
        return user

    def delete_user(self, target: User) -> tuple[bool, str | None]:
        if target.orders.filter(is_paid=True).exists():
            return False, _("این کاربر سفارش پرداخت‌شده دارد و قابل حذف نیست.")
        target.delete()
        return True, None

    def get_or_create_circumference(self, user: User) -> BodyCircumferenceMeasurement:
        instance = BodyCircumferenceMeasurement.objects.filter(user=user).order_by("-recorded_at").first() or BodyCircumferenceMeasurement(user=user)
        instance.measured_at_jalali = jdatetime.date.today().strftime("%Y/%m/%d")
        return instance

    def get_or_create_caliper(self, user: User) -> CaliperMeasurement:
        instance = CaliperMeasurement.objects.filter(user=user).order_by("-recorded_at").first() or CaliperMeasurement(user=user)
        instance.measured_at_jalali = jdatetime.date.today().strftime("%Y/%m/%d")
        return instance

    def save_circumference(self, *, user: User, form) -> BodyCircumferenceMeasurement:
        instance = form.save(commit=False)
        instance.user = user
        instance.pk = None
        instance.save()
        update_fields = []
        if instance.height_cm is not None:
            user.height_cm = instance.height_cm
            update_fields.append("height_cm")
        if instance.weight_kg is not None:
            user.weight_kg = instance.weight_kg
            update_fields.append("weight_kg")
        if update_fields:
            user.save(update_fields=update_fields)
        return instance

    def save_caliper(self, *, user: User, form) -> CaliperMeasurement:
        instance = form.save(commit=False)
        instance.user = user
        instance.pk = None
        instance.save()
        return instance

    def update_circumference(self, *, form) -> BodyCircumferenceMeasurement:
        return form.save()

    def update_caliper(self, *, form) -> CaliperMeasurement:
        return form.save()

    def save_media(self, *, user: User, uploaded_by: User, form) -> ClientMedia:
        instance = form.save(commit=False)
        instance.user = user
        instance.uploaded_by = uploaded_by
        instance.save()
        NotificationService.schedule_media_uploaded(instance)
        return instance

    def save_document(self, *, user: User, uploaded_by: User, form) -> ClientDocument:
        instance = form.save(commit=False)
        instance.user = user
        instance.uploaded_by = uploaded_by
        instance.save()
        NotificationService.schedule_document_uploaded(instance)
        return instance

    def get_analysis_context(
        self,
        user: User,
        *,
        metric: str | None = None,
        start: str | None = None,
        end: str | None = None,
        circ_date: str | None = None,
        body_fat_formula: str | None = None,
        caliper_date: str | None = None,
        use_full_chart_range: bool = False,
    ) -> dict:
        context = self.profile_service.get_analysis_context(
            user,
            metric=metric,
            start=start,
            end=end,
            circ_date=circ_date,
            body_fat_formula=body_fat_formula,
            caliper_date=caliper_date,
            use_full_chart_range=use_full_chart_range,
        )
        context.update(
            {
                "latest_circumference": user.circumference_records.first(),
                "latest_caliper": user.caliper_records.first(),
                "latest_media": list(user.client_media.all()[:4]),
            }
        )
        return context

    def get_analysis_dashboard_data(self, user: User, *, body_fat_formula: str | None = None) -> dict:
        return self.profile_service.get_analysis_dashboard_data(user, body_fat_formula=body_fat_formula)

    def get_analysis_metric_series(self, user: User, *, body_fat_formula: str | None = None) -> dict:
        return self.profile_service.get_analysis_metric_series(user, body_fat_formula=body_fat_formula)

    def get_user_summary_context(self, user: User) -> dict:
        return {
            "latest_circumference": user.circumference_records.first(),
            "latest_caliper": user.caliper_records.first(),
            "latest_media": list(user.client_media.all()[:4]),
            "latest_documents": list(user.client_documents.all()[:4]),
            "latest_workout_programs": list(WorkoutProgram.objects.filter(user=user)[:4]),
            "coach_requests": list(user.coach_requests.all()[:10]),
        }

    def mark_coach_request_handled(self, coach_request) -> None:
        self.coach_request_service.mark_handled(coach_request)

    # Fields copied 1:1 from a CoachRequest into a BodyCircumferenceMeasurement.
    COACH_REQUEST_MEASUREMENT_FIELDS = (
        "height_cm", "weight_kg", "wrist_cm", "forearm_cm", "arm_rest_cm", "arm_flexed_cm",
        "chest_cm", "shoulders_cm", "waist_cm", "abdomen_cm", "hips_cm", "thigh_cm", "calf_cm",
        "thigh_left_cm", "calf_left_cm",
    )

    def push_coach_request_to_measurements(self, coach_request) -> BodyCircumferenceMeasurement | None:
        """Copy the athlete-submitted body data from a coach request into a measurement record (once)."""
        if coach_request.pushed_to_measurements or not coach_request.has_body_data:
            return None
        values = {field: getattr(coach_request, field) for field in self.COACH_REQUEST_MEASUREMENT_FIELDS}
        instance = BodyCircumferenceMeasurement.objects.create(
            user=coach_request.user,
            measured_at_jalali=jdatetime.date.today().strftime("%Y/%m/%d"),
            **values,
        )
        coach_request.pushed_to_measurements = True
        coach_request.save(update_fields=["pushed_to_measurements"])
        return instance

    def toggle_admin_role(self, *, actor: User, target: User, make_admin: bool) -> None:
        if actor.pk == target.pk:
            raise ValueError(_("نمی‌توانید نقش خودتان را تغییر دهید."))
        if target.is_admin and not make_admin and User.objects.filter(is_admin=True).count() <= 1:
            raise ValueError(_("حداقل یک ادمین باید در سیستم باقی بماند."))
        target.is_admin = make_admin
        target.save(update_fields=["is_admin"])

    def assign_coach_to_all(self, coach: User) -> int:
        return User.objects.exclude(is_admin=True).update(coach=coach)

    def assign_coach_to_user(self, user: User, coach: User | None) -> None:
        user.coach = coach
        user.save(update_fields=["coach"])

    def get_coach_management_context(self) -> dict:
        coaches = list(User.objects.filter(is_admin=True).order_by("fullname"))
        clients = list(User.objects.exclude(is_admin=True).select_related("coach").order_by("fullname"))
        return {
            "coaches": coaches,
            "clients": clients,
            "bulk_form": AdminBulkCoachAssignForm(),
        }
