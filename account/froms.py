import re

from django import forms
from django.contrib.auth.forms import PasswordChangeForm
from django.core.exceptions import ValidationError
from django.core.validators import MinLengthValidator, RegexValidator
from django.utils.translation import gettext_lazy as _

from account.models import User
from account.utils import normalize_digits, normalize_phone_number
from account.validators import (
    AUDIO_UPLOAD_TYPES,
    IMAGE_UPLOAD_TYPES,
    VIDEO_UPLOAD_TYPES,
    validate_image_upload,
    validate_media_upload,
    validate_pdf_upload,
    validate_phone_number,
    validate_upload,
)
INPUT_CLASS = (
    "form-input enterprise-input w-full h-11 !ring-0 !ring-offset-0 bg-secondary "
    "border-border focus:border-border rounded-xl text-sm text-foreground px-5"
)


class OtpForm(forms.Form):
    phone = forms.CharField(
        widget=forms.TextInput(
            attrs={
                "class": INPUT_CLASS,
                "placeholder": _("شماره تلفن خود را وارد کنید"),
                "inputmode": "tel",
                "autocomplete": "tel",
                "dir": "ltr",
            }
        ),
    )

    def clean_phone(self):
        return validate_phone_number(self.cleaned_data.get("phone"))


class CheckOtp(forms.Form):
    code = forms.CharField(
        widget=forms.TextInput(
            attrs={
                "class": INPUT_CLASS,
                "placeholder": _("کد را وارد کنید"),
                "inputmode": "numeric",
                "autocomplete": "one-time-code",
                "dir": "ltr",
            }
        ),
    )

    def clean_code(self):
        code = normalize_digits(self.cleaned_data.get("code"))
        if not re.match(r"^\d{5}$", code or ""):
            raise ValidationError(_("لطفا کد 5 رقمی وارد کنید"))
        return code


class UserEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = (
            "first_name",
            "last_name",
            "fullname",
            "email",
            "biography",
            "web_site",
            "github",
            "linkdin",
            "telegram",
            "profile_picture",
        )
        labels = {
            "first_name": _("نام"),
            "last_name": _("نام خانوادگی"),
            "fullname": _("نام کاربری"),
        }
        widgets = {
            "first_name": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "last_name": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "email": forms.EmailInput(attrs={"class": INPUT_CLASS}),
            "fullname": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "biography": forms.Textarea(
                attrs={
                    "class": (
                        "form-textarea w-full min-h-[132px] !ring-0 !ring-offset-0 bg-secondary "
                        "border-border focus:border-border rounded-2xl text-sm text-foreground px-5 py-4"
                    )
                }
            ),
            "web_site": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "github": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "linkdin": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "telegram": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "profile_picture": forms.FileInput(attrs={"class": INPUT_CLASS}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].required = True
        self.fields["last_name"].required = True

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if not email:
            raise ValidationError(_("لطفا ایمیل خود را وارد کنید."))
        if User.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(_("این ایمیل قبلا توسط کاربر دیگری ثبت شده است."))
        return email

    def clean_fullname(self):
        fullname = (self.cleaned_data.get("fullname") or "").strip()
        if not fullname:
            raise ValidationError(_("لطفا نام کاربری را وارد کنید."))
        if User.objects.filter(fullname=fullname).exclude(pk=self.instance.pk).exists():
            raise ValidationError(_("این نام کاربری قبلا توسط کاربر دیگری انتخاب شده است."))
        return fullname

    def clean_profile_picture(self):
        return validate_image_upload(self.cleaned_data.get("profile_picture"))

    def save(self, commit=True):
        instance = super().save(commit=False)
        if "profile_picture" in self.changed_data and instance.pk:
            old_instance = User.objects.get(pk=instance.pk)
            if old_instance.profile_picture:
                try:
                    old_instance.profile_picture.storage.delete(old_instance.profile_picture.name)
                except Exception:
                    pass

        if commit:
            instance.save()
        return instance


class NumberEditForm(forms.Form):
    phone_number_new = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={"class": INPUT_CLASS, "inputmode": "tel", "autocomplete": "tel", "dir": "ltr"}),
        error_messages={
            "required": _("لطفا شماره تماس جدید را وارد کنید."),
            "invalid": _("فرمت شماره تماس نامعتبر است."),
        },
    )

    def clean_phone_number_new(self):
        phone_number = normalize_phone_number(self.cleaned_data.get("phone_number_new"))
        if not re.match(r"^\d{11}$", phone_number or ""):
            raise ValidationError(_("لطفا یک شماره تماس 11 رقمی وارد کنید."))
        if User.objects.filter(phone=phone_number).exists():
            raise ValidationError(_("این شماره تماس قبلا ثبت شده است."))
        return phone_number


