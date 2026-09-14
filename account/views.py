from __future__ import annotations

import os
import re
from collections import defaultdict
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import PasswordChangeView
from django.db import transaction
from django.db.models import Q
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import TemplateView

from account.constants import OTP_EXPIRATION_MINUTES, OTP_REQUEST_COOLDOWN_SECONDS
from account.limits import enforce_web_otp_rate_limit
from account.exceptions import (
    AuthenticationException,
    ExpiredOtpException,
    InvalidOtpException,
    OTPRateLimitExceededException,
    PasswordResetException,
    PhoneAlreadyExistsException,
    SessionValidationException,
    SMSProviderException,
)
from account.froms import (
    CheckOtp,
    BirthDateForm,
    CoachRequestForm,
    FormLogin,
    FormRegister,
    BloodGroupForm,
    HeightForm,
    NumberEditForm,
    OtpForm,
    PasswordChanged,
    PasswordResetConfirmForm,
    PasswordResetRequestForm,
    WeightForm,
    UserEditForm,
    validate_coach_request_file,
)
from django.core.exceptions import ValidationError
from account.services import AuthService, OTPService, ProfileService, SessionService, create_and_send_otp, get_valid_otp
from account.services.coach_request_service import CoachRequestService
from account.services.gym_program_pdf import build_program_pdf
from account.services.gym_program_service import GymProgramService
from account.services.access_payment_service import AccessPaymentService
from account.portal_mixins import UserPortalRequiredMixin, get_post_login_redirect_url, user_portal_required
from account.utils import format_phone_display, normalize_digits
from account.models import (
    ClientDocument,
    ClientDocumentPayment,
    CorrectiveExercise,
    Exercise,
    WorkoutPerformanceRecord,
    WorkoutProgram,
    WorkoutProgramPayment,
    WorkoutProgramDay,
    WorkoutProgramExercise,
    WorkoutProgramFeedback,
)
from cart.exceptions import PaymentProviderException, PaymentVerificationException
from cart.providers.zarinpal_provider import ZarinPalPaymentProvider
from cart.zarinpal import build_payment_callback_url
from home.models import SeriesModel


auth_service = AuthService()
otp_service = OTPService()
profile_service = ProfileService()
session_service = SessionService()
coach_request_service = CoachRequestService()
gym_program_service = GymProgramService()
access_payment_service = AccessPaymentService()


def _has_workout_program_access(user, program) -> bool:
    return bool(
        program
        and (
            not program.requires_payment
            or WorkoutProgramPayment.objects.filter(
                program=program,
                user=user,
                status=WorkoutProgramPayment.Status.PAID,
            ).exists()
        )
    )


