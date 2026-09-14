from __future__ import annotations

import jdatetime
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.views import PasswordChangeView
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import ListView, TemplateView

from account.admin_forms import (
    AdminBulkCoachAssignForm,
    AdminCaliperForm,
    AdminCircumferenceForm,
    AdminClientDocumentForm,
    AdminClientMediaForm,
    AdminCommentModerationForm,
    AdminPersonalInfoForm,
    AdminRoleToggleForm,
    AdminUserCoachForm,
    AdminUserCreateForm,
    AdminUserSearchForm,
)
from account.froms import PasswordChanged
from account.models import BirthdaySmsLog, BodyCircumferenceMeasurement, CaliperMeasurement, CoachRequest, User
from home.models import Comment, CommentSectionModel, Reply
from account.portal_mixins import AdminRequiredMixin
from account.selectors.user_selector import UserSelector
from account.services.admin_portal_service import AdminPortalService

admin_portal_service = AdminPortalService()

USER_LIST_SORT_OPTIONS = {
    "fullname": "fullname",
    "-fullname": "-fullname",
    "-id": "-id",
    "coach": "coach__fullname",
    "-coach": "-coach__fullname",
}


class AdminPageMixin(AdminRequiredMixin):
    active_section = "search"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault("active_section", self.active_section)
        return context


class AdminSearchView(AdminPageMixin, TemplateView):
    template_name = "admin_portal/search.html"
    active_section = "search"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = (self.request.GET.get("query") or "").strip()
        form = AdminUserSearchForm(initial={"query": query})
        results = admin_portal_service.search_users(query=query) if query else []
        context.update(admin_portal_service.get_dashboard_context())
        context.update(
            {
                "form": form,
                "search_query": query,
                "search_results": results,
                "has_searched": bool(query),
            }
        )
        return context


class AdminUserListView(AdminPageMixin, ListView):
    model = User
    template_name = "admin_portal/user_list.html"
    context_object_name = "clients"
    active_section = "clients"
    paginate_by = 20

    def get_queryset(self):
        queryset = User.objects.select_related("coach")
        query = (self.request.GET.get("query") or "").strip()
        queryset = UserSelector.search_clients(queryset, query)
        sort = self.request.GET.get("sort") or "fullname"
        return queryset.order_by(USER_LIST_SORT_OPTIONS.get(sort, "fullname"))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        search_query = (self.request.GET.get("query") or "").strip()
        context.update(
            {
                "form": AdminUserSearchForm(initial={"query": search_query}),
                "search_query": search_query,
                "current_sort": self.request.GET.get("sort") or "fullname",
            }
        )
        return context


class AdminUserCreateView(AdminPageMixin, View):
    template_name = "admin_portal/user_create.html"
    active_section = "clients"

    def get(self, request):
        return render(request, self.template_name, self._context(AdminUserCreateForm()))

    def post(self, request):
        form = AdminUserCreateForm(request.POST)
        if form.is_valid():
            user = admin_portal_service.create_user(form=form)
            messages.success(request, _("کاربر جدید با موفقیت اضافه شد."))
            return redirect("register:admin_circumference", user_id=user.pk)
        return render(request, self.template_name, self._context(form))

    def _context(self, form):
        return {
            "form": form,
            "active_section": self.active_section,
            "page_title": _("افزودن کاربر جدید"),
        }


class AdminUserDeleteView(AdminRequiredMixin, View):
    def post(self, request, user_id):
        target = get_object_or_404(User, pk=user_id, is_admin=False)
        success, error = admin_portal_service.delete_user(target)
        if success:
            messages.success(request, _("کاربر با موفقیت حذف شد."))
        else:
            messages.error(request, error)
        return redirect("register:admin_user_list")


class AdminUserMixin(AdminPageMixin):
    def dispatch(self, request, *args, **kwargs):
        self.target_user = get_object_or_404(User, pk=kwargs["user_id"])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["target_user"] = self.target_user
        return context


