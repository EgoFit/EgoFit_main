from django import forms
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.cache import cache
from django.db import transaction
from django.http import HttpResponse
from django.urls import path
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from account.constants import GLOBAL_NOTIFICATION_CACHE_KEY
from account.admin_forms import CorrectiveExerciseForm
from account.models import (
    BodyCircumferenceMeasurement,
    CaliperMeasurement,
    ClientDocument,
    ClientMedia,
    CoachRequest,
    CorrectiveExercise,
    Exercise,
    ExerciseBodyPart,
    ExerciseDifficultyLevel,
    ExerciseEquipmentType,
    ExerciseJointType,
    ExerciseMovementType,
    ExercisePowerType,
    Muscle,
    Notification,
    Otp,
    User,
    UserSession,
    WorkoutPerformanceRecord,
    WorkoutProgram,
    WorkoutProgramPayment,
    WorkoutProgramCorrective,
    WorkoutProgramDay,
    WorkoutProgramExercise,
    WorkoutProgramFeedback,
)
from account.services.notification_service import NotificationService
from account.tasks.dispatch import dispatch_task
from account.tasks.sms_tasks import send_notification_sms_broadcast as send_notification_sms_broadcast_task
from account.validators import validate_strong_password


class UserCreationForm(forms.ModelForm):
    password1 = forms.CharField(label=_("گذرواژه"), widget=forms.PasswordInput, required=False)
    password2 = forms.CharField(label=_("تایید گذرواژه"), widget=forms.PasswordInput, required=False)

    class Meta:
        model = User
        fields = ["fullname", "phone", "email", "is_active", "is_admin"]

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 or password2:
            if password1 != password2:
                raise ValidationError(_("رمز عبور و تکرار آن یکسان نیست."))
            validate_strong_password(password1)
        return password2

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get("password1")
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        if commit:
            user.save()
        return user


