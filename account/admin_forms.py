from django import forms
from django.utils.translation import gettext_lazy as _

from account.froms import INPUT_CLASS
from account.models import (
    BodyCircumferenceMeasurement,
    CaliperMeasurement,
    ClientDocument,
    ClientMedia,
    CorrectiveExercise,
    Exercise,
    ExerciseSecondaryMovementType,
    Muscle,
    User,
    WorkoutProgram,
    ExerciseAbnormalityType,
    ExerciseDifficultyLevel,
)
from account.utils import calculate_age_from_jalali, combine_fullname, normalize_phone_number
from account.validators import validate_image_upload, validate_media_upload, validate_pdf_upload, validate_video_upload


class AdminUserSearchForm(forms.Form):
    query = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": INPUT_CLASS,
                "placeholder": _("نام یا شماره همراه کاربر را وارد کنید"),
            }
        ),
    )


class AdminCommentModerationForm(forms.Form):
    action = forms.ChoiceField(
        choices=(
            ("approve", _("تایید و انتشار")),
            ("reject", _("رد و عدم انتشار")),
            ("respond", _("ثبت پاسخ")),
        ),
        widget=forms.HiddenInput,
    )
    response = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": INPUT_CLASS,
                "rows": 3,
                "placeholder": _("پاسخ مدیر (اختیاری)") ,
            }
        ),
    )

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("action") == "respond" and not (cleaned_data.get("response") or "").strip():
            self.add_error("response", _("برای ثبت پاسخ، متن پاسخ را وارد کنید."))
        return cleaned_data