class AdminUserHubView(AdminUserMixin, TemplateView):
    template_name = "admin_portal/user_hub.html"
    active_section = "records"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(admin_portal_service.get_user_summary_context(self.target_user))
        return context


class AdminPersonalInfoView(AdminUserMixin, View):
    template_name = "admin_portal/personal_info.html"
    active_section = "records"

    def get(self, request, user_id):
        form = AdminPersonalInfoForm(instance=self.target_user)
        return render(request, self.template_name, self._context(form))

    def post(self, request, user_id):
        form = AdminPersonalInfoForm(request.POST, instance=self.target_user)
        if form.is_valid():
            form.save()
            messages.success(request, _("اطلاعات شخصی با موفقیت ثبت شد."))
            return redirect("register:admin_user_hub", user_id=self.target_user.pk)
        return render(request, self.template_name, self._context(form))

    def _context(self, form):
        return {
            "form": form,
            "target_user": self.target_user,
            "active_section": self.active_section,
            "page_title": _("ثبت اطلاعات شخصی"),
        }


class AdminCircumferenceView(AdminUserMixin, View):
    template_name = "admin_portal/circumference.html"
    active_section = "records"

    def get(self, request, user_id):
        instance = admin_portal_service.get_or_create_circumference(self.target_user)
        form = AdminCircumferenceForm(instance=instance)
        return render(request, self.template_name, self._context(form))

    def post(self, request, user_id):
        instance = admin_portal_service.get_or_create_circumference(self.target_user)
        form = AdminCircumferenceForm(request.POST, instance=instance)
        if form.is_valid():
            admin_portal_service.save_circumference(user=self.target_user, form=form)
            messages.success(request, _("اندازه‌گیری محیط بدن ثبت شد."))
            return redirect("register:admin_user_hub", user_id=self.target_user.pk)
        return render(request, self.template_name, self._context(form))

    def _context(self, form):
        return {
            "form": form,
            "target_user": self.target_user,
            "active_section": self.active_section,
            "page_title": _("ثبت اندازه‌گیری محیط بدن"),
            "is_edit": False,
        }


class AdminCircumferenceEditView(AdminUserMixin, View):
    template_name = "admin_portal/circumference.html"
    active_section = "records"

    def get(self, request, user_id, pk):
        instance = get_object_or_404(BodyCircumferenceMeasurement, pk=pk, user=self.target_user)
        form = AdminCircumferenceForm(instance=instance)
        return render(request, self.template_name, self._context(form, instance))

    def post(self, request, user_id, pk):
        instance = get_object_or_404(BodyCircumferenceMeasurement, pk=pk, user=self.target_user)
        form = AdminCircumferenceForm(request.POST, instance=instance)
        if form.is_valid():
            admin_portal_service.update_circumference(form=form)
            messages.success(request, _("اندازه‌گیری به‌روزرسانی شد."))
            return redirect("register:admin_measurement_history", user_id=self.target_user.pk)
        return render(request, self.template_name, self._context(form, instance))

    def _context(self, form, instance):
        return {
            "form": form,
            "target_user": self.target_user,
            "active_section": self.active_section,
            "page_title": _("ویرایش اندازه‌گیری"),
            "is_edit": True,
            "edit_pk": instance.pk,
        }


class AdminCaliperView(AdminUserMixin, View):
    template_name = "admin_portal/caliper.html"
    active_section = "records"

    def get(self, request, user_id):
        instance = admin_portal_service.get_or_create_caliper(self.target_user)
        form = AdminCaliperForm(instance=instance)
        return render(request, self.template_name, self._context(form))

    def post(self, request, user_id):
        instance = admin_portal_service.get_or_create_caliper(self.target_user)
        form = AdminCaliperForm(request.POST, instance=instance)
        if form.is_valid():
            admin_portal_service.save_caliper(user=self.target_user, form=form)
            messages.success(request, _("اندازه‌گیری کالیپر ثبت شد."))
            return redirect("register:admin_user_hub", user_id=self.target_user.pk)
        return render(request, self.template_name, self._context(form))

    def _context(self, form):
        return {
            "form": form,
            "target_user": self.target_user,
            "active_section": self.active_section,
            "page_title": _("ثبت کالیپر (Caliper)"),
            "is_edit": False,
        }