class UserChangeForm(forms.ModelForm):
    password1 = forms.CharField(
        label=_("رمز عبور جدید"),
        widget=forms.PasswordInput,
        required=False,
        help_text=_("برای کاربرانی که فقط با OTP وارد می‌شوند، اینجا رمز تعیین کنید."),
    )
    password2 = forms.CharField(label=_("تایید رمز عبور جدید"), widget=forms.PasswordInput, required=False)
    password_status = forms.CharField(
        label=_("وضعیت رمز عبور"),
        required=False,
        disabled=True,
        help_text=_("رمز ذخیره‌شده قابل مشاهده نیست؛ فقط می‌توانید رمز جدید تنظیم کنید."),
    )

    class Meta:
        model = User
        fields = [
            "fullname",
            "phone",
            "email",
            "display_name",
            "first_name",
            "last_name",
            "is_active",
            "is_admin",
            "coach",
            "birth_date_jalali",
            "weight_kg",
            "height_cm",
            "blood_group",
            "gender",
            "activity_level",
            "biography",
            "telegram",
            "github",
            "linkdin",
            "web_site",
            "profile_picture",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            if self.instance.has_usable_password():
                self.fields["password_status"].initial = _("تنظیم شده (ورود با نام کاربری و رمز)")
            else:
                self.fields["password_status"].initial = _("تنظیم نشده (فقط ورود با OTP)")

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 or password2:
            if password1 != password2:
                raise ValidationError(_("رمز عبور و تکرار آن یکسان نیست."))
            validate_strong_password(password1)
        return password2

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get("password1")
        if password:
            user.set_password(password)
        if commit:
            user.save()
        return user


@admin.action(description=_("فعال‌سازی کاربران انتخاب‌شده"))
def activate_users(modeladmin, request, queryset):
    updated = queryset.update(is_active=True)
    modeladmin.message_user(request, _("%(count)s کاربر فعال شد.") % {"count": updated})


@admin.action(description=_("غیرفعال‌سازی کاربران انتخاب‌شده"))
def deactivate_users(modeladmin, request, queryset):
    updated = queryset.update(is_active=False)
    modeladmin.message_user(request, _("%(count)s کاربر غیرفعال شد.") % {"count": updated})


@admin.action(description=_("تبدیل به ادمین"))
def promote_to_admin(modeladmin, request, queryset):
    updated = queryset.update(is_admin=True)
    modeladmin.message_user(request, _("%(count)s کاربر به ادمین تبدیل شد.") % {"count": updated})


@admin.action(description=_("حذف دسترسی ادمین"))
def demote_from_admin(modeladmin, request, queryset):
    if queryset.filter(is_admin=True).count() == User.objects.filter(is_admin=True).count():
        modeladmin.message_user(request, _("حداقل یک ادمین باید در سیستم باقی بماند."), level=messages.ERROR)
        return
    updated = queryset.update(is_admin=False)
    modeladmin.message_user(request, _("%(count)s کاربر از حالت ادمین خارج شد.") % {"count": updated})


class UserAdmin(BaseUserAdmin):
    form = UserChangeForm
    add_form = UserCreationForm
    change_list_template = "admin/account/user/change_list.html"
    list_display = ["fullname", "phone", "email", "password_status_display", "is_admin", "is_active", "coach"]
    list_select_related = ("coach",)
    list_filter = ["is_admin", "is_active", "gender", "activity_level"]
    search_fields = ["email", "fullname", "phone", "display_name"]
    ordering = ["fullname"]
    filter_horizontal = ()
    actions = [activate_users, deactivate_users, promote_to_admin, demote_from_admin]
    readonly_fields = ["last_login"]

    fieldsets = [
        (
            _("ورود و امنیت"),
            {
                "fields": [
                    "password_status",
                    "password1",
                    "password2",
                    "last_login",
                ]
            },
        ),
        (
            _("اطلاعات اصلی"),
            {
                "fields": [
                    "fullname",
                    "phone",
                    "email",
                    "display_name",
                    "first_name",
                    "last_name",
                    "profile_picture",
                ]
            },
        ),
        (
            _("پروفایل سلامت"),
            {
                "fields": [
                    "birth_date_jalali",
                    "weight_kg",
                    "height_cm",
                    "blood_group",
                    "gender",
                    "activity_level",
                    "coach",
                ]
            },
        ),
        (
            _("شبکه‌های اجتماعی"),
            {"fields": ["biography", "telegram", "github", "linkdin", "web_site"]},
        ),
        (_("دسترسی‌ها"), {"fields": ["is_active", "is_admin"]}),
    ]
    add_fieldsets = [
        (
            None,
            {
                "classes": ["wide"],
                "fields": [
                    "fullname",
                    "phone",
                    "email",
                    "password1",
                    "password2",
                    "is_active",
                    "is_admin",
                ],
            },
        ),
    ]

    @admin.display(boolean=True, description=_("رمز دارد"))
    def password_status_display(self, obj):
        return obj.has_usable_password()

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "download-phone-backup/",
                self.admin_site.admin_view(self.download_phone_backup),
                name="account_user_phone_backup",
            ),
        ]
        return custom_urls + urls

    def download_phone_backup(self, request):
        timestamp = timezone.localtime(timezone.now())
        filename = f"user-phone-backup-{timestamp:%Y%m%d-%H%M%S}.txt"
        phone_numbers = list(
            User.objects.order_by("fullname").values_list("phone", flat=True)
        )
        lines = [
            f"generated_at: {timestamp:%Y-%m-%d %H:%M:%S %Z}",
            f"total_numbers: {len(phone_numbers)}",
            "",
        ]
        lines.extend(phone_numbers)

        response = HttpResponse("\n".join(lines), content_type="text/plain; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


admin.site.register(User, UserAdmin)
admin.site.unregister(Group)


@admin.register(Otp)
class OtpAdmin(admin.ModelAdmin):
    list_display = ("phone", "code", "created_at", "exprision_date")
    search_fields = ("phone", "token")
    readonly_fields = ("token", "phone", "code", "exprision_date", "created_at")
    ordering = ("-created_at",)


class UserSessionAdmin(admin.ModelAdmin):
    list_display = ("user", "ip_address", "user_agent", "created_at")
    list_select_related = ("user",)
    search_fields = ("user__fullname", "ip_address")
    ordering = ("-created_at",)


admin.site.register(UserSession, UserSessionAdmin)


@admin.register(BodyCircumferenceMeasurement)
class BodyCircumferenceMeasurementAdmin(admin.ModelAdmin):
    list_display = ("user", "recorded_at", "height_snapshot", "weight_snapshot")
    list_select_related = ("user",)
    search_fields = ("user__fullname", "user__phone")
    ordering = ("-recorded_at",)

    @admin.display(description=_("قد"))
    def height_snapshot(self, obj):
        return obj.user.height_cm or "-"

    @admin.display(description=_("وزن"))
    def weight_snapshot(self, obj):
        return obj.user.weight_kg or "-"


@admin.register(CaliperMeasurement)
class CaliperMeasurementAdmin(admin.ModelAdmin):
    list_display = ("user", "recorded_at", "abdominal_mm", "triceps_mm", "thigh_mm")
    list_select_related = ("user",)
    search_fields = ("user__fullname", "user__phone")
    ordering = ("-recorded_at",)


@admin.register(ClientMedia)
class ClientMediaAdmin(admin.ModelAdmin):
    list_display = ("user", "uploaded_by", "uploaded_at", "image", "video")
    list_select_related = ("user", "uploaded_by")
    search_fields = ("user__fullname", "user__phone", "uploaded_by__fullname")
    ordering = ("-uploaded_at",)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if not change:
            NotificationService.schedule_media_uploaded(obj)


class NotificationAdminForm(forms.ModelForm):
    class Meta:
        model = Notification
        fields = "__all__"

    def clean(self):
        cleaned_data = super().clean()
        send_sms_to_all = cleaned_data.get("send_sms_to_all")
        is_global = cleaned_data.get("is_global")
        user = cleaned_data.get("user")

        if send_sms_to_all and not is_global:
            self.add_error("send_sms_to_all", _("ارسال پیامک گروهی فقط برای اعلان عمومی مجاز است."))
        if is_global and user is not None:
            self.add_error("user", _("برای اعلان عمومی نباید کاربر مشخص انتخاب شود."))
        return cleaned_data


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    form = NotificationAdminForm
    list_display = ("title", "user", "is_global", "send_sms_to_all", "sms_status", "sms_recipients_count", "created_at", "read")
    list_select_related = ("user",)
    list_filter = ("is_global", "send_sms_to_all", "sms_status", "read", "created_at")
    search_fields = ("title", "message")
    readonly_fields = ("sms_status", "sms_sent_at", "sms_recipients_count", "sms_error", "created_at")
    ordering = ("-created_at",)

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "title",
                    "message",
                    "user",
                    "is_global",
                    "read",
                )
            },
        ),
        (
            _("ارسال پیامک"),
            {
                "fields": (
                    "send_sms_to_all",
                    "sms_status",
                    "sms_recipients_count",
                    "sms_sent_at",
                    "sms_error",
                )
            },
        ),
    )

    def save_model(self, request, obj, form, change):
        if obj.is_global:
            obj.user = None
        if obj.send_sms_to_all and obj.sms_status == Notification.SmsStatus.NOT_REQUESTED:
            obj.sms_status = Notification.SmsStatus.PENDING
        super().save_model(request, obj, form, change)

        if obj.is_global:
            cache.delete(f"{GLOBAL_NOTIFICATION_CACHE_KEY}:20")

        should_send_sms = obj.is_global and obj.send_sms_to_all and obj.sms_status in {
            Notification.SmsStatus.PENDING,
            Notification.SmsStatus.FAILED,
        }
        if not should_send_sms:
            return

        def _send_sms():
            try:
                dispatch_task(send_notification_sms_broadcast_task, obj.pk)
            except Exception as exc:
                self.message_user(
                    request,
                    _("اعلان ذخیره شد اما ارسال پیامک با خطا مواجه شد: %(error)s") % {"error": exc},
                    level=messages.ERROR,
                )
                return
            self.message_user(
                request,
                _("اعلان ذخیره شد و ارسال پیامک در صف قرار گرفت."),
                level=messages.SUCCESS,
            )

        transaction.on_commit(_send_sms)


