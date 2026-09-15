from __future__ import annotations

import os

from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.views import PasswordChangeView
from django.http import FileResponse
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
    FormLogin,
    FormRegister,
    NumberEditForm,
    OtpForm,
    PasswordChanged,
    PasswordResetConfirmForm,
    PasswordResetRequestForm,
)
from account.services import AuthService, OTPService, ProfileService, SessionService, create_and_send_otp
from account.services.access_payment_service import AccessPaymentService
from account.portal_mixins import UserPortalRequiredMixin, get_post_login_redirect_url
from account.utils import format_phone_display, normalize_digits
from account.view_mixins import AccountPageMixin
from account.models import (
    ClientDocument,
    ClientDocumentPayment,
    WorkoutProgram,
    WorkoutProgramPayment,
)
from cart.exceptions import PaymentProviderException, PaymentVerificationException
from cart.providers.zarinpal_provider import ZarinPalPaymentProvider
from cart.zarinpal import build_payment_callback_url


auth_service = AuthService()
otp_service = OTPService()
profile_service = ProfileService()
session_service = SessionService()
access_payment_service = AccessPaymentService()


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


# Compatibility exports: URLs and older integrations can continue importing
# account views while profile and workout pages move to dedicated modules.
from account.workout_views import (
    ProfileWorkoutMovementView,
    ProfileWorkoutProgramPerformanceView,
    ProfileWorkoutProgramPdfView,
    ProfileWorkoutProgramsView,
    _has_workout_program_access,
)
from account.profile_views import (  # noqa: E402,F401
    AddCourseToProfileView,
    ProfileAnalysisView,
    ProfileCoachView,
    ProfileCommentsView,
    ProfileCoursesView,
    ProfileDocumentsView,
    ProfileFinancialView,
    ProfileMetricEditView,
    ProfileNotificationsView,
    ProfileView,
    edit_user_profile,
)