class AdminCaliperEditView(AdminUserMixin, View):
    template_name = "admin_portal/caliper.html"
    active_section = "records"

    def get(self, request, user_id, pk):
        instance = get_object_or_404(CaliperMeasurement, pk=pk, user=self.target_user)
        form = AdminCaliperForm(instance=instance)
        return render(request, self.template_name, self._context(form, instance))

    def post(self, request, user_id, pk):
        instance = get_object_or_404(CaliperMeasurement, pk=pk, user=self.target_user)
        form = AdminCaliperForm(request.POST, instance=instance)
        if form.is_valid():
            admin_portal_service.update_caliper(form=form)
            messages.success(request, _("اندازه‌گیری به‌روزرسانی شد."))
            return redirect("register:admin_measurement_history", user_id=self.target_user.pk)
        return render(request, self.template_name, self._context(form, instance))

    def _context(self, form, instance):
        return {
            "form": form,
            "target_user": self.target_user,
            "active_section": self.active_section,
            "page_title": _("ویرایش اندازه‌گیری"),
            "is_edit": True,
            "edit_pk": instance.pk,
        }


def _measurement_date_label(record) -> str:
    if record.measured_at_jalali:
        return record.measured_at_jalali
    local = timezone.localtime(record.recorded_at)
    return jdatetime.datetime.fromgregorian(datetime=local).strftime("%Y/%m/%d")


class AdminMeasurementHistoryView(AdminUserMixin, TemplateView):
    template_name = "admin_portal/measurement_history.html"
    active_section = "records"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        entries = [
            {
                "kind": "circumference",
                "label": _("اندازه‌گیری محیط بدن"),
                "date": _measurement_date_label(record),
                "edit_url": reverse("register:admin_circumference_edit", args=[self.target_user.pk, record.pk]),
            }
            for record in self.target_user.circumference_records.all()
        ] + [
            {
                "kind": "caliper",
                "label": _("اندازه‌گیری کالیپر"),
                "date": _measurement_date_label(record),
                "edit_url": reverse("register:admin_caliper_edit", args=[self.target_user.pk, record.pk]),
            }
            for record in self.target_user.caliper_records.all()
        ]
        entries.sort(key=lambda item: item["date"], reverse=True)
        context["measurement_entries"] = entries
        return context


class AdminUserAnalysisView(AdminUserMixin, TemplateView):
    template_name = "admin_portal/analysis.html"
    active_section = "analysis"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            admin_portal_service.get_analysis_context(
                self.target_user,
                metric=self.request.GET.get("metric"),
                circ_date=self.request.GET.get("circ_date"),
                body_fat_formula=self.request.GET.get("body_fat_formula"),
                use_full_chart_range=True,
            )
        )
        selected_body_fat_formula = context.get("analysis_selected_body_fat_formula")
        context.update(
            admin_portal_service.get_analysis_dashboard_data(
                self.target_user,
                body_fat_formula=selected_body_fat_formula,
            )
        )
        context["analysis_metric_series"] = admin_portal_service.get_analysis_metric_series(
            self.target_user,
            body_fat_formula=selected_body_fat_formula,
        )
        context["page_title"] = self.target_user.fullname
        return context