@admin.register(ClientDocument)
class ClientDocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "uploaded_by", "uploaded_at", "requires_payment", "price")
    list_select_related = ("user", "uploaded_by")
    search_fields = ("title", "user__fullname", "user__phone")
    ordering = ("-uploaded_at",)
    list_filter = ("requires_payment",)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if not change:
            NotificationService.schedule_document_uploaded(obj)


@admin.register(CoachRequest)
class CoachRequestAdmin(admin.ModelAdmin):
    list_display = ("user", "sessions_per_week", "wants_diet", "wants_workout", "status", "created_at")
    list_select_related = ("user",)
    list_filter = ("status", "wants_diet", "wants_workout")
    search_fields = ("user__fullname", "user__phone")
    ordering = ("-created_at",)


class WorkoutProgramDayInline(admin.TabularInline):
    model = WorkoutProgramDay
    extra = 0
    fields = ("order", "name", "notes")
    ordering = ("order",)


class WorkoutProgramCorrectiveInline(admin.TabularInline):
    model = WorkoutProgramCorrective
    extra = 0
    fields = ("order", "phase", "corrective_exercise", "sets", "reps", "note")
    ordering = ("phase", "order")


class WorkoutProgramFeedbackInline(admin.StackedInline):
    model = WorkoutProgramFeedback
    extra = 0
    fields = ("day", "difficulty", "submitted_at")
    readonly_fields = ("submitted_at",)