PROFILE_METRIC_CONFIG = {
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


def _build_verification_context(*, token: str, form):
    context = {
        "form": form,
        "token": token,
        "verification_phone": None,
        "otp_expires_in_seconds": OTP_EXPIRATION_MINUTES * 60,
        "otp_resend_cooldown_seconds": OTP_REQUEST_COOLDOWN_SECONDS,
        "otp_cooldown_remaining_seconds": 0,
        "otp_can_resend": True,
    }
    token = (token or "").strip()
    if not token:
        return context

    try:
        status = otp_service.get_verification_status(token)
        context.update(
            {
                "verification_phone": format_phone_display(status.phone),
                "otp_expires_in_seconds": status.expires_in_seconds,
                "otp_cooldown_remaining_seconds": status.resend_cooldown_seconds,
                "otp_can_resend": status.can_resend,
            }
        )
    except Exception:
        pass
    return context


class AccountPageMixin:
    active_section = "dashboard"
    account_title = ""
    account_description = ""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault("active_section", self.active_section)
        context.setdefault("account_title", self.account_title)
        context.setdefault("account_description", self.account_description)
        return context


class Register(View):
    template_name = "account/login-register.html"

    def get(self, request):
        return render(request, self.template_name, {"form": OtpForm()})

    def post(self, request):
        form = OtpForm(request.POST)
        if form.is_valid():
            try:
                enforce_web_otp_rate_limit(request, form.cleaned_data["phone"])
                token = create_and_send_otp(form.cleaned_data["phone"])
            except SMSProviderException as exc:
                form.add_error("phone", str(exc))
                return render(request, self.template_name, {"form": form})
            except OTPRateLimitExceededException as exc:
                form.add_error("phone", str(exc))
                return render(request, self.template_name, {"form": form})

            messages.success(request, _("کد تایید برای شما ارسال شد."))
            return redirect(f"{reverse('register:verification')}?token={token}")

        return render(request, self.template_name, {"form": form})


class CheckOtpView(View):
    template_name = "account/verification.html"

    def get(self, request):
        token = (request.GET.get("token") or "").strip()
        return render(
            request,
            self.template_name,
            _build_verification_context(token=token, form=CheckOtp()),
        )

    def post(self, request):
        token = (request.GET.get("token") or "").strip()
        form = CheckOtp(request.POST)
        if form.is_valid():
            try:
                otp = otp_service.validate_otp(token=token, code=int(form.cleaned_data["code"]))
                user, _created = auth_service.get_or_create_otp_user(phone=otp.phone)
                login(request, user)
                otp_service.consume_otp(otp)
                session_service.queue_login_session_log(user=user, request=request)
                messages.success(request, _("با موفقیت وارد شدید."))
                return redirect(get_post_login_redirect_url(user))
            except (InvalidOtpException, ExpiredOtpException):
                form.add_error("code", _("کد وارد شده نادرست یا منقضی شده است."))

        return render(
            request,
            self.template_name,
            _build_verification_context(token=token, form=form),
        )


class ResendOtpView(View):
    def get(self, request):
        token = (request.GET.get("token") or "").strip()
        if not token:
            messages.error(request, _("درخواست معتبر نیست."))
            return redirect("register:register")

        try:
            status = otp_service.get_verification_status(token)
            enforce_web_otp_rate_limit(request, status.phone)
            new_token = otp_service.resend_otp(token=token)
        except OTPRateLimitExceededException as exc:
            messages.error(request, str(exc))
            return redirect(f"{reverse('register:verification')}?token={token}")
        except SMSProviderException as exc:
            messages.error(request, str(exc))
            return redirect(f"{reverse('register:verification')}?token={token}")
        except Exception:
            messages.error(request, _("امکان ارسال دوباره کد وجود ندارد. دوباره شماره موبایل را وارد کنید."))
            return redirect("register:register")

        messages.success(request, _("کد تایید دوباره ارسال شد."))
        return redirect(f"{reverse('register:verification')}?token={new_token}")


def user_logout(request):
    logout(request)
    return redirect("/")


class ProfileView(AccountPageMixin, UserPortalRequiredMixin, TemplateView):
    template_name = "account/profile.html"
    active_section = "dashboard"
    account_title = _("پروفایل")
    account_description = _("اطلاعات حساب و وضعیت بدن خود را در یک نگاه مدیریت کنید.")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(profile_service.get_dashboard_context(self.request.user))
        return context


class ProfileAnalysisView(AccountPageMixin, UserPortalRequiredMixin, TemplateView):
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


class ClientDocumentPaymentView(UserPortalRequiredMixin, View):
    def post(self, request, pk):
        document = get_object_or_404(ClientDocument, pk=pk, user=request.user)
        if not document.requires_payment or document.price <= 0:
            return redirect("register:profile_plans")
        try:
            result = access_payment_service.initiate_document(
                document_id=document.pk,
                user=request.user,
                callback_url=build_payment_callback_url(request, url_name="register:profile_document_verify"),
            )
        except PaymentProviderException as exc:
            messages.error(request, str(exc))
            return redirect("register:profile_plans")
        if result.already_paid:
            return redirect("register:profile_document_download", pk=document.pk)
        request.session["document_payment_id"] = result.payment_id
        request.session.save()
        return redirect(result.redirect_url)

        if False:
            # Legacy reference retained only to keep historical source context inert.
                description=f"دریافت فایل {document.title}",
class ClientDocumentPaymentVerifyView(View):
    def get(self, request):
        authority = (request.GET.get("Authority") or "").strip()
        status = (request.GET.get("Status") or "").strip().upper()
        result = access_payment_service.verify_document(authority=authority, status=status)
        if result.payment is None:
            messages.error(request, "پرداخت فایل پیدا نشد.")
            return redirect("register:profile_plans")
        if result.state not in {"paid", "already_paid"}:
            messages.error(request, result.message or "پرداخت فایل تأیید نشد.")
            return redirect("register:profile_plans")
        request.session.pop("document_payment_id", None)
        messages.success(request, "پرداخت با موفقیت انجام شد.")
        return redirect("register:profile_document_download", pk=result.payment.document_id)

        payment = ClientDocumentPayment.objects.filter(
            authority=authority,
            status=ClientDocumentPayment.Status.INITIATED,
        ).select_related("document", "user").first()
        if payment is None:
            messages.error(request, _("پرداخت فایل پیدا نشد."))
            return redirect("register:profile_plans")
        if status != "OK":
            payment.status = ClientDocumentPayment.Status.FAILED
            payment.save(update_fields=["status"])
            messages.error(request, _("پرداخت فایل لغو یا ناموفق بود."))
            return redirect("register:profile_plans")
        try:
            result = ZarinPalPaymentProvider().verify_payment(
                amount=payment.amount,
                authority=authority,
            )
        except PaymentVerificationException as exc:
            payment.status = ClientDocumentPayment.Status.FAILED
            payment.save(update_fields=["status"])
            messages.error(request, str(exc))
            return redirect("register:profile_plans")
        if not result.success:
            payment.status = ClientDocumentPayment.Status.FAILED
            payment.save(update_fields=["status"])
            messages.error(request, result.message or _("پرداخت فایل تایید نشد."))
            return redirect("register:profile_plans")
        payment.status = ClientDocumentPayment.Status.PAID
        payment.ref_id = result.ref_id or ""
        payment.paid_at = timezone.now()
        payment.save(update_fields=["status", "ref_id", "paid_at"])
        request.session.pop("document_payment_id", None)
        messages.success(request, _("پرداخت با موفقیت انجام شد."))
        return redirect("register:profile_document_download", pk=payment.document_id)


class ClientDocumentDownloadView(UserPortalRequiredMixin, View):
    def get(self, request, pk):
        document = get_object_or_404(ClientDocument, pk=pk, user=request.user)
        if document.requires_payment and not ClientDocumentPayment.objects.filter(
            document=document,
            user=request.user,
            status=ClientDocumentPayment.Status.PAID,
        ).exists():
            messages.info(request, _("برای دریافت این فایل ابتدا هزینه آن را پرداخت کنید."))
            return redirect("register:profile_plans")
        document.file.open("rb")
        return FileResponse(document.file, as_attachment=True, filename=os.path.basename(document.file.name))


class WorkoutProgramPaymentView(UserPortalRequiredMixin, View):
    def post(self, request, pk):
        program = get_object_or_404(
            WorkoutProgram,
            pk=pk,
            user=request.user,
            is_published=True,
        )
        if not program.requires_payment or program.price <= 0:
            return redirect("register:profile_workout_programs")
        if _has_workout_program_access(request.user, program):
            return redirect("register:profile_workout_programs")

        try:
            result = access_payment_service.initiate_program(
                program_id=program.pk,
                user=request.user,
                callback_url=build_payment_callback_url(request, url_name="register:profile_workout_program_verify"),
            )
        except PaymentProviderException as exc:
            messages.error(request, str(exc))
            return redirect("register:profile_workout_programs")
        if result.already_paid:
            return redirect("register:profile_workout_programs")
        request.session["workout_program_payment_id"] = result.payment_id
        request.session.save()
        return redirect(result.redirect_url)

        payment = WorkoutProgramPayment.objects.filter(
            program=program,
            user=request.user,
            status=WorkoutProgramPayment.Status.INITIATED,
        ).first()
        if payment is None:
            payment = WorkoutProgramPayment.objects.create(
                program=program,
                user=request.user,
                amount=program.price,
            )
        try:
            result = ZarinPalPaymentProvider().request_payment(
                amount=payment.amount,
                callback_url=build_payment_callback_url(
                    request,
                    url_name="register:profile_workout_program_verify",
                ),
                description=f"دسترسی به برنامه {program.title}",
                mobile=request.user.phone,
                email=request.user.email or None,
            )
        except PaymentProviderException as exc:
            messages.error(request, str(exc))
            return redirect("register:profile_workout_programs")
        payment.authority = result.authority
        payment.status = WorkoutProgramPayment.Status.INITIATED
        payment.save(update_fields=["authority", "status"])
        request.session["workout_program_payment_id"] = payment.pk
        request.session.save()
        return redirect(result.redirect_url)


class WorkoutProgramPaymentVerifyView(View):
    def get(self, request):
        authority = (request.GET.get("Authority") or "").strip()
        status = (request.GET.get("Status") or "").strip().upper()
        result = access_payment_service.verify_program(authority=authority, status=status)
        if result.payment is None:
            messages.error(request, "پرداخت برنامه پیدا نشد.")
            return redirect("register:profile_workout_programs")
        if result.state not in {"paid", "already_paid"}:
            messages.error(request, result.message or "پرداخت برنامه تأیید نشد.")
            return redirect("register:profile_workout_programs")
        request.session.pop("workout_program_payment_id", None)
        messages.success(request, "پرداخت با موفقیت انجام شد و برنامه فعال شد.")
        return redirect("register:profile_workout_programs")

        payment = WorkoutProgramPayment.objects.filter(
            authority=authority,
            status=WorkoutProgramPayment.Status.INITIATED,
        ).select_related("program", "user").first()
        if payment is None:
            messages.error(request, _("پرداخت برنامه پیدا نشد."))
            return redirect("register:profile_workout_programs")
        if status != "OK":
            payment.status = WorkoutProgramPayment.Status.FAILED
            payment.save(update_fields=["status"])
            messages.error(request, _("پرداخت برنامه لغو یا ناموفق بود."))
            return redirect("register:profile_workout_programs")
        try:
            result = ZarinPalPaymentProvider().verify_payment(
                amount=payment.amount,
                authority=authority,
            )
        except PaymentVerificationException as exc:
            payment.status = WorkoutProgramPayment.Status.FAILED
            payment.save(update_fields=["status"])
            messages.error(request, str(exc))
            return redirect("register:profile_workout_programs")
        if not result.success:
            payment.status = WorkoutProgramPayment.Status.FAILED
            payment.save(update_fields=["status"])
            messages.error(request, result.message or _("پرداخت برنامه تایید نشد."))
            return redirect("register:profile_workout_programs")
        payment.status = WorkoutProgramPayment.Status.PAID
        payment.ref_id = result.ref_id or ""
        payment.paid_at = timezone.now()
        payment.save(update_fields=["status", "ref_id", "paid_at"])
        request.session.pop("workout_program_payment_id", None)
        messages.success(request, _("پرداخت با موفقیت انجام شد و برنامه فعال شد."))
        return redirect("register:profile_workout_programs")


class ProfileWorkoutProgramsView(AccountPageMixin, UserPortalRequiredMixin, TemplateView):
    template_name = "account/profile-workout-programs.html"
    active_section = "workout"
    account_title = _("برنامه بدنسازی")
    account_description = _("برنامه تمرینی تجویز‌شده، حرکت‌ها و نکات مربی را آنلاین دنبال کنید.")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        programs = list(gym_program_service.get_program_queryset().filter(
            user=self.request.user,
            is_published=True,
        ))
        feedbacks = list(
            WorkoutProgramFeedback.objects.filter(
                program_id__in=[program.pk for program in programs]
            ).select_related("day")
        )
        feedback_by_day = {
            feedback.day_id: feedback
            for feedback in feedbacks
            if feedback.day_id is not None
        }
        legacy_feedback_by_program = {}
        latest_feedback_by_program = {}
        for feedback in sorted(
            feedbacks,
            key=lambda item: item.submitted_at,
            reverse=True,
        ):
            latest_feedback_by_program.setdefault(feedback.program_id, feedback)
            if feedback.day_id is None:
                legacy_feedback_by_program.setdefault(feedback.program_id, feedback)

        for program in programs:
            program.can_access = _has_workout_program_access(self.request.user, program)
            corrective_items = list(program.corrective_items.all())
            program.warmup_correctives = [
                item for item in corrective_items if item.phase == "warmup"
            ]
            program.cooldown_correctives = [
                item for item in corrective_items if item.phase == "cooldown"
            ]
            program.user_feedback = latest_feedback_by_program.get(program.pk)
            for day_index, day in enumerate(program.days.all()):
                day.user_feedback = feedback_by_day.get(day.pk)
                if day.user_feedback is None and day_index == 0:
                    day.user_feedback = legacy_feedback_by_program.get(program.pk)
            self._attach_performance_context(program)
        context["programs"] = programs
        return context

    @staticmethod
    def _attach_performance_context(program):
        days = list(program.days.all())
        groups_by_day = {
            day.pk: ProfileWorkoutProgramsView._build_performance_groups(
                list(day.items.all())
            )
            for day in days
        }
        exercise_ids = {
            group["exercise"].pk
            for groups in groups_by_day.values()
            for group in groups
        }
        records = list(
            WorkoutPerformanceRecord.objects.filter(
                user=program.user,
                exercise_id__in=exercise_ids,
            )
        )
        records_by_movement = defaultdict(list)
        for record in records:
            records_by_movement[
                (
                    record.exercise_id,
                    ProfileWorkoutProgramsView._normalize_repetition_key(
                        record.repetitions
                    ),
                )
            ].append(record)

        mode_units = {
            WorkoutPerformanceRecord.Mode.WEIGHT: _("کیلوگرم"),
            WorkoutPerformanceRecord.Mode.BODY_WEIGHT: _("کیلوگرم"),
            WorkoutPerformanceRecord.Mode.TIME: _("ثانیه"),
        }
        mode_choices = WorkoutPerformanceRecord.Mode.choices
        mode_values = {mode_value for mode_value, _ in mode_choices}
        for day in days:
            for item in day.items.all():
                item.performance_movements = []

        for day in days:
            day.performance_movements = []
            for group in groups_by_day[day.pk]:
                exercise = group["exercise"]
                repetitions = group["repetitions"]
                movement_records = records_by_movement.get(
                    (
                        exercise.pk,
                        ProfileWorkoutProgramsView._normalize_repetition_key(
                            repetitions
                        ),
                    ),
                    [],
                )
                latest_record = max(
                    movement_records,
                    key=lambda record: record.updated_at,
                    default=None,
                )
                modes = []
                for mode_value, mode_label in mode_choices:
                    mode_records = [
                        record
                        for record in movement_records
                        if record.mode == mode_value
                    ]
                    values_by_set = {
                        record.set_number: record.value
                        for record in mode_records
                    }
                    best_value = max(
                        (record.value for record in mode_records),
                        default=None,
                    )
                    modes.append(
                        {
                            "value": mode_value,
                            "label": mode_label,
                            "unit": mode_units[mode_value],
                            "step": "1" if mode_value == WorkoutPerformanceRecord.Mode.TIME else "0.01",
                            "best": best_value,
                            "sets": [
                                {
                                    "number": set_number,
                                    "value": values_by_set.get(set_number),
                                }
                                for set_number in range(1, group["set_count"] + 1)
                            ],
                        }
                )
                saved_mode = next(
                    (
                        source["item"].performance_modes.get(source["slot"])
                        for source in group["sources"]
                        if isinstance(source["item"].performance_modes, dict)
                        and source["item"].performance_modes.get(source["slot"]) in mode_values
                    ),
                    None,
                )
                movement_context = {
                    "exercise": exercise,
                    "slot": group["sources"][0]["slot"],
                    "input_prefix": group["input_prefix"],
                    "selected_mode": (
                        saved_mode
                        or (
                            latest_record.mode
                            if latest_record
                            else WorkoutPerformanceRecord.Mode.WEIGHT
                        )
                    ),
                    "modes": modes,
                    "repetitions": repetitions,
                }
                day.performance_movements.append(movement_context)
                for source in group["sources"]:
                    source_saved_modes = source["item"].performance_modes
                    source_selected_mode = (
                        source_saved_modes.get(source["slot"])
                        if isinstance(source_saved_modes, dict)
                        and source_saved_modes.get(source["slot"]) in mode_values
                        else movement_context["selected_mode"]
                    )
                    source_set_count = gym_program_service.parse_set_count(
                        source["sets"]
                    )
                    source_modes = [
                        {
                            **mode,
                            "sets": mode["sets"][:source_set_count],
                        }
                        for mode in movement_context["modes"]
                    ]
                    source["item"].performance_movements.append(
                        {
                            **movement_context,
                            "slot": source["slot"],
                            "input_prefix": (
                                f"performance_{source['item'].pk}_{source['slot']}"
                            ),
                            "selected_mode": source_selected_mode,
                            "modes": source_modes,
                        }
                    )

    @staticmethod
    def _normalize_repetition_key(repetitions):
        normalized = normalize_digits(repetitions or "").strip()
        parts = re.findall(r"\d+", normalized)
        if not parts:
            return normalized
        return "-".join(parts)

    @staticmethod
    def _build_performance_groups(items):
        groups = {}
        for item in items:
            movement_slots = (
                ("main", item.exercise, item.sets, item.reps, item.rest),
                (
                    "superset",
                    item.superset_exercise,
                    item.superset_sets if item.superset_sets is not None else item.sets,
                    item.superset_reps if item.superset_reps is not None else item.reps,
                    item.superset_rest if item.superset_rest is not None else item.rest,
                ),
                (
                    "third",
                    item.third_exercise,
                    item.third_sets if item.third_sets is not None else item.sets,
                    item.third_reps if item.third_reps is not None else item.reps,
                    item.third_rest if item.third_rest is not None else item.rest,
                ),
            )
            for slot, exercise, sets, reps, rest in movement_slots:
                if exercise is None:
                    continue
                repetitions = str(reps or "").strip()
                key = (
                    exercise.pk,
                    ProfileWorkoutProgramsView._normalize_repetition_key(
                        repetitions
                    ),
                )
                group = groups.setdefault(
                    key,
                    {
                        "exercise": exercise,
                        "repetitions": repetitions,
                        "set_count": 1,
                        "sources": [],
                        "input_prefix": f"performance_{item.pk}_{slot}",
                    },
                )
                group["set_count"] = max(
                    group["set_count"],
                    gym_program_service.parse_set_count(sets),
                )
                group["sources"].append(
                    {
                        "item": item,
                        "slot": slot,
                        "sets": sets,
                        "reps": repetitions,
                        "rest": rest,
                    }
                )
        return list(groups.values())


class ProfileWorkoutProgramPerformanceView(UserPortalRequiredMixin, View):
    """Save workout set values and optional difficulty feedback for the owner."""

    def post(self, request, pk):
        program = get_object_or_404(
            gym_program_service.get_program_queryset(),
            pk=pk,
            user=request.user,
            is_published=True,
        )
        if not _has_workout_program_access(request.user, program):
            messages.info(request, _("برای مشاهده این برنامه ابتدا هزینه آن را پرداخت کنید."))
            return redirect("register:profile_workout_programs")
        day_id = (request.POST.get("day_id") or "").strip()
        selected_day = None
        if day_id:
            selected_day = get_object_or_404(
                WorkoutProgramDay,
                pk=day_id,
                program=program,
            )
            item_queryset = selected_day.items
        else:
            item_queryset = WorkoutProgramExercise.objects.filter(day__program=program)
        items = list(
            item_queryset.select_related(
                "exercise",
                "superset_exercise",
                "third_exercise",
            )
        )
        valid_modes = set(WorkoutPerformanceRecord.Mode.values)
        performance_values = []
        original_modes = {
            item.pk: item.performance_modes
            if isinstance(item.performance_modes, dict)
            else {}
            for item in items
        }
        selected_modes_by_item = {
            item_id: dict(saved_modes)
            for item_id, saved_modes in original_modes.items()
        }
        errors = []

        for group in ProfileWorkoutProgramsView._build_performance_groups(items):
            posted_sources = [
                (
                    source,
                    f"performance_{source['item'].pk}_{source['slot']}",
                )
                for source in group["sources"]
                if request.POST.get(
                    f"performance_{source['item'].pk}_{source['slot']}_mode"
                )
            ]
            if len(posted_sources) > 1:
                entries = [
                    (
                        source,
                        prefix,
                        gym_program_service.parse_set_count(source["sets"]),
                    )
                    for source, prefix in posted_sources
                ]
            else:
                entries = [
                    (
                        group["sources"][0],
                        group["input_prefix"],
                        group["set_count"],
                    )
                ]

            for source, prefix, set_count in entries:
                mode = (request.POST.get(f"{prefix}_mode") or "").strip()
                if not mode:
                    continue
                if mode not in valid_modes:
                    errors.append(_("نحوه ثبت عملکرد یکی از حرکت‌ها معتبر نیست."))
                    continue

                for selected_source in (
                    group["sources"] if len(posted_sources) <= 1 else [source]
                ):
                    selected_modes_by_item[selected_source["item"].pk][
                        selected_source["slot"]
                    ] = mode

                for set_number in range(1, set_count + 1):
                    raw_value = request.POST.get(
                        f"{prefix}_{mode}_set_{set_number}"
                    )
                    if not (raw_value or "").strip():
                        continue
                    try:
                        value = self._parse_performance_value(raw_value)
                    except ValueError as exc:
                        errors.append(
                            _("%(exercise)s، ست %(set)s: %(error)s")
                            % {
                                "exercise": group["exercise"].name,
                                "set": set_number,
                                "error": str(exc),
                            }
                        )
                        continue
                    performance_values.append(
                        {
                            "user": request.user,
                            "exercise": group["exercise"],
                            "program": program,
                            "program_exercise": source["item"],
                            "repetitions": normalize_digits(group["repetitions"]).strip(),
                            "mode": mode,
                            "set_number": set_number,
                            "value": value,
                        }
                    )

        mode_selections = {
            item_id: selected_modes
            for item_id, selected_modes in selected_modes_by_item.items()
            if selected_modes != original_modes[item_id]
        }

        difficulty_raw = (request.POST.get("difficulty") or "").strip()
        difficulty = None
        if difficulty_raw:
            try:
                difficulty = int(normalize_digits(difficulty_raw))
            except (TypeError, ValueError):
                errors.append(_("سطح دشواری باید عددی بین صفر تا ۱۰ باشد."))
            else:
                if difficulty < 0 or difficulty > 10:
                    errors.append(_("سطح دشواری باید عددی بین صفر تا ۱۰ باشد."))

        if errors:
            for error in errors:
                messages.error(request, error)
            return redirect("register:profile_workout_programs")

        with transaction.atomic():
            saved_count = 0
            if mode_selections:
                items_by_id = {item.pk: item for item in items}
                for item_id, selected_modes in mode_selections.items():
                    item = items_by_id[item_id]
                    item.performance_modes = selected_modes
                    item.save(update_fields=["performance_modes"])

            for payload in performance_values:
                lookup = {
                    "user": payload["user"],
                    "exercise": payload["exercise"],
                    "repetitions": payload["repetitions"],
                    "mode": payload["mode"],
                    "set_number": payload["set_number"],
                }
                record, created = (
                    WorkoutPerformanceRecord.objects.select_for_update().get_or_create(
                        **lookup,
                        defaults={
                            "program": payload["program"],
                            "program_exercise": payload["program_exercise"],
                            "value": payload["value"],
                        },
                    )
                )
                if not created and payload["value"] > record.value:
                    record.value = payload["value"]
                    record.program = payload["program"]
                    record.program_exercise = payload["program_exercise"]
                    record.save(
                        update_fields=[
                            "value",
                            "program",
                            "program_exercise",
                            "updated_at",
                        ]
                    )
                saved_count += 1

            if difficulty is not None:
                WorkoutProgramFeedback.objects.update_or_create(
                    program=program,
                    day=selected_day,
                    defaults={"difficulty": difficulty},
                )

        if saved_count:
            messages.success(
                request,
                _("%(count)s مقدار عملکرد با موفقیت ثبت شد.")
                % {"count": saved_count},
            )
        if difficulty is not None:
            messages.success(request, _("بازخورد سطح دشواری برنامه ثبت شد."))
        if not saved_count and difficulty is None:
            messages.info(request, _("مقداری برای ثبت انتخاب نشده است."))
        return redirect("register:profile_workout_programs")

    @staticmethod
    def _parse_performance_value(raw_value):
        normalized = normalize_digits(raw_value).strip()
        normalized = normalized.replace(",", ".").replace("٫", ".")
        if not re.fullmatch(r"\d+(?:\.\d{1,2})?", normalized):
            raise ValueError(_("مقدار باید یک عدد مثبت باشد."))
        try:
            value = Decimal(normalized)
        except InvalidOperation:
            raise ValueError(_("مقدار باید یک عدد مثبت باشد."))
        if value <= 0:
            raise ValueError(_("مقدار باید بیشتر از صفر باشد."))
        if value > Decimal("999999.99"):
            raise ValueError(_("مقدار واردشده بیش از حد مجاز است."))
        return value


class ProfileWorkoutProgramPdfView(UserPortalRequiredMixin, View):
    def get(self, request, pk):
        program = get_object_or_404(
            gym_program_service.get_program_queryset(),
            pk=pk,
            user=request.user,
            is_published=True,
        )
        if not _has_workout_program_access(request.user, program):
            messages.info(request, _("برای دریافت این برنامه ابتدا هزینه آن را پرداخت کنید."))
            return redirect("register:profile_workout_programs")
        response = HttpResponse(
            build_program_pdf(program, request=request),
            content_type="application/pdf",
        )
        response["Content-Disposition"] = f'attachment; filename="workout-program-{program.pk}.pdf"'
        return response


class ProfileWorkoutMovementView(AccountPageMixin, UserPortalRequiredMixin, TemplateView):
    template_name = "account/workout-movement-detail.html"
    active_section = "workout"
    account_title = _("نمایش حرکت")
    account_description = _("ویدیوی حرکت انتخاب‌شده از کتابخانه ایگوفیت.")

    def dispatch(self, request, *args, **kwargs):
        self.movement_kind = kwargs.get("kind")
        self.movement_id = kwargs.get("movement_id")
        self.return_program = None
        requested_program_id = request.GET.get("program")
        try:
            requested_program_id = int(requested_program_id)
        except (TypeError, ValueError):
            requested_program_id = None

        if self.movement_kind == "exercise":
            movement_queryset = Exercise.objects.select_related(
                "primary_muscle",
                "secondary_muscle",
                "body_part",
            )
            if requested_program_id:
                requested_program = WorkoutProgram.objects.filter(
                    pk=requested_program_id,
                    user=request.user,
                    is_published=True,
                ).first()
                if requested_program and _has_workout_program_access(request.user, requested_program):
                    movement_queryset = movement_queryset.filter(
                        Q(program_items__day__program=requested_program)
                        | Q(superset_program_items__day__program=requested_program)
                        | Q(third_program_items__day__program=requested_program)
                    ).distinct()
                    self.return_program = requested_program

            self.movement = get_object_or_404(
                movement_queryset.filter(
                    (
                        Q(
                            program_items__day__program__user=request.user,
                            program_items__day__program__is_published=True,
                            program_items__day__program__requires_payment=False,
                        )
                        | Q(
                            program_items__day__program__user=request.user,
                            program_items__day__program__is_published=True,
                            program_items__day__program__payments__user=request.user,
                            program_items__day__program__payments__status=WorkoutProgramPayment.Status.PAID,
                        )
                        | Q(
                            superset_program_items__day__program__user=request.user,
                            superset_program_items__day__program__is_published=True,
                            superset_program_items__day__program__requires_payment=False,
                        )
                        | Q(
                            superset_program_items__day__program__user=request.user,
                            superset_program_items__day__program__is_published=True,
                            superset_program_items__day__program__payments__user=request.user,
                            superset_program_items__day__program__payments__status=WorkoutProgramPayment.Status.PAID,
                        )
                        | Q(
                            third_program_items__day__program__user=request.user,
                            third_program_items__day__program__is_published=True,
                            third_program_items__day__program__requires_payment=False,
                        )
                        | Q(
                            third_program_items__day__program__user=request.user,
                            third_program_items__day__program__is_published=True,
                            third_program_items__day__program__payments__user=request.user,
                            third_program_items__day__program__payments__status=WorkoutProgramPayment.Status.PAID,
                        )
                    ),
                ).distinct(),
                pk=self.movement_id,
            )
            if self.return_program is None:
                self.return_program = (
                    WorkoutProgram.objects.filter(
                        user=request.user,
                        is_published=True,
                    ).filter(
                        Q(requires_payment=False)
                        | Q(payments__user=request.user, payments__status=WorkoutProgramPayment.Status.PAID)
                    )
                    .filter(
                        Q(days__items__exercise_id=self.movement.pk)
                        | Q(days__items__superset_exercise_id=self.movement.pk)
                        | Q(days__items__third_exercise_id=self.movement.pk)
                    )
                    .order_by("pk")
                    .first()
                )
        elif self.movement_kind == "corrective":
            movement_queryset = CorrectiveExercise.objects.select_related(
                "equipment",
                "abnormality_type",
            )
            if requested_program_id:
                requested_program = WorkoutProgram.objects.filter(
                    pk=requested_program_id,
                    user=request.user,
                    is_published=True,
                ).first()
                if requested_program and _has_workout_program_access(request.user, requested_program):
                    movement_queryset = movement_queryset.filter(
                        program_items__program=requested_program
                    ).distinct()
                    self.return_program = requested_program

            self.movement = get_object_or_404(
                movement_queryset.filter(
                    Q(
                        program_items__program__user=request.user,
                        program_items__program__is_published=True,
                        program_items__program__requires_payment=False,
                    )
                    | Q(
                        program_items__program__user=request.user,
                        program_items__program__is_published=True,
                        program_items__program__payments__user=request.user,
                        program_items__program__payments__status=WorkoutProgramPayment.Status.PAID,
                    ),
                ).distinct(),
                pk=self.movement_id,
            )
            if self.return_program is None:
                self.return_program = (
                    WorkoutProgram.objects.filter(
                        user=request.user,
                        is_published=True,
                        corrective_items__corrective_exercise_id=self.movement.pk,
                    ).filter(
                        Q(requires_payment=False)
                        | Q(payments__user=request.user, payments__status=WorkoutProgramPayment.Status.PAID)
                    )
                    .order_by("pk")
                    .first()
                )
        else:
            return redirect("register:profile_workout_programs")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["movement"] = self.movement
        context["movement_kind"] = self.movement_kind
        context["return_program"] = self.return_program
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


class NumberEdit(AccountPageMixin, UserPortalRequiredMixin, View):
    template_name = "account/edit_number.html"
    active_section = "number"
    account_title = _("ویرایش شماره تماس")
    account_description = _("شماره تماس حساب خود را با دریافت کد تایید به‌روزرسانی کنید.")

    def get(self, request):
        return render(
            request,
            self.template_name,
            {
                "form": NumberEditForm(initial={"phone_number_new": ""}),
                "active_section": self.active_section,
                "account_title": self.account_title,
                "account_description": self.account_description,
            },
        )

    def post(self, request):
        form = NumberEditForm(request.POST)
        if form.is_valid():
            new_phone = form.cleaned_data["phone_number_new"]
            try:
                enforce_web_otp_rate_limit(request, new_phone)
                token = profile_service.request_phone_change(
                    user=request.user,
                    new_phone=new_phone,
                    session=request.session,
                    otp_creator=create_and_send_otp,
                )
            except PhoneAlreadyExistsException as exc:
                form.add_error("phone_number_new", str(exc))
                return render(
                    request,
                    self.template_name,
                    {
                        "form": form,
                        "active_section": self.active_section,
                        "account_title": self.account_title,
                        "account_description": self.account_description,
                    },
                )
            except SMSProviderException as exc:
                form.add_error("phone_number_new", str(exc))
                return render(
                    request,
                    self.template_name,
                    {
                        "form": form,
                        "active_section": self.active_section,
                        "account_title": self.account_title,
                        "account_description": self.account_description,
                    },
                )
            except OTPRateLimitExceededException as exc:
                form.add_error("phone_number_new", str(exc))
                return render(
                    request,
                    self.template_name,
                    {
                        "form": form,
                        "active_section": self.active_section,
                        "account_title": self.account_title,
                        "account_description": self.account_description,
                    },
                )

            messages.success(request, _("کد تایید برای شماره جدید ارسال شد."))
            return redirect(f"{reverse('register:profile_number_verify')}?token={token}")
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "active_section": self.active_section,
                "account_title": self.account_title,
                "account_description": self.account_description,
            },
        )