class WeightForm(forms.Form):
    weight = forms.DecimalField(
        label=_("وزن"),
        min_value=20,
        max_value=400,
        decimal_places=1,
        widget=forms.NumberInput(
            attrs={
                "class": INPUT_CLASS,
                "placeholder": _("وزن خود را وارد کنید"),
                "inputmode": "decimal",
                "step": "0.1",
                "dir": "ltr",
                "data-select-all-on-focus": "true",
            }
        ),
    )


class HeightForm(forms.Form):
    height = forms.DecimalField(
        label=_("قد"),
        min_value=50,
        max_value=260,
        decimal_places=1,
        widget=forms.NumberInput(
            attrs={
                "class": INPUT_CLASS,
                "placeholder": _("قد خود را وارد کنید"),
                "inputmode": "decimal",
                "step": "0.1",
                "dir": "ltr",
                "data-select-all-on-focus": "true",
            }
        ),
    )


class BirthDateForm(forms.Form):
    birth_date = forms.CharField(
        label=_("تاریخ تولد"),
        max_length=10,
        widget=forms.TextInput(
            attrs={
                "class": INPUT_CLASS,
                "placeholder": "1368/05/23",
                "inputmode": "numeric",
                "dir": "ltr",
            }
        ),
    )

    def clean_birth_date(self):
        value = (self.cleaned_data.get("birth_date") or "").strip()
        if not re.match(r"^\d{4}/\d{2}/\d{2}$", value):
            raise ValidationError(_("لطفا تاریخ را با فرمت 1368/05/23 وارد کنید."))
        return value


class BloodGroupForm(forms.Form):
    blood_group = forms.ChoiceField(
        label=_("گروه خونی"),
        choices=User.BloodGroupChoices.choices,
        widget=forms.RadioSelect(
            attrs={
                "class": "blood-group-options",
            }
        ),
    )


COACH_REQUEST_MAX_BYTES = 15 * 1024 * 1024
COACH_REQUEST_ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png", "webp", "gif", "mp4", "webm", "mov", "m4v", "ogv", "mp3", "wav", "ogg", "m4a", "aac"}
COACH_REQUEST_ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
    "video/mp4",
    "video/webm",
    "video/quicktime",
    "video/x-m4v",
    "video/ogg",
    "audio/mpeg",
    "audio/mp3",
    "audio/wav",
    "audio/x-wav",
    "audio/ogg",
    "audio/mp4",
    "audio/x-m4a",
    "audio/aac",
}
COACH_REQUEST_EXTENSION_MIME_TYPES = {
    "pdf": {"application/pdf"},
    **{extension: {mime} for extension, mime in IMAGE_UPLOAD_TYPES.items()},
    **VIDEO_UPLOAD_TYPES,
    **AUDIO_UPLOAD_TYPES,
}


def validate_coach_request_file(uploaded_file):
    return validate_upload(
        uploaded_file,
        allowed_extensions=COACH_REQUEST_ALLOWED_EXTENSIONS,
        allowed_content_types=COACH_REQUEST_ALLOWED_MIME_TYPES,
        extension_content_types=COACH_REQUEST_EXTENSION_MIME_TYPES,
        max_bytes=COACH_REQUEST_MAX_BYTES,
        message=_("فقط فایل‌های تصویر، ویدیو، صدا یا PDF مجاز هستند."),
    )


