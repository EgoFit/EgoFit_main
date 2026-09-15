from __future__ import annotations

from typing import Any

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import TemplateView

from account.froms import (
    BloodGroupForm,
    BirthDateForm,
    CoachRequestForm,
    HeightForm,
    UserEditForm,
    WeightForm,
    validate_coach_request_file,
)
from account.models import (
    ClientDocumentPayment,
    WorkoutProgramPayment,
)
from account.portal_mixins import UserPortalRequiredMixin, user_portal_required
from account.services.coach_request_service import CoachRequestService
from account.services.gym_program_service import GymProgramService
from account.services.profile_service import ProfileService
from account.view_mixins import AccountPageMixin
from home.models import SeriesModel


profile_service = ProfileService()
coach_request_service = CoachRequestService()
gym_program_service = GymProgramService()


PROFILE_METRIC_CONFIG: dict[str, dict[str, Any]] = {
    "weight": {
        "field": "weight_kg",
        "form_field": "weight",
        "form_class": WeightForm,
        "template_name": "account/profile-metric-edit.html",
        "title": _("وزن"),
        "description": _("وزنتون رو به کیلوگرم وارد کنید."),
    },
    "height": {
        "field": "height_cm",
        "form_field": "height",
        "form_class": HeightForm,
        "template_name": "account/profile-metric-edit.html",
        "title": _("قد"),
        "description": _("قدتون رو به سانتی متر وارد کنید."),
    },
    "birth_date": {
        "field": "birth_date_jalali",
        "form_field": "birth_date",
        "form_class": BirthDateForm,
        "template_name": "account/profile-metric-edit.html",
        "title": _("تاریخ تولد"),
        "description": _("تاریخ تولدتون رو وارد کنید."),
    },
    "blood_group": {
        "field": "blood_group",
        "form_field": "blood_group",
        "form_class": BloodGroupForm,
        "template_name": "account/profile-blood-group.html",
        "title": _("گروه خونی"),
        "description": _("گروه خونی خود را انتخاب کنید."),
    },
}


class ProfileView(AccountPageMixin, UserPortalRequiredMixin, TemplateView):
    """Dashboard page for the authenticated athlete."""

    template_name = "account/profile.html"
    active_section = "dashboard"
    account_title = _("پروفایل")
    account_description = _("اطلاعات حساب و وضعیت بدن خود را در یک نگاه مدیریت کنید.")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(profile_service.get_dashboard_context(self.request.user))
        return context


class ProfileAnalysisView(AccountPageMixin, UserPortalRequiredMixin, TemplateView):
    """Body-composition analysis page; formulas remain owned by ProfileService."""

    template_name = "account/profile-analysis.html"
    active_section = "analysis"
    account_title = _("آنالیز")
    account_description = _("شاخص‌های بدنی و گزارش‌های روزانه را از اینجا بررسی کنید.")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(profile_service.get_dashboard_context(self.request.user))
        context.update(
            profile_service.get_analysis_context(
                self.request.user,
                metric=self.request.GET.get("metric"),
                start=self.request.GET.get("start"),
                end=self.request.GET.get("end"),
                date=self.request.GET.get("date"),
            )
        )
        context.update(profile_service.get_analysis_dashboard_data(self.request.user))
        context["analysis_metric_series"] = profile_service.get_analysis_metric_series(self.request.user)
        return context


class ProfileCoachView(AccountPageMixin, UserPortalRequiredMixin, View):
    """Create and update the athlete's coach request."""

    template_name = "account/profile-coach.html"
    active_section = "coach"
    account_title = _("مربی شما")
    account_description = _("در این بخش اطلاعات مربی اختصاصی و مسیر پیگیری برنامه نمایش داده می‌شود.")

    def _get_pending(self, user):
        return coach_request_service.get_pending_for_user(user).first()

    def _build_context(self, *, form=None, pending=None):
        user = self.request.user
        pending = pending if pending is not None else self._get_pending(user)
        return {
            "active_section": self.active_section,
            "account_title": self.account_title,
            "account_description": self.account_description,
            "coach": user.coach,
            "pending_request": pending,
            "attachments": list(pending.attachments.all()) if pending else [],
            "form": form or CoachRequestForm(instance=pending),
        }

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self._build_context())

    def post(self, request, *args, **kwargs):
        pending = self._get_pending(request.user)
        form = CoachRequestForm(request.POST, instance=pending)
        files = request.FILES.getlist("attachments")
        file_errors: list[str] = []
        for uploaded in files:
            try:
                validate_coach_request_file(uploaded)
            except ValidationError as exc:
                file_errors.extend(exc.messages)
        if form.is_valid() and not file_errors:
            coach_request_service.save_request(user=request.user, form=form, files=files)
            messages.success(
                request,
                _("درخواست شما به‌روزرسانی شد.") if pending else _("درخواست شما برای مربی ثبت شد."),
            )
            return redirect("register:profile_coach")
        for error in file_errors:
            messages.error(request, error)
        return render(request, self.template_name, self._build_context(form=form, pending=pending))