class NumberEditVerify(AccountPageMixin, UserPortalRequiredMixin, View):
    template_name = "account/edit_number_verify.html"
    active_section = "number"
    account_title = _("تایید شماره تماس")
    account_description = _("کد ارسال شده به شماره جدید را وارد کنید.")

    def get(self, request):
        return render(request, self.template_name, {"form": CheckOtp()})

    def post(self, request):
        token = (request.GET.get("token") or "").strip()
        form = CheckOtp(request.POST)

        if form.is_valid():
            try:
                profile_service.confirm_phone_change(
                    user=request.user,
                    token=token,
                    code=int(form.cleaned_data["code"]),
                    session=request.session,
                )
                messages.success(request, _("شماره تماس با موفقیت تایید و بروزرسانی شد."))
                return redirect("register:profile_number_edit")
            except (SessionValidationException, AuthenticationException):
                messages.error(request, _("درخواست تغییر شماره معتبر نیست."))
                return redirect("register:profile_number_edit")
            except PhoneAlreadyExistsException:
                form.add_error("code", _("شماره تماس جدید معتبر نیست."))
            except (InvalidOtpException, ExpiredOtpException):
                form.add_error("code", _("کد وارد شده نادرست یا منقضی شده است."))

        return render(request, self.template_name, {"form": form})