class AdminPersonalInfoForm(forms.ModelForm):
    class Meta:
        model = User
        fields = (
            "first_name",
            "last_name",
            "display_name",
            "phone",
            "blood_group",
            "gender",
            "birth_date_jalali",
            "activity_level",
            "coach",
        )
        widgets = {
            "first_name": forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": _("نام")}),
            "last_name": forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": _("نام خانوادگی")}),
            "display_name": forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": _("نام کاربری")}),
            "phone": forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": _("شماره تماس"), "dir": "ltr"}),
            "blood_group": forms.Select(attrs={"class": INPUT_CLASS}),
            "gender": forms.Select(attrs={"class": INPUT_CLASS}),
            "birth_date_jalali": forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": _("تاریخ تولد (فرمت: سال/ماه/روز)")}),
            "activity_level": forms.Select(attrs={"class": INPUT_CLASS}),
            "coach": forms.Select(attrs={"class": INPUT_CLASS}),
        }
        labels = {
            "display_name": _("نام کاربری"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["coach"].queryset = User.objects.filter(is_admin=True)
        self.fields["coach"].required = False
        self.fields["coach"].empty_label = _("بدون مربی")

    def clean(self):
        cleaned_data = super().clean()
        first_name = cleaned_data.get("first_name", "")
        last_name = cleaned_data.get("last_name", "")
        combined = combine_fullname(first_name, last_name)
        if combined and User.objects.filter(fullname=combined).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(_("این نام و نام خانوادگی قبلاً ثبت شده است."))
        cleaned_data["fullname"] = combined
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.cleaned_data.get("fullname"):
            instance.fullname = self.cleaned_data["fullname"]
        instance.age = calculate_age_from_jalali(self.cleaned_data.get("birth_date_jalali"))
        if commit:
            instance.save()
        return instance


class AdminUserCreateForm(forms.ModelForm):
    password = forms.CharField(
        label=_("رمز عبور (برای ورود به اپ)"),
        widget=forms.TextInput(attrs={"class": INPUT_CLASS, "dir": "ltr"}),
        help_text=_("برای ورود کاربر به اپ استفاده می‌شود"),
    )

    class Meta:
        model = User
        fields = ("first_name", "last_name", "phone", "blood_group", "gender", "birth_date_jalali", "activity_level", "coach")
        widgets = {
            "first_name": forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": _("نام")}),
            "last_name": forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": _("نام خانوادگی")}),
            "phone": forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": _("شماره تماس"), "dir": "ltr"}),
            "blood_group": forms.Select(attrs={"class": INPUT_CLASS}),
            "gender": forms.Select(attrs={"class": INPUT_CLASS}),
            "birth_date_jalali": forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": _("تاریخ تولد (فرمت: سال/ماه/روز)")}),
            "activity_level": forms.Select(attrs={"class": INPUT_CLASS}),
            "coach": forms.Select(attrs={"class": INPUT_CLASS}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["coach"].queryset = User.objects.filter(is_admin=True)
        self.fields["coach"].required = False
        self.fields["coach"].empty_label = _("بدون مربی")

    def clean_phone(self):
        normalized = normalize_phone_number(self.cleaned_data["phone"])
        if len(normalized) != 11 or not normalized.isdigit():
            raise forms.ValidationError(_("شماره تماس معتبر نیست."))
        return normalized

    def clean(self):
        cleaned_data = super().clean()
        combined = combine_fullname(cleaned_data.get("first_name", ""), cleaned_data.get("last_name", ""))
        if combined and User.objects.filter(fullname=combined).exists():
            raise forms.ValidationError(_("این نام و نام خانوادگی قبلاً ثبت شده است."))
        cleaned_data["fullname"] = combined
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.fullname = self.cleaned_data["fullname"]
        instance.age = calculate_age_from_jalali(self.cleaned_data.get("birth_date_jalali"))
        if commit:
            instance.save()
        return instance


class AdminCircumferenceForm(forms.ModelForm):
    class Meta:
        model = BodyCircumferenceMeasurement
        exclude = ("user", "recorded_at")
        widgets = {
            "measured_at_jalali": forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": _("تاریخ ثبت (فرمت: سال/ماه/روز)")}),
            **{field: forms.NumberInput(attrs={"class": INPUT_CLASS, "step": "0.1", "dir": "ltr", "data-select-all-on-focus": "true"}) for field in (
                "height_cm",
                "weight_kg",
                "wrist_cm",
                "forearm_cm",
                "arm_rest_cm",
                "arm_flexed_cm",
                "wrist_left_cm",
                "forearm_left_cm",
                "arm_rest_left_cm",
                "arm_flexed_left_cm",
                "head_cm",
                "neck_cm",
                "chest_cm",
                "shoulders_cm",
                "waist_cm",
                "abdomen_cm",
                "hips_cm",
                "thigh_cm",
                "calf_cm",
                "thigh_left_cm",
                "calf_left_cm",
                "sit_height_cm",
                "leg_length_cm",
                "shoulder_width_cm",
                "hip_width_cm",
                "elbow_width_cm",
                "knee_width_cm",
                "arm_length_cm",
            )},
        }


class AdminCaliperForm(forms.ModelForm):
    class Meta:
        model = CaliperMeasurement
        exclude = ("user", "recorded_at")
        widgets = {
            "measured_at_jalali": forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": _("تاریخ ثبت (فرمت: سال/ماه/روز)")}),
            **{field: forms.NumberInput(attrs={"class": INPUT_CLASS, "step": "0.1", "dir": "ltr", "data-select-all-on-focus": "true"}) for field in (
                "chest_armpit_men_mm",
                "axilla_mm",
                "subscapular_mm",
                "abdominal_mm",
                "suprailiac_mm",
                "chest_mm",
                "biceps_mm",
                "triceps_mm",
                "thigh_mm",
                "calf_mm",
            )},
        }


class AdminClientMediaForm(forms.ModelForm):
    class Meta:
        model = ClientMedia
        fields = ("image", "video")
        widgets = {
            "image": forms.ClearableFileInput(attrs={"class": INPUT_CLASS}),
            "video": forms.ClearableFileInput(attrs={"class": INPUT_CLASS}),
        }

    def clean_image(self):
        return validate_image_upload(self.cleaned_data.get("image"))

    def clean_video(self):
        return validate_video_upload(self.cleaned_data.get("video"))


class AdminClientDocumentForm(forms.ModelForm):
    access_type = forms.MultipleChoiceField(
        choices=(("paid", _("پرداخت شده — دانلود بدون هزینه")), ("unpaid", _("پرداخت نشده — نیازمند پرداخت"))),
        required=False,
        label=_("نوع دسترسی"),
        widget=forms.CheckboxSelectMultiple(attrs={"class": "admin-access-checkboxes"}),
    )
    class Meta:
        model = ClientDocument
        fields = ("title", "file", "price")
        widgets = {
            "title": forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": _("مثلاً: برنامه تمرینی هفته ۱")}),
            "file": forms.ClearableFileInput(attrs={"class": INPUT_CLASS}),
            "price": forms.NumberInput(attrs={"class": INPUT_CLASS, "min": 0, "step": 1, "inputmode": "numeric", "dir": "ltr"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["price"].required = False
        if self.instance and self.instance.pk:
            self.fields["access_type"].initial = ["paid" if self.instance.requires_payment else "unpaid"]
        else:
            self.fields["access_type"].initial = ["paid"]

    def clean_file(self):
        return validate_pdf_upload(self.cleaned_data.get("file"))

    def clean(self):
        cleaned = super().clean()
        # Preserve the legacy upload behavior when older clients submit without
        # the new access selector: those files were free to download.
        access_types = cleaned.get("access_type") or ["paid"]
        if len(access_types) != 1:
            self.add_error("access_type", _("فقط یکی از گزینه‌های پرداختی یا رایگان را انتخاب کنید."))
        cleaned["access_type"] = access_types
        if access_types == ["unpaid"] and not cleaned.get("price"):
            self.add_error("price", _("برای فایل پولی مبلغ را وارد کنید."))
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.requires_payment = "unpaid" in self.cleaned_data.get("access_type", [])
        if not instance.requires_payment:
            instance.price = 0
        if commit:
            instance.save()
        return instance


class AdminRoleToggleForm(forms.Form):
    is_admin = forms.BooleanField(required=False, label=_("نقش ادمین"))


class AdminBulkCoachAssignForm(forms.Form):
    coach = forms.ModelChoiceField(
        queryset=User.objects.filter(is_admin=True).order_by("fullname"),
        required=True,
        label=_("مربی"),
        widget=forms.Select(attrs={"class": INPUT_CLASS}),
    )


class AdminUserCoachForm(forms.Form):
    coach = forms.ModelChoiceField(
        queryset=User.objects.filter(is_admin=True).order_by("fullname"),
        required=False,
        label=_("مربی"),
        empty_label=_("بدون مربی"),
        widget=forms.Select(attrs={"class": INPUT_CLASS}),
    )


class LibrarySearchForm(forms.Form):
    query = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": INPUT_CLASS,
                "placeholder": _("نام را وارد کنید"),
            }
        ),
    )


class MuscleForm(forms.ModelForm):
    class Meta:
        model = Muscle
        fields = ("name", "name_en", "origin", "insertion", "nerve", "function_note", "image")
        widgets = {
            "name": forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": _("نام عضله")}),
            "name_en": forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": _("نام انگلیسی عضله"), "dir": "ltr"}),
            "origin": forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 2}),
            "insertion": forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 2}),
            "nerve": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "function_note": forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 2}),
            "image": forms.ClearableFileInput(attrs={"class": INPUT_CLASS}),
        }

    def clean_image(self):
        return validate_image_upload(self.cleaned_data.get("image"))