class CoachRequestForm(forms.ModelForm):
    class Meta:
        from account.models import CoachRequest

        model = CoachRequest
        fields = (
            "sessions_per_week",
            "wants_diet",
            "wants_workout",
            "height_cm",
            "weight_kg",
            "wrist_cm",
            "forearm_cm",
            "arm_rest_cm",
            "arm_flexed_cm",
            "chest_cm",
            "shoulders_cm",
            "waist_cm",
            "abdomen_cm",
            "hips_cm",
            "thigh_cm",
            "calf_cm",
            "thigh_left_cm",
            "calf_left_cm",
            "pain_notes",
            "illness_notes",
            "diet_restrictions",
        )
        widgets = {
            "sessions_per_week": forms.Select(attrs={"class": INPUT_CLASS}),
            "wants_diet": forms.CheckboxInput(attrs={"class": "coach-request-checkbox"}),
            "wants_workout": forms.CheckboxInput(attrs={"class": "coach-request-checkbox"}),
            "pain_notes": forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 3, "placeholder": _("در صورت وجود درد یا آسیب، توضیح دهید")}),
            "illness_notes": forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 3, "placeholder": _("بیماری زمینه‌ای (اختیاری)")}),
            "diet_restrictions": forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 3, "placeholder": _("محدودیت‌های غذایی (اختیاری)")}),
        }

    # Fields the form makes mandatory (DB columns stay nullable so legacy rows are valid).
    REQUIRED_BODY_FIELDS = ("height_cm", "weight_kg", "wrist_cm", "waist_cm", "abdomen_cm", "hips_cm")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        measure_fields = (
            "wrist_cm", "forearm_cm", "arm_rest_cm", "arm_flexed_cm", "chest_cm",
            "shoulders_cm", "waist_cm", "abdomen_cm", "hips_cm", "thigh_cm", "calf_cm",
            "thigh_left_cm", "calf_left_cm",
        )
        for name in measure_fields:
            self.fields[name].widget = forms.NumberInput(
                attrs={
                    "class": INPUT_CLASS,
                    "inputmode": "decimal",
                    "dir": "ltr",
                    "step": "0.1",
                    "min": "0",
                    "data-select-all-on-focus": "true",
                }
            )
        for name in ("height_cm", "weight_kg"):
            self.fields[name].widget = forms.NumberInput(
                attrs={
                    "class": INPUT_CLASS,
                    "inputmode": "decimal",
                    "dir": "ltr",
                    "step": "0.1",
                    "min": "0",
                    "data-select-all-on-focus": "true",
                }
            )
        for name in self.REQUIRED_BODY_FIELDS:
            self.fields[name].required = True

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get("wants_diet") and not cleaned_data.get("wants_workout"):
            raise ValidationError(_("حداقل یکی از برنامه غذایی یا برنامه تمرینی را انتخاب کنید."))
        return cleaned_data


class PasswordResetRequestForm(forms.Form):
    phone = forms.CharField(
        label=_("شماره تماس"),
        max_length=11,
        widget=forms.TextInput(
            attrs={
                "class": INPUT_CLASS,
                "placeholder": _("شماره تماس ثبت‌شده در حساب"),
                "inputmode": "tel",
                "autocomplete": "tel",
                "dir": "ltr",
            }
        ),
    )

    def clean_phone(self):
        phone = normalize_phone_number(self.cleaned_data.get("phone"))
        if not re.match(r"^\d{11}$", phone):
            raise ValidationError(_("لطفا یک شماره تماس ۱۱ رقمی وارد کنید."))
        if not User.objects.filter(phone=phone).exists():
            raise ValidationError(_("حسابی با این شماره تماس پیدا نشد."))
        return phone


class PasswordResetConfirmForm(forms.Form):
    code = forms.CharField(
        label=_("کد تایید"),
        max_length=5,
        widget=forms.TextInput(
            attrs={
                "class": INPUT_CLASS,
                "placeholder": _("کد پنج رقمی"),
                "inputmode": "numeric",
                "autocomplete": "one-time-code",
                "dir": "ltr",
            }
        ),
        validators=[RegexValidator(regex=r"^\d{5}$", message=_("لطفا کد ۵ رقمی وارد کنید."))],
    )
    new_password1 = forms.CharField(
        label=_("رمز عبور جدید"),
        widget=forms.PasswordInput(attrs={"class": INPUT_CLASS, "placeholder": _("رمز عبور جدید")}),
        validators=[
            MinLengthValidator(8, message=_("رمز عبور باید حداقل ۸ کاراکتر باشد.")),
            RegexValidator(
                r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).+$",
                message=_("رمز عبور باید شامل حرف کوچک، حرف بزرگ و عدد باشد."),
            ),
        ],
    )
    new_password2 = forms.CharField(
        label=_("تکرار رمز عبور جدید"),
        widget=forms.PasswordInput(attrs={"class": INPUT_CLASS, "placeholder": _("تکرار رمز عبور جدید")}),
    )

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("new_password1")
        password_confirm = cleaned_data.get("new_password2")
        if password and password_confirm and password != password_confirm:
            self.add_error("new_password2", _("رمز عبور جدید و تکرار آن یکسان نیستند."))
        return cleaned_data