def signup(request):
    if request.method == "POST":
        form = FormRegister(request.POST)
        if form.is_valid():
            phone = form.cleaned_data["phone"]
            password = form.cleaned_data["password"]
            fullname = form.cleaned_data["fullname"]

            try:
                user = auth_service.register_user(fullname=fullname, phone=phone, password=password)
            except AuthenticationException as exc:
                form.add_error("fullname", str(exc))
                return render(request, "account/pass_register.html", {"form": form})
            except PhoneAlreadyExistsException as exc:
                form.add_error("phone", str(exc))
                return render(request, "account/pass_register.html", {"form": form})

            login(request, user)
            session_service.queue_login_session_log(user=user, request=request)
            messages.success(request, _("با موفقیت وارد شدید."))
            return redirect(get_post_login_redirect_url(user))
    else:
        form = FormRegister()

    return render(request, "account/pass_register.html", {"form": form})


class PasswordsChangeView(AccountPageMixin, UserPortalRequiredMixin, PasswordChangeView):
    form_class = PasswordChanged
    success_url = reverse_lazy("home:home")
    template_name = "account/change_password.html"
    active_section = "password"
    account_title = _("تغییر رمز عبور")
    account_description = _("رمز عبور حساب خود را به شکل امن به‌روز کنید.")

    def form_valid(self, form):
        response = super().form_valid(form)
        update_session_auth_hash(self.request, form.user)
        messages.success(self.request, _("رمز عبور شما با موفقیت تغییر کرد."))
        return response