@admin.register(WorkoutProgram)
class WorkoutProgramAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "user",
        "prescribed_by",
        "start_date",
        "end_date",
        "is_published",
        "requires_payment",
        "price",
        "difficulty_score",
        "updated_at",
    )
    list_select_related = ("user", "prescribed_by")
    list_filter = ("is_published", "requires_payment", "start_date", "end_date")
    search_fields = ("title", "user__fullname", "user__phone", "prescribed_by__fullname")
    ordering = ("-updated_at",)
    inlines = (WorkoutProgramDayInline, WorkoutProgramCorrectiveInline, WorkoutProgramFeedbackInline)

    def save_model(self, request, obj, form, change):
        was_published = False
        if change and obj.pk:
            was_published = bool(
                WorkoutProgram.objects.filter(pk=obj.pk).values_list("is_published", flat=True).first()
            )
        super().save_model(request, obj, form, change)
        if obj.is_published and (not change or not was_published):
            NotificationService.schedule_program_registered(obj)

    @admin.display(description=_("دشواری برنامه"))
    def difficulty_score(self, obj):
        feedback = obj.difficulty_feedback.order_by("-submitted_at").first()
        return f"{feedback.difficulty}/10" if feedback and feedback.difficulty is not None else "—"


@admin.register(WorkoutProgramPayment)
class WorkoutProgramPaymentAdmin(admin.ModelAdmin):
    list_display = ("program", "user", "amount", "status", "authority", "created_at", "paid_at")
    list_select_related = ("program", "user")
    list_filter = ("status", "created_at", "paid_at")
    search_fields = ("program__title", "user__fullname", "user__phone", "authority", "ref_id")
    readonly_fields = ("created_at", "paid_at", "authority", "ref_id")
    ordering = ("-created_at",)


@admin.register(WorkoutProgramDay)
class WorkoutProgramDayAdmin(admin.ModelAdmin):
    list_display = ("name", "program", "order")
    list_select_related = ("program",)
    search_fields = ("name", "program__title", "program__user__fullname")
    ordering = ("program", "order")


@admin.register(WorkoutProgramExercise)
class WorkoutProgramExerciseAdmin(admin.ModelAdmin):
    list_display = ("exercise", "superset_exercise", "third_exercise", "day", "sets", "reps", "rest", "order")
    list_select_related = ("day", "day__program", "exercise", "superset_exercise", "third_exercise")
    search_fields = (
        "exercise__name",
        "superset_exercise__name",
        "third_exercise__name",
        "day__program__title",
        "day__program__user__fullname",
    )
    ordering = ("day", "order")


@admin.register(WorkoutProgramCorrective)
class WorkoutProgramCorrectiveAdmin(admin.ModelAdmin):
    list_display = ("corrective_exercise", "program", "phase", "sets", "reps", "order")
    list_select_related = ("program", "corrective_exercise")
    list_filter = ("phase",)
    search_fields = ("corrective_exercise__name", "program__title", "program__user__fullname")
    ordering = ("program", "phase", "order")


@admin.register(WorkoutPerformanceRecord)
class WorkoutPerformanceRecordAdmin(admin.ModelAdmin):
    list_display = (
        "exercise",
        "user",
        "repetitions",
        "mode",
        "set_number",
        "value",
        "updated_at",
    )
    list_select_related = ("user", "exercise", "program")
    list_filter = ("mode", "updated_at")
    search_fields = (
        "exercise__name",
        "user__fullname",
        "user__phone",
        "program__title",
    )
    ordering = ("-updated_at",)


@admin.register(Muscle)
class MuscleAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(Exercise)
class ExerciseAdmin(admin.ModelAdmin):
    list_display = ("name", "primary_muscle", "body_part", "difficulty_level")
    list_select_related = ("primary_muscle", "secondary_muscle", "body_part", "movement_type", "joint_type", "power_type", "difficulty_level", "equipment_type")
    list_filter = ("body_part", "movement_type", "difficulty_level", "equipment_type")
    search_fields = ("name", "primary_muscle__name")
    ordering = ("name",)


@admin.register(CorrectiveExercise)
class CorrectiveExerciseAdmin(admin.ModelAdmin):
    form = CorrectiveExerciseForm
    list_display = ("name", "abnormality_type", "equipment", "media", "video_count")
    list_select_related = ("abnormality_type", "equipment")
    list_filter = ("abnormality_type", "equipment")
    search_fields = ("name", "description", "abnormality_type__name", "equipment__name")
    ordering = ("name",)

    @admin.display(description=_("تعداد ویدیو"))
    def video_count(self, obj):
        return len(obj.video_files)


class _LookupModelAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)
    ordering = ("name",)


admin.site.register(ExerciseBodyPart, _LookupModelAdmin)
admin.site.register(ExerciseMovementType, _LookupModelAdmin)
admin.site.register(ExerciseJointType, _LookupModelAdmin)
admin.site.register(ExercisePowerType, _LookupModelAdmin)
admin.site.register(ExerciseDifficultyLevel, _LookupModelAdmin)
admin.site.register(ExerciseEquipmentType, _LookupModelAdmin)