def build_lookup_form(model, *, fields=("name", "name_en"), data=None, instance=None):
    widgets = {
        field: forms.TextInput(attrs={"class": INPUT_CLASS, **({"dir": "ltr"} if field.endswith("_en") else {})})
        for field in fields
    }
    form_class = forms.modelform_factory(model, fields=fields, widgets=widgets)
    return form_class(data, instance=instance)


class ExerciseForm(forms.ModelForm):
    class Meta:
        model = Exercise
        fields = (
            "name",
            "name_en",
            "primary_muscle",
            "secondary_muscle",
            "body_part",
            "movement_type",
            "joint_type",
            "power_type",
            "difficulty_level",
            "equipment_type",
            "execution_equipment_type",
            "secondary_movement_type",
            "pressure_type",
            "description",
            "media",
            "video_1",
            "video_2",
            "video_3",
        )
        widgets = {
            "name": forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": _("نام حرکت")}),
            "name_en": forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": _("نام انگلیسی حرکت"), "dir": "ltr"}),
            "primary_muscle": forms.Select(attrs={"class": INPUT_CLASS}),
            "secondary_muscle": forms.Select(attrs={"class": INPUT_CLASS}),
            "body_part": forms.Select(attrs={"class": INPUT_CLASS}),
            "movement_type": forms.Select(attrs={"class": INPUT_CLASS}),
            "joint_type": forms.Select(attrs={"class": INPUT_CLASS}),
            "power_type": forms.Select(attrs={"class": INPUT_CLASS}),
            "difficulty_level": forms.Select(attrs={"class": INPUT_CLASS}),
            "equipment_type": forms.Select(attrs={"class": INPUT_CLASS}),
            "execution_equipment_type": forms.Select(attrs={"class": INPUT_CLASS}),
            "secondary_movement_type": forms.Select(attrs={"class": INPUT_CLASS}),
            "pressure_type": forms.Select(attrs={"class": INPUT_CLASS}),
            "description": forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 3, "placeholder": _("توضیحات حرکت")}),
            "media": forms.ClearableFileInput(
                attrs={"class": INPUT_CLASS, "accept": "image/*,video/*"}
            ),
            "video_1": forms.ClearableFileInput(
                attrs={"class": INPUT_CLASS, "accept": "video/*"}
            ),
            "video_2": forms.ClearableFileInput(
                attrs={"class": INPUT_CLASS, "accept": "video/*"}
            ),
            "video_3": forms.ClearableFileInput(
                attrs={"class": INPUT_CLASS, "accept": "video/*"}
            ),
        }
        labels = {
            "media": _("تصویر یا ویدیوی قدیمی"),
            "video_1": _("ویدیوی ۱"),
            "video_2": _("ویدیوی ۲"),
            "video_3": _("ویدیوی ۳"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["secondary_muscle"].required = False
        self.fields["secondary_muscle"].empty_label = _("بدون عضله فرعی")
        self.fields["pressure_type"].required = False
        self.fields["pressure_type"].empty_label = _("نامشخص")
        self.fields["execution_equipment_type"].required = False
        self.fields["execution_equipment_type"].empty_label = _("نامشخص")
        self.fields["secondary_movement_type"].required = False
        self.fields["secondary_movement_type"].empty_label = _("نامشخص")

    def clean_media(self):
        return validate_media_upload(self.cleaned_data.get("media"))

    def clean_video_1(self):
        return validate_video_upload(self.cleaned_data.get("video_1"))

    def clean_video_2(self):
        return validate_video_upload(self.cleaned_data.get("video_2"))

    def clean_video_3(self):
        return validate_video_upload(self.cleaned_data.get("video_3"))


class CorrectiveExerciseForm(forms.ModelForm):
    class Meta:
        model = CorrectiveExercise
        fields = (
            "name",
            "equipment",
            "abnormality_type",
            "description",
            "media",
            "video_1",
            "video_2",
            "video_3",
        )
        widgets = {
            "name": forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": _("نام حرکت")}),
            "equipment": forms.Select(attrs={"class": INPUT_CLASS}),
            "abnormality_type": forms.Select(attrs={"class": INPUT_CLASS}),
            "description": forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 3, "placeholder": _("توضیحات")}),
            "media": forms.ClearableFileInput(
                attrs={"class": INPUT_CLASS, "accept": "image/*,video/*"}
            ),
            "video_1": forms.ClearableFileInput(
                attrs={"class": INPUT_CLASS, "accept": "video/*"}
            ),
            "video_2": forms.ClearableFileInput(
                attrs={"class": INPUT_CLASS, "accept": "video/*"}
            ),
            "video_3": forms.ClearableFileInput(
                attrs={"class": INPUT_CLASS, "accept": "video/*"}
            ),
        }
        labels = {
            "media": _("تصویر یا ویدیوی قدیمی"),
            "video_1": _("ویدیوی ۱"),
            "video_2": _("ویدیوی ۲"),
            "video_3": _("ویدیوی ۳"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["equipment"].required = False
        self.fields["equipment"].empty_label = _("نامشخص")
        self.fields["abnormality_type"].required = False
        self.fields["abnormality_type"].empty_label = _("نامشخص")

    def clean_media(self):
        return validate_media_upload(self.cleaned_data.get("media"))

    def clean_video_1(self):
        return validate_video_upload(self.cleaned_data.get("video_1"))

    def clean_video_2(self):
        return validate_video_upload(self.cleaned_data.get("video_2"))

    def clean_video_3(self):
        return validate_video_upload(self.cleaned_data.get("video_3"))


class WorkoutProgramForm(forms.ModelForm):
    class Meta:
        model = WorkoutProgram
        fields = (
            "title",
            "start_date",
            "end_date",
            "is_published",
            "requires_payment",
            "price",
            "notes",
            "supplements_note",
            "warmup_notes",
            "cooldown_notes",
        )
        widgets = {
            "title": forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": _("مثلاً: برنامه حجم ماه اول")}),
            "start_date": forms.DateInput(attrs={"class": INPUT_CLASS, "type": "date", "dir": "ltr"}),
            "end_date": forms.DateInput(attrs={"class": INPUT_CLASS, "type": "date", "dir": "ltr"}),
            "is_published": forms.CheckboxInput(attrs={"class": "admin-checkbox"}),
            "requires_payment": forms.CheckboxInput(attrs={"class": "admin-checkbox"}),
            "price": forms.NumberInput(
                attrs={"class": INPUT_CLASS, "min": 0, "step": 1, "inputmode": "numeric", "dir": "ltr"}
            ),
            "notes": forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 3, "placeholder": _("توضیحات کلی برنامه")}),
            "supplements_note": forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 3, "placeholder": _("مکمل و نکات تغذیه‌ای")}),
            "warmup_notes": forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 3, "placeholder": _("توضیحات گرم کردن")}),
            "cooldown_notes": forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 3, "placeholder": _("توضیحات سرد کردن")}),
        }

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("requires_payment") and not cleaned.get("price"):
            self.add_error("price", _("برای برنامه پولی مبلغ را وارد کنید."))
        if not cleaned.get("requires_payment"):
            cleaned["price"] = 0
        return cleaned

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["price"].required = False