class FormRegister(forms.Form):
    fullname = forms.CharField(
        label=_("نام و نام خانوادگی"),
        max_length=150,
        widget=forms.TextInput(attrs={"placeholder": _("نام و نام خانوادگی"), "autocomplete": "name"}),
    )
    password = forms.CharField(
        label=_("رمز عبور"),
        widget=forms.PasswordInput(attrs={"placeholder": _("رمز عبور"), "autocomplete": "new-password"}),
    )
    password_confirm = forms.CharField(
        label=_("تایید رمز عبور"),
        widget=forms.PasswordInput(attrs={"placeholder": _("تکرار رمز عبور"), "autocomplete": "new-password"}),
    )
    phone = forms.CharField(
        label=_("شماره تلفن"),
        max_length=11,
        widget=forms.TextInput(attrs={"placeholder": _("شماره تماس"), "inputmode": "tel", "autocomplete": "tel", "dir": "ltr"}),
    )

    def clean_fullname(self):
        fullname = (self.cleaned_data.get("fullname") or "").strip()
        if not fullname:
            raise ValidationError(_("نام کاربری نمی‌تواند خالی باشد."))
        if not re.match(r"^[\w\s\u0600-\u06FF.\-]+$", fullname, flags=re.UNICODE):
            raise ValidationError(_("نام و نام خانوادگی باید فقط شامل حروف، اعداد و فاصله باشد."))
        if User.objects.filter(fullname=fullname).exists():
            raise ValidationError(_("این نام و نام خانوادگی قبلا ثبت شده است."))
        return fullname

    def clean_phone(self):
        phone = normalize_phone_number(self.cleaned_data.get("phone"))
        if len(phone) != 11 or not phone.isdigit():
            raise ValidationError(_("لطفا شماره تماس معتبر وارد کنید."))
        if User.objects.filter(phone=phone).exists():
            raise ValidationError(_("این شماره تماس قبلا ثبت شده است."))
        return phone

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        password_confirm = cleaned_data.get("password_confirm")
        if password and password_confirm and password != password_confirm:
            self.add_error("password_confirm", _("رمز عبور با تایید رمز عبور مطابقت ندارد."))
        return cleaned_data

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({"class": INPUT_CLASS})


class PasswordChanged(PasswordChangeForm):
    old_password = forms.CharField(
        max_length=128,
        widget=forms.PasswordInput(attrs={"class": INPUT_CLASS, "placeholder": _("کلمه عبور فعلی"), "autocomplete": "current-password"}),
        error_messages={"required": _("لطفا کلمه عبور فعلی خود را وارد کنید")},
    )
    new_password1 = forms.CharField(
        max_length=128,
        widget=forms.PasswordInput(attrs={"class": INPUT_CLASS, "placeholder": _("کلمه عبور جدید"), "autocomplete": "new-password"}),
        error_messages={"required": _("لطفا کلمه عبور جدید خود را وارد کنید")},
        validators=[
            MinLengthValidator(8, message=_("کلمه عبور باید حداقل 8 کاراکتر داشته باشد")),
            RegexValidator(
                r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).+$",
                message=_("کلمه عبور باید حداقل یک حرف کوچک، یک حرف بزرگ و یک عدد داشته باشد"),
            ),
        ],
    )
    new_password2 = forms.CharField(
        max_length=128,
        widget=forms.PasswordInput(attrs={"class": INPUT_CLASS, "placeholder": _("تکرار کلمه عبور جدید"), "autocomplete": "new-password"}),
        error_messages={"required": _("لطفا تکرار کلمه عبور جدید خود را وارد کنید")},
        validators=[
            MinLengthValidator(8, message=_("تکرار کلمه عبور باید حداقل 8 کاراکتر داشته باشد")),
            RegexValidator(
                r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).+$",
                message=_("تکرار کلمه عبور باید حداقل یک حرف کوچک، یک حرف بزرگ و یک عدد داشته باشد"),
            ),
        ],
    )

    def clean(self):
        cleaned_data = super().clean()
        new_password1 = cleaned_data.get("new_password1")
        new_password2 = cleaned_data.get("new_password2")
        if new_password1 and new_password2 and new_password1 != new_password2:
            self.add_error("new_password2", _("کلمه عبور جدید و تکرار آن یکسان نیستند"))
        return cleaned_data


class FormLogin(forms.Form):
    fullname = forms.CharField(
        label=_("نام کاربری"),
        max_length=150,
        widget=forms.TextInput(attrs={"placeholder": _("نام کاربری"), "autocomplete": "username"}),
    )
    password = forms.CharField(
        label=_("رمز عبور"),
        widget=forms.PasswordInput(attrs={"placeholder": _("رمز عبور"), "autocomplete": "current-password"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({"class": INPUT_CLASS})