class AdminCoachManagementView(AdminPageMixin, View):
    template_name = "admin_portal/coach_management.html"
    active_section = "coaches"

    def get(self, request):
        return render(request, self.template_name, self._context())

    def post(self, request):
        action = request.POST.get("action")
        if action == "bulk_assign":
            form = AdminBulkCoachAssignForm(request.POST)
            if form.is_valid():
                coach = form.cleaned_data["coach"]
                count = admin_portal_service.assign_coach_to_all(coach)
                messages.success(
                    request,
                    _("مربی «%(coach)s» برای %(count)s کاربر تنظیم شد.") % {"coach": coach.fullname, "count": count},
                )
                return redirect("register:admin_coach_management")
            return render(request, self.template_name, self._context(bulk_form=form))

        if action == "update_user":
            user_id = request.POST.get("user_id")
            target = get_object_or_404(User, pk=user_id, is_admin=False)
            form = AdminUserCoachForm(request.POST)
            if form.is_valid():
                admin_portal_service.assign_coach_to_user(target, form.cleaned_data.get("coach"))
                messages.success(
                    request,
                    _("مربی کاربر «%(name)s» به‌روزرسانی شد.") % {"name": target.fullname},
                )
            else:
                messages.error(request, _("انتخاب مربی معتبر نیست."))
            return redirect("register:admin_coach_management")

        return redirect("register:admin_coach_management")

    def _context(self, bulk_form=None):
        context = admin_portal_service.get_coach_management_context()
        if bulk_form is not None:
            context["bulk_form"] = bulk_form
        context.update(
            {
                "active_section": self.active_section,
                "page_title": _("مدیریت مربیان"),
            }
        )
        return context


class AdminPasswordChangeView(AdminPageMixin, PasswordChangeView):
    form_class = PasswordChanged
    template_name = "admin_portal/change_password.html"
    success_url = reverse_lazy("register:admin_search")
    active_section = "settings"

    def form_valid(self, form):
        response = super().form_valid(form)
        update_session_auth_hash(self.request, form.user)
        messages.success(self.request, _("رمز عبور شما با موفقیت تغییر کرد."))
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = _("تغییر رمز عبور")
        return context


class AdminUploadView(AdminUserMixin, View):
    template_name = "admin_portal/upload.html"
    active_section = "search"
    hide_admin_chrome = True

    def get(self, request, user_id):
        return render(request, self.template_name, self._context(AdminClientMediaForm(), AdminClientDocumentForm()))

    def post(self, request, user_id):
        upload_kind = request.POST.get("upload_kind")

        if upload_kind == "document":
            document_form = AdminClientDocumentForm(request.POST, request.FILES)
            media_form = AdminClientMediaForm()
            if document_form.is_valid():
                admin_portal_service.save_document(user=self.target_user, uploaded_by=request.user, form=document_form)
                messages.success(request, _("برنامه/فایل با موفقیت آپلود شد."))
                return redirect("register:admin_user_hub", user_id=self.target_user.pk)
        else:
            media_form = AdminClientMediaForm(request.POST, request.FILES)
            document_form = AdminClientDocumentForm()
            if media_form.is_valid():
                if not media_form.cleaned_data.get("image") and not media_form.cleaned_data.get("video"):
                    media_form.add_error(None, _("حداقل یک فایل تصویر یا ویدیو انتخاب کنید."))
                else:
                    admin_portal_service.save_media(user=self.target_user, uploaded_by=request.user, form=media_form)
                    messages.success(request, _("فایل با موفقیت آپلود شد."))
                    return redirect("register:admin_search")

        return render(request, self.template_name, self._context(media_form, document_form))

    def _context(self, media_form, document_form):
        return {
            "form": media_form,
            "document_form": document_form,
            "target_user": self.target_user,
            "active_section": self.active_section,
            "hide_admin_chrome": self.hide_admin_chrome,
            "page_title": _("آپلود فایل"),
        }


class AdminRoleToggleView(AdminRequiredMixin, View):
    def post(self, request, user_id):
        target_user = get_object_or_404(User, pk=user_id, is_admin=False)
        form = AdminRoleToggleForm(request.POST)
        if form.is_valid():
            try:
                admin_portal_service.toggle_admin_role(
                    actor=request.user,
                    target=target_user,
                    make_admin=form.cleaned_data["is_admin"],
                )
                messages.success(request, _("نقش کاربر به‌روزرسانی شد."))
            except ValueError as exc:
                messages.error(request, str(exc))
        return redirect(f"{reverse('register:admin_search')}?query={target_user.fullname}")