class WorkoutProgramPayloadForm(forms.Form):
    days_json = forms.JSONField(
        required=True,
        widget=forms.HiddenInput(),
        label=_("روزهای برنامه"),
    )
    correctives_json = forms.JSONField(
        required=False,
        initial=[],
        widget=forms.HiddenInput(),
        label=_("حرکت‌های اصلاحی"),
    )

    def clean_days_json(self):
        value = self.cleaned_data["days_json"]
        if not isinstance(value, list):
            raise forms.ValidationError(_("ساختار روزهای برنامه معتبر نیست."))
        return value


class AutomaticProgrammingForm(forms.Form):
    """Inputs used by the automatic workout designer."""

    GOAL_CHOICES = (
        ("strength", _("قدرت")),
        ("volume", _("حجم عضلانی")),
        ("endurance", _("استقامت")),
        ("fat_burning", _("چربی‌سوزی")),
        ("power", _("توان انفجاری")),
        ("general", _("تناسب عمومی")),
    )

    user = forms.ModelChoiceField(
        queryset=User.objects.filter(is_admin=False).order_by("fullname"),
        label=_("ورزشکار"),
        widget=forms.Select(attrs={"class": INPUT_CLASS}),
    )
    difficulty = forms.ModelChoiceField(
        queryset=ExerciseDifficultyLevel.objects.all(),
        label=_("سطح دشواری"),
        widget=forms.Select(attrs={"class": INPUT_CLASS}),
    )
    gender = forms.ChoiceField(
        choices=(("", _("همه جنسیت‌ها")),) + tuple(User.GenderChoices.choices),
        required=False,
        label=_("جنسیت"),
        widget=forms.Select(attrs={"class": INPUT_CLASS}),
    )
    abnormalities = forms.ModelMultipleChoiceField(
        queryset=ExerciseAbnormalityType.objects.all(),
        required=False,
        label=_("ناهنجاری‌های اسکلتی"),
        widget=forms.SelectMultiple(attrs={"class": INPUT_CLASS, "size": 5}),
    )
    sessions_per_week = forms.IntegerField(
        min_value=1, max_value=7, initial=3, label=_("جلسه در هفته"),
        widget=forms.NumberInput(attrs={"class": INPUT_CLASS, "min": 1, "max": 7, "dir": "ltr"}),
    )
    movements_per_session = forms.IntegerField(
        min_value=1, max_value=50, initial=6, label=_("حرکت در هر جلسه"),
        widget=forms.NumberInput(attrs={"class": INPUT_CLASS, "min": 1, "max": 50, "dir": "ltr"}),
    )
    goal = forms.ChoiceField(
        choices=GOAL_CHOICES, initial="general", label=_("هدف برنامه"),
        widget=forms.Select(attrs={"class": INPUT_CLASS}),
    )
    target_secondary_movement_types = forms.ModelMultipleChoiceField(
        queryset=ExerciseSecondaryMovementType.objects.all(),
        required=True,
        label=_("انواع حرکت دوم هدف"),
        widget=forms.SelectMultiple(
            attrs={"class": INPUT_CLASS, "size": 7, "data-secondary-movement-picker": "true"}
        ),
    )
    secondary_movement_counts_json = forms.JSONField(
        required=False, initial={}, widget=forms.HiddenInput()
    )
    session_movement_targets_json = forms.JSONField(
        required=False, initial=[], widget=forms.HiddenInput()
    )
    title = forms.CharField(
        max_length=150, initial=_("برنامه خودکار بدنسازی"),
        label=_("عنوان برنامه"),
        widget=forms.TextInput(attrs={"class": INPUT_CLASS}),
    )
    is_published = forms.BooleanField(
        required=False, initial=True, label=_("نمایش برای کاربر"),
        widget=forms.CheckboxInput(attrs={"class": "admin-checkbox"}),
    )
    requires_payment = forms.BooleanField(
        required=False,
        label=_("نیازمند پرداخت"),
        widget=forms.CheckboxInput(attrs={"class": "admin-checkbox", "data-payment-toggle": "true"}),
    )
    price = forms.IntegerField(
        required=False,
        min_value=0,
        label=_("هزینه برنامه (تومان)"),
        widget=forms.NumberInput(
            attrs={"class": INPUT_CLASS, "min": 0, "step": 1, "inputmode": "numeric", "dir": "ltr", "data-payment-price": "true"}
        ),
    )

    def clean_secondary_movement_counts_json(self):
        value = self.cleaned_data.get("secondary_movement_counts_json") or {}
        if not isinstance(value, dict):
            raise forms.ValidationError(_("تنظیمات تعداد حرکت انواع حرکت دوم معتبر نیست."))
        cleaned = {}
        for movement_type_id, count in value.items():
            try:
                movement_type_id = str(int(movement_type_id))
                count = int(count)
            except (TypeError, ValueError):
                raise forms.ValidationError(_("شناسه یا تعداد حرکت معتبر نیست."))
            if int(movement_type_id) <= 0 or count < 0 or count > 20:
                raise forms.ValidationError(_("تعداد حرکت باید بین صفر و بیست باشد."))
            cleaned[movement_type_id] = count
        return cleaned

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("requires_payment") and not cleaned.get("price"):
            self.add_error("price", _("برای برنامه پولی مبلغ را وارد کنید."))
        if not cleaned.get("requires_payment"):
            cleaned["price"] = 0
        return cleaned

    def clean_session_movement_targets_json(self):
        value = self.cleaned_data.get("session_movement_targets_json") or []
        if not isinstance(value, list):
            raise forms.ValidationError(_("تنظیمات عضلات هر جلسه معتبر نیست."))
        sessions = self.cleaned_data.get("sessions_per_week") or 0
        if len(value) > sessions:
            raise forms.ValidationError(_("تعداد تنظیمات جلسه‌ها بیشتر از تعداد جلسه‌های هفته است."))
        selected_ids = {
            str(item.pk)
            for item in self.cleaned_data.get("target_secondary_movement_types", [])
        }
        cleaned = []
        for session in value:
            if not isinstance(session, dict):
                raise forms.ValidationError(_("ساختار تنظیمات عضلات هر جلسه معتبر نیست."))
            movement_types = session.get("movement_types", [])
            counts = session.get("counts", {}) or {}
            if not isinstance(movement_types, list) or not isinstance(counts, dict):
                raise forms.ValidationError(_("ساختار هدف‌های هر جلسه معتبر نیست."))
            normalized_types = []
            normalized_counts = {}
            for movement_type_id in movement_types:
                try:
                    movement_type_id = str(int(movement_type_id))
                except (TypeError, ValueError):
                    raise forms.ValidationError(_("نوع حرکت دوم انتخاب‌شده معتبر نیست."))
                if movement_type_id not in selected_ids:
                    raise forms.ValidationError(_("یکی از انواع حرکت دوم جلسه در فهرست هدف‌ها نیست."))
                if movement_type_id not in normalized_types:
                    normalized_types.append(movement_type_id)
                raw_count = counts.get(movement_type_id, counts.get(int(movement_type_id), 0))
                try:
                    count = int(raw_count)
                except (TypeError, ValueError):
                    raise forms.ValidationError(_("تعداد حرکت جلسه معتبر نیست."))
                if count < 0 or count > 20:
                    raise forms.ValidationError(_("تعداد حرکت جلسه باید بین صفر و بیست باشد."))
                normalized_counts[movement_type_id] = count
            cleaned.append(
                {
                    "movement_types": normalized_types,
                    "counts": normalized_counts,
                }
            )
        return cleaned

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["user"].label_from_instance = self._user_label

    @staticmethod
    def _user_label(user):
        name_parts = " ".join(
            value.strip()
            for value in (user.first_name or "", user.last_name or "")
            if value and value.strip()
        )
        name = name_parts or user.fullname or _("بدون نام")
        if name_parts and user.fullname and user.fullname != name_parts:
            name = f"{name} ({user.fullname})"
        return f"{name} — {user.phone}"

    def clean_correctives_json(self):
        value = self.cleaned_data.get("correctives_json") or []
        if not isinstance(value, list):
            raise forms.ValidationError(_("ساختار حرکت‌های اصلاحی معتبر نیست."))
        return value