class ProfileMetricEditView(AccountPageMixin, UserPortalRequiredMixin, View):
    """Edit one of the allowlisted profile metrics."""

    template_name = "account/profile-metric-edit.html"
    active_section = "dashboard"
    hide_account_chrome = True

    def dispatch(self, request, *args, **kwargs):
        self.metric = kwargs.get("metric")
        self.metric_config = PROFILE_METRIC_CONFIG.get(self.metric)
        if self.metric_config is None:
            return redirect("register:profile")
        self.template_name = self.metric_config["template_name"]
        self.account_title = self.metric_config["title"]
        self.account_description = self.metric_config["description"]
        return super().dispatch(request, *args, **kwargs)

    def _build_form(self, *, data=None):
        form_class = self.metric_config["form_class"]
        field_name = self.metric_config["field"]
        form_field_name = self.metric_config["form_field"]
        initial_value = getattr(self.request.user, field_name, None)
        initial = {form_field_name: initial_value} if initial_value is not None else None
        return form_class(data=data, initial=initial)

    def _get_form_context(self, form):
        form_field_name = self.metric_config["form_field"]
        field = form[form_field_name]
        return {
            "form": form,
            "field": field,
            "field_label": self.metric_config["title"],
            "metric": self.metric,
            "metric_config": self.metric_config,
            "active_section": self.active_section,
            "account_title": self.account_title,
            "account_description": self.account_description,
            "hide_account_chrome": self.hide_account_chrome,
        }

    def get(self, request, *args, **kwargs):
        form = self._build_form()
        return render(request, self.template_name, self._get_form_context(form))

    def post(self, request, *args, **kwargs):
        form = self._build_form(data=request.POST)
        if form.is_valid():
            field_name = self.metric_config["field"]
            value = next(iter(form.cleaned_data.values()))
            profile_service.update_profile_metric(user=request.user, field_name=field_name, value=value)
            messages.success(request, _("اطلاعات پروفایل با موفقیت به‌روزرسانی شد."))
            return redirect("register:profile")
        return render(request, self.template_name, self._get_form_context(form))


class ProfileCoursesView(AccountPageMixin, UserPortalRequiredMixin, TemplateView):
    template_name = "account/profile-courses.html"
    active_section = "courses"
    account_title = _("دوره‌های من")
    account_description = _("آخرین دوره‌هایی که به آن‌ها دسترسی دارید را ببینید.")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["items"] = profile_service.get_learning_courses(self.request.user)
        return context


class ProfileDocumentsView(AccountPageMixin, UserPortalRequiredMixin, TemplateView):
    template_name = "account/profile-plans.html"
    active_section = "plans"
    account_title = _("برنامه‌های من")
    account_description = _("فایل‌ها و برنامه‌هایی که مربی برای شما ارسال کرده است.")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["documents"] = self.request.user.client_documents.all()
        context["paid_document_ids"] = set(
            ClientDocumentPayment.objects.filter(
                user=self.request.user,
                status=ClientDocumentPayment.Status.PAID,
            ).values_list("document_id", flat=True)
        )
        context["workout_programs"] = gym_program_service.get_program_queryset().filter(
            user=self.request.user,
            is_published=True,
        )
        context["paid_workout_program_ids"] = set(
            WorkoutProgramPayment.objects.filter(
                user=self.request.user,
                status=WorkoutProgramPayment.Status.PAID,
            ).values_list("program_id", flat=True)
        )
        return context


class AddCourseToProfileView(UserPortalRequiredMixin, View):
    def post(self, request, series_id):
        series = get_object_or_404(SeriesModel, id=series_id, free=True)
        profile_service.add_free_course_to_profile(user=request.user, series_id=series_id, series=series)
        return redirect("home:series_episod", pk=series_id)


class ProfileFinancialView(AccountPageMixin, UserPortalRequiredMixin, TemplateView):
    template_name = "account/profile-financial.html"
    active_section = "financial"
    account_title = _("مالی و سفارش‌ها")
    account_description = _("وضعیت پرداخت‌ها و سفارش‌های ثبت شده را بررسی کنید.")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["orders"] = profile_service.get_paid_orders(self.request.user)
        return context


class ProfileCommentsView(AccountPageMixin, UserPortalRequiredMixin, TemplateView):
    template_name = "account/profile-comments.html"
    active_section = "comments"
    account_title = _("دیدگاه‌های من")
    account_description = _("آخرین تعامل‌های شما با دوره‌ها در این بخش نمایش داده می‌شود.")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["comments"] = profile_service.get_comments(self.request.user)
        return context


class ProfileNotificationsView(AccountPageMixin, UserPortalRequiredMixin, TemplateView):
    template_name = "account/profile-notifications.html"
    active_section = "notifications"
    account_title = _("اعلان‌ها")
    account_description = _("اعلان‌های سیستم و درخواست‌های جدید را از اینجا دنبال کنید.")

    def post(self, request, *args, **kwargs):
        course_id = request.POST.get("course_id")
        course = get_object_or_404(SeriesModel, id=course_id)
        profile_service.create_course_request_notification(user=request.user, course=course)
        messages.success(request, _("درخواست شما ثبت شد."))
        return redirect("register:profile_notifications")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["notifications"] = profile_service.get_notifications_feed(self.request.user)
        return context


@user_portal_required
def edit_user_profile(request):
    if request.method == "POST":
        form = UserEditForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            profile_service.update_profile(form=form)
            messages.success(request, _("اطلاعات شما با موفقیت بروزرسانی شد."))
            return redirect("register:profile_useredit")
    else:
        form = UserEditForm(instance=request.user)

    return render(
        request,
        "account/profile-edit.html",
        {
            "form": form,
            "active_section": "edit",
            "account_title": _("ویرایش پروفایل"),
            "account_description": _("اطلاعات اصلی حساب کاربری خود را به‌روزرسانی کنید."),
        },
    )