class CoachRequestMarkHandledView(AdminRequiredMixin, View):
    def post(self, request, pk):
        coach_request = get_object_or_404(CoachRequest, pk=pk)
        admin_portal_service.mark_coach_request_handled(coach_request)
        messages.success(request, _("درخواست به‌عنوان بررسی‌شده علامت خورد."))
        next_url = request.POST.get("next") or reverse("register:admin_search")
        return redirect(next_url)


class CoachRequestPushMeasurementsView(AdminRequiredMixin, View):
    def post(self, request, pk):
        coach_request = get_object_or_404(CoachRequest, pk=pk)
        instance = admin_portal_service.push_coach_request_to_measurements(coach_request)
        if instance is not None:
            messages.success(request, _("اندازه‌های درخواست به اندازه‌گیری‌های کاربر افزوده شد."))
        else:
            messages.info(request, _("اندازه‌ای برای افزودن وجود ندارد یا قبلاً افزوده شده است."))
        next_url = request.POST.get("next") or reverse("register:admin_search")
        return redirect(next_url)


class AdminNotificationsView(AdminPageMixin, TemplateView):
    template_name = "admin_portal/notifications.html"
    active_section = "notifications"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        admin_portal_service.send_pending_birthday_sms()
        today_jalali = jdatetime.date.today().strftime("%Y/%m/%d")
        sent_user_ids = set(
            BirthdaySmsLog.objects.filter(sent_on=today_jalali).values_list("user_id", flat=True)
        )
        birthday_users = [
            {"user": user, "sms_sent": user.pk in sent_user_ids}
            for user in admin_portal_service.get_birthday_users()
        ]
        context.update(
            {
                "pending_coach_requests": list(admin_portal_service.coach_request_service.get_pending_queryset()),
                "birthday_users": birthday_users,
                "pending_opinions": list(
                    Comment.objects.filter(publication_status=Comment.PublicationStatus.PENDING)
                    .select_related("user")
                    .order_by("-id")
                ),
                "pending_comments": list(
                    CommentSectionModel.objects.filter(publication_status=CommentSectionModel.PublicationStatus.PENDING)
                    .select_related("user", "series")
                    .order_by("-created_at")
                ),
            }
        )
        return context


class AdminCommentModerationView(AdminRequiredMixin, View):
    def post(self, request):
        kind = request.POST.get("kind")
        object_id = request.POST.get("object_id")
        form = AdminCommentModerationForm(request.POST)
        if not form.is_valid():
            messages.error(request, _("عملیات دیدگاه معتبر نیست."))
            return redirect("register:admin_notifications")

        action = form.cleaned_data["action"]
        response_text = (form.cleaned_data.get("response") or "").strip()
        if kind == "opinion":
            item = get_object_or_404(Comment, pk=object_id)
            if action in {"approve", "reject"}:
                item.is_active = action == "approve"
                item.publication_status = Comment.PublicationStatus.APPROVED if action == "approve" else Comment.PublicationStatus.REJECTED
            if response_text:
                item.admin_response = response_text
                item.responded_at = timezone.now()
            item.save(update_fields=["is_active", "publication_status", "admin_response", "responded_at"])
        elif kind == "comment":
            item = get_object_or_404(CommentSectionModel, pk=object_id)
            if action in {"approve", "reject"}:
                item.is_active = action == "approve"
                item.publication_status = CommentSectionModel.PublicationStatus.APPROVED if action == "approve" else CommentSectionModel.PublicationStatus.REJECTED
                item.save(update_fields=["is_active", "publication_status"])
            if response_text:
                Reply.objects.create(comment=item, user=request.user, text=response_text, is_active=True)
        else:
            messages.error(request, _("نوع دیدگاه معتبر نیست."))
            return redirect("register:admin_notifications")

        messages.success(request, _("عملیات دیدگاه با موفقیت ثبت شد."))
        return redirect("register:admin_notifications")