def login_view(request):
    if request.method == "POST":
        form = FormLogin(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            try:
                user = auth_service.authenticate_user(fullname=cd["fullname"], password=cd["password"])
                login(request, user)
                session_service.queue_login_session_log(user=user, request=request)
                messages.success(request, _("با موفقیت وارد شدید."))
                return redirect(get_post_login_redirect_url(user))
            except AuthenticationException:
                form.add_error(None, _("نام کاربری یا کلمه عبور اشتباه است."))
    else:
        form = FormLogin()
    return render(request, "account/pass_login.html", {"form": form})


class ForgotPasswordView(View):
    template_name = "account/forgot_password.html"

    def get(self, request):
        return render(request, self.template_name, {"form": PasswordResetRequestForm()})

    def post(self, request):
        form = PasswordResetRequestForm(request.POST)
        if form.is_valid():
            try:
                enforce_web_otp_rate_limit(request, form.cleaned_data["phone"])
                token = profile_service.request_password_reset(
                    phone=form.cleaned_data["phone"],
                    session=request.session,
                    otp_creator=create_and_send_otp,
                )
            except PasswordResetException as exc:
                form.add_error("phone", str(exc))
                return render(request, self.template_name, {"form": form})
            except SMSProviderException as exc:
                form.add_error("phone", str(exc))
                return render(request, self.template_name, {"form": form})
            except OTPRateLimitExceededException as exc:
                form.add_error("phone", str(exc))
                return render(request, self.template_name, {"form": form})

            messages.success(request, _("کد تایید برای شماره شما ارسال شد."))
            return redirect(f"{reverse('register:forgot_password_confirm')}?token={token}")
        return render(request, self.template_name, {"form": form})


class ForgotPasswordConfirmView(View):
    template_name = "account/forgot_password_confirm.html"

    def get(self, request):
        return render(request, self.template_name, {"form": PasswordResetConfirmForm()})

    def post(self, request):
        token = (request.GET.get("token") or "").strip()
        session_token = request.session.get("password_reset_token")
        form = PasswordResetConfirmForm(request.POST)

        if token != session_token:
            messages.error(request, _("درخواست بازیابی رمز عبور معتبر نیست."))
            return redirect("register:forgot_password")

        if form.is_valid():
            try:
                profile_service.confirm_password_reset(
                    token=token,
                    code=int(form.cleaned_data["code"]),
                    new_password=form.cleaned_data["new_password1"],
                    session=request.session,
                )
                messages.success(request, _("رمز عبور با موفقیت تغییر کرد. اکنون وارد حساب شوید."))
                return redirect("register:pass_login")
            except (InvalidOtpException, ExpiredOtpException):
                form.add_error("code", _("کد وارد شده نادرست یا منقضی شده است."))
            except (SessionValidationException, AuthenticationException):
                messages.error(request, _("درخواست بازیابی رمز عبور معتبر نیست."))
                return redirect("register:forgot_password")
            except PasswordResetException as exc:
                form.add_error("code", str(exc))

        return render(request, self.template_name, {"form": form})
