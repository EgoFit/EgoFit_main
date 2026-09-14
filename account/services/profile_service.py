from __future__ import annotations

from datetime import date

from django.db import transaction
from django.utils.translation import gettext_lazy as _

from account.domain.body_composition.calculator import (
    CaliperSkinfolds,
    CircumferenceMeasures,
    activity_factor_for_level,
    bmi_category_label,
    build_body_composition_snapshot,
    calculate_body_fat_from_caliper,
    calculate_bmi,
    calculate_bmr_mifflin_st_jeor,
    calculate_lean_mass,
    calculate_tdee,
    calculate_whr,
    calculate_whr_status,
    calculate_whtr,
    resolve_body_fat_result,
)
from account.exceptions import AuthenticationException, PasswordResetException, PhoneAlreadyExistsException
from account.models import User
from account.repositories.user_repository import UserRepository
from account.utils import is_birthday_today
from account.selectors.course_selector import CourseSelector
from account.selectors.user_selector import UserSelector
from account.services.notification_service import NotificationService
from account.services.otp_service import OTPService
from account.services.password_service import PasswordService
from account.services.session_service import SessionService


class ProfileService:
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

    def get_dashboard_context(self, user) -> dict:
        learning_courses = UserSelector.get_learning_courses(user)
        paid_orders = UserSelector.get_paid_orders(user)
        comments = UserSelector.get_user_comments(user)
        learning_courses_count = learning_courses.count()
        paid_orders_count = paid_orders.count()
        comments_count = comments.count()
        notifications_count = self.notification_service.get_notifications_count(user)
        recent_notifications = list(self.notification_service.get_dashboard_notifications(user, limit=5))
        recent_courses = list(learning_courses[:4])
        recent_orders = list(paid_orders[:5])
        recent_comments = list(comments[:5])
        return {
            "items": recent_courses,
            "recent_courses": recent_courses,
            "recent_orders": recent_orders,
            "recent_comments": recent_comments,
            "learning_courses_count": learning_courses_count,
            "paid_orders_count": paid_orders_count,
            "comments_count": comments_count,
            "notifications_count": notifications_count,
            "recent_notifications": recent_notifications,
            "dashboard_cards": [
                {
                    "key": "courses",
                    "label": _("دوره‌های من"),
                    "value": learning_courses_count,
                },
                {
                    "key": "orders",
                    "label": _("سفارش‌ها"),
                    "value": paid_orders_count,
                },
                {
                    "key": "comments",
                    "label": _("دیدگاه‌ها"),
                    "value": comments_count,
                },
                {
                    "key": "notifications",
                    "label": _("اعلان‌ها"),
                    "value": notifications_count,
                },
            ],
            "profile_metrics": self.get_profile_metrics(user),
            "profile_overview_cards": self.get_profile_overview_cards(user),
            "is_birthday_today": is_birthday_today(user.birth_date_jalali),
            "dashboard_feed": self.get_dashboard_feed(user, recent_notifications=recent_notifications),
        }

    def get_dashboard_feed(self, user, *, recent_notifications=None) -> dict | None:
        """A single banner item for the dashboard: birthday greeting, else latest admin news."""
        if is_birthday_today(user.birth_date_jalali):
            display_name = user.display_name or user.fullname
            return {
                "kind": "birthday",
                "title": _("🎉 تولدت مبارک، %(name)s!") % {"name": display_name},
                "body": _("تیم ایگوفیت برات یک سال پر از پیشرفت آرزو می‌کند."),
            }
        latest = list(recent_notifications[:1]) if recent_notifications is not None else list(
            self.notification_service.get_dashboard_notifications(user, limit=1)
        )
        if latest:
            notification = latest[0]
            return {
                "kind": "news",
                "title": notification.title,
                "body": notification.message,
                "created_at": notification.created_at,
            }
        return None

    @staticmethod
    def _format_value(value, suffix: str = "") -> str:
        if value in (None, ""):
            return _("ثبت نشده")
        return f"{value}{suffix}"

    @staticmethod
    def _calculate_bmi(weight_kg: int | None, height_cm: int | None):
        return calculate_bmi(weight_kg, height_cm)

    @staticmethod
    def _bmi_label(bmi: float | None) -> str:
        if bmi is None:
            return _("ثبت نشده")
        if bmi < 18.5:
            return _("کم‌وزن")
        if bmi < 25:
            return _("نرمال")
        if bmi < 30:
            return _("اضافه‌وزن")
        return _("چاق")

    @staticmethod
    def _parse_birth_date_jalali(birth_date: str | None):
        if not birth_date:
            return None
        try:
            import jdatetime

            parts = [int(part) for part in birth_date.split("/")]
            if len(parts) != 3:
                return None
            jalali_date = jdatetime.date(parts[0], parts[1], parts[2])
            gregorian_date = jalali_date.togregorian()
            today = date.today()
            age = today.year - gregorian_date.year - ((today.month, today.day) < (gregorian_date.month, gregorian_date.day))
            return age
        except Exception:
            return None

    def get_profile_metrics(self, user) -> list[dict]:
        bmi = self._calculate_bmi(user.weight_kg, user.height_cm)
        age = self._parse_birth_date_jalali(user.birth_date_jalali)
        metric_rows = [
            {
                "key": "weight",
                "label": _("وزن"),
                "value": self._format_value(user.weight_kg, f" {_('کیلوگرم')}"),
                "raw_value": user.weight_kg,
                "edit_url": "register:profile_weight_edit",
            },
            {
                "key": "height",
                "label": _("قد"),
                "value": self._format_value(user.height_cm, f" {_('سانتی متر')}"),
                "raw_value": user.height_cm,
                "edit_url": "register:profile_height_edit",
            },
            {
                "key": "birth_date",
                "label": _("تولد"),
                "value": self._format_value(user.birth_date_jalali),
                "raw_value": user.birth_date_jalali,
                "edit_url": "register:profile_birth_date_edit",
            },
            {
                "key": "phone",
                "label": _("شماره همراه"),
                "value": self._format_value(user.phone),
                "raw_value": user.phone,
                "edit_url": "register:profile_number_edit",
            },
            {
                "key": "blood_group",
                "label": _("گروه خونی"),
                "value": self._format_value(user.blood_group),
                "raw_value": user.blood_group,
                "edit_url": "register:profile_blood_group_edit",
            },
        ]
        return [
            *metric_rows,
            {
                "key": "bmi",
                "label": "BMI",
                "value": self._format_value(bmi),
                "raw_value": bmi,
                "edit_url": "register:profile_analysis",
                "badge": self._bmi_label(bmi),
            },
            {
                "key": "age",
                "label": _("سن"),
                "value": self._format_value(age, f" {_('سال')}"),
                "raw_value": age,
                "edit_url": "register:profile_birth_date_edit",
            },
        ]

    def get_profile_overview_cards(self, user) -> list[dict]:
        return [
            {
                "key": "weight",
                "label": _("وزن"),
                "value": self._format_value(user.weight_kg, f" {_('کیلوگرم')}"),
                "edit_url": "register:profile_weight_edit",
                "icon": "weight",
            },
            {
                "key": "height",
                "label": _("قد"),
                "value": self._format_value(user.height_cm, f" {_('سانتی‌متر')}"),
                "edit_url": "register:profile_height_edit",
                "icon": "height",
            },
            {
                "key": "phone",
                "label": _("شماره همراه"),
                "value": self._format_value(user.phone),
                "edit_url": "register:profile_number_edit",
                "icon": "phone",
            },
            {
                "key": "birth_date",
                "label": _("تاریخ تولد"),
                "value": self._format_value(user.birth_date_jalali),
                "edit_url": "register:profile_birth_date_edit",
                "icon": "birth_date",
            },
            {
                "key": "blood_group",
                "label": _("گروه خونی"),
                "value": self._format_value(user.blood_group),
                "edit_url": "register:profile_blood_group_edit",
                "icon": "blood_group",
                "full_width": True,
            },
        ]

    @staticmethod
    def _segmented_bar(marker: int, *, zones: list[dict] | None = None) -> dict:
        return {
            "marker": max(4, min(marker, 96)),
            "zones": zones
            or [
                {"width": 22, "tone": "orange"},
                {"width": 24, "tone": "yellow"},
                {"width": 28, "tone": "green"},
                {"width": 26, "tone": "yellow"},
            ],
        }

    @staticmethod
    def _build_chart(points: list[int], *, width: int = 320, height: int = 160, top_pad: int = 18, bottom_pad: int = 34):
        if not points:
            points = [0]

        usable_width = width - 40
        usable_height = height - top_pad - bottom_pad
        min_value = min(points)
        max_value = max(points)
        if min_value == max_value:
            max_value = min_value + 1

        rendered_points = []
        for index, value in enumerate(points):
            if len(points) == 1:
                x = 20 + usable_width / 2
            else:
                x = 20 + (usable_width * index / (len(points) - 1))
            normalized = (value - min_value) / (max_value - min_value)
            y = top_pad + ((1 - normalized) * usable_height)
            rendered_points.append({"x": round(x, 1), "y": round(y, 1), "value": value})

        path = "M " + " L ".join(f"{point['x']} {point['y']}" for point in rendered_points)
        baseline = height - bottom_pad
        area_path = f"{path} L {rendered_points[-1]['x']} {baseline} L {rendered_points[0]['x']} {baseline} Z"
        return rendered_points, path, area_path

    CIRCUMFERENCE_FIELD_LABELS = [
        ("wrist_cm", _("دور مچ دست")),
        ("forearm_cm", _("دور ساعد")),
        ("arm_rest_cm", _("دور بازو (استراحت)")),
        ("arm_flexed_cm", _("دور بازو (انقباض)")),
        ("wrist_left_cm", _("دور مچ دست (چپ)")),
        ("forearm_left_cm", _("دور ساعد (چپ)")),
        ("arm_rest_left_cm", _("دور بازو در حالت استراحت (چپ)")),
        ("arm_flexed_left_cm", _("دور بازو در حالت انقباض (چپ)")),
        ("head_cm", _("دور سر")),
        ("neck_cm", _("دور گردن")),
        ("chest_cm", _("دور قفسه سینه")),
        ("shoulders_cm", _("دور شانه‌ها")),
        ("waist_cm", _("دور کمر")),
        ("abdomen_cm", _("دور شکم")),
        ("hips_cm", _("دور باسن")),
        ("thigh_cm", _("دور ران")),
        ("calf_cm", _("دور ساق پا")),
        ("thigh_left_cm", _("دور ران پا (چپ)")),
        ("calf_left_cm", _("دور ساق پا (چپ)")),
        ("sit_height_cm", _("قد نشسته")),
        ("leg_length_cm", _("طول پا")),
    ]

    CALIPER_FIELD_LABELS = [
        ("chest_armpit_men_mm", _("سینه")),
        ("axilla_mm", _("زیربغل")),
        ("subscapular_mm", _("تحت کتفی")),
        ("abdominal_mm", _("شکم")),
        ("suprailiac_mm", _("سه‌تیغ خاصره")),
        ("chest_mm", _("کمر")),
        ("biceps_mm", _("جلوبازو")),
        ("triceps_mm", _("پشت بازو")),
        ("thigh_mm", _("جلوی ران")),
        ("calf_mm", _("پشت ساق")),
    ]

    ANALYSIS_METRIC_OPTIONS = [
        {"key": "body_fat", "label": _("درصد چربی بدن")},
        {"key": "lean_mass", "label": _("توده عضلانی بدون چربی")},
        {"key": "whr", "label": "WHR"},
        {"key": "whtr", "label": "WHtR"},
        {"key": "bmi", "label": "BMI"},
        {"key": "bmr", "label": "BMR"},
    ]

    BODY_FAT_FORMULA_OPTIONS = [
        {"key": "auto", "label": _("خودکار (بهترین فرمول موجود)")},
        {"key": "jp7", "label": "Jackson-Pollock 7-site"},
        {"key": "jp4", "label": "Jackson-Pollock 4-site"},
        {"key": "jp3", "label": "Jackson-Pollock 3-site"},
        {"key": "circumference", "label": _("درصد چربی (دورسنجی — Navy)")},
    ]

    @classmethod
    def _analysis_metric_label(cls, metric: str) -> str:
        for option in cls.ANALYSIS_METRIC_OPTIONS:
            if option["key"] == metric:
                return option["label"]
        return _("درصد چربی بدن")

    @staticmethod
    def _validate_jalali_date(value: str | None) -> str | None:
        if not value:
            return None
        try:
            import jdatetime

            parts = [int(part) for part in value.strip().split("/")]
            if len(parts) != 3:
                return None
            jdatetime.date(parts[0], parts[1], parts[2])
            return value.strip()
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _jalali_from_datetime(dt) -> str:
        import jdatetime
        from django.utils import timezone

        local = timezone.localtime(dt)
        return jdatetime.datetime.fromgregorian(datetime=local).strftime("%Y/%m/%d")

    @classmethod
    def _parse_jalali_date_obj(cls, value: str):
        import jdatetime

        parts = [int(part) for part in value.split("/")]
        return jdatetime.date(parts[0], parts[1], parts[2])

    @classmethod
    def _default_analysis_date_range(cls, user) -> tuple[str, str]:
        import jdatetime
        from datetime import timedelta

        timestamps = []
        for record in user.circumference_records.all()[:100]:
            timestamps.append(record.recorded_at)
        for record in user.caliper_records.all()[:100]:
            timestamps.append(record.recorded_at)

        if timestamps:
            return cls._jalali_from_datetime(min(timestamps)), cls._jalali_from_datetime(max(timestamps))

        today = jdatetime.date.today()
        start = jdatetime.date.fromgregorian(date=today.togregorian() - timedelta(days=90))
        return start.strftime("%Y/%m/%d"), today.strftime("%Y/%m/%d")

    @staticmethod
    def _resolve_age(user) -> int | None:
        age = ProfileService._parse_birth_date_jalali(user.birth_date_jalali)
        if age is not None:
            return age
        return user.age

    @classmethod
    def _build_measurement_display(cls, circumference, caliper) -> dict:
        circumference_rows = []
        caliper_rows = []

        if circumference:
            for field_name, label in cls.CIRCUMFERENCE_FIELD_LABELS:
                value = getattr(circumference, field_name, None)
                if value not in (None, ""):
                    circumference_rows.append({"label": label, "value": f"{value} {_('سانتی‌متر')}"})

        if caliper:
            for field_name, label in cls.CALIPER_FIELD_LABELS:
                value = getattr(caliper, field_name, None)
                if value not in (None, ""):
                    caliper_rows.append({"label": label, "value": f"{value} {_('میلی‌متر')}"})

        return {
            "circumference_rows": circumference_rows,
            "caliper_rows": caliper_rows,
            "has_measurements": bool(circumference_rows or caliper_rows),
        }

    @classmethod
    def _find_caliper_for_datetime(cls, user, dt, caliper_records=None):
        import jdatetime
        from django.utils import timezone

        target_local = timezone.localtime(dt)
        target_j = jdatetime.datetime.fromgregorian(datetime=target_local).date()
        records = caliper_records if caliper_records is not None else user.caliper_records.all()
        for record in records:
            record_local = timezone.localtime(record.recorded_at)
            record_j = jdatetime.datetime.fromgregorian(datetime=record_local).date()
            if record_j == target_j:
                return record
        return None

    @staticmethod
    def _body_fat_from_caliper(
        caliper,
        *,
        age: int | None,
        gender: str | None,
        formula: str | None = None,
    ) -> float | None:
        skinfolds = CaliperSkinfolds.from_model(caliper)
        result = calculate_body_fat_from_caliper(skinfolds, age=age, gender=gender, formula=formula)
        return result.body_fat_percent if result else None

    @staticmethod
    def _body_fat_from_measurements(
        *,
        caliper,
        circumference,
        height_cm,
        age: int | None,
        gender: str | None,
        formula: str | None = None,
    ) -> float | None:
        result = resolve_body_fat_result(
            skinfolds=CaliperSkinfolds.from_model(caliper),
            circumference=CircumferenceMeasures.from_model(circumference),
            height_cm=height_cm,
            age=age,
            gender=gender,
            formula=formula,
        )
        return result.body_fat_percent if result else None

    @staticmethod
    def _whr_from_circumference(circumference) -> float | None:
        measures = CircumferenceMeasures.from_model(circumference)
        if measures is None:
            return None
        return calculate_whr(measures.waist_cm, measures.hips_cm)

    def _whtr_from_circumference(self, user, circumference) -> float | None:
        measures = CircumferenceMeasures.from_model(circumference)
        if measures is None:
            return None
        return calculate_whtr(measures.waist_cm, user.height_cm)

    @staticmethod
    def _lean_mass_from_user(user, body_fat: float | None) -> float | None:
        return calculate_lean_mass(user.weight_kg, body_fat)

    def _bmr_value(self, user, age) -> int | None:
        from account.domain.body_composition.calculator import calculate_bmr_mifflin_st_jeor

        return calculate_bmr_mifflin_st_jeor(
            weight_kg=user.weight_kg,
            height_cm=user.height_cm,
            age=age,
            gender=user.gender,
        )

    def _metric_value_from_records(
        self,
        user,
        metric: str,
        circumference,
        caliper,
        *,
        body_fat_formula: str | None = None,
    ):
        age = self._resolve_age(user)
        gender = user.gender
        weight = user.weight_kg
        height = user.height_cm
        if circumference is not None:
            if circumference.weight_kg is not None:
                weight = circumference.weight_kg
            if circumference.height_cm is not None:
                height = circumference.height_cm
        skinfolds = CaliperSkinfolds.from_model(caliper)
        measures = CircumferenceMeasures.from_model(circumference)
        snapshot = build_body_composition_snapshot(
            weight_kg=weight,
            height_cm=height,
            age=age,
            gender=gender,
            skinfolds=skinfolds,
            circumference=measures,
            body_fat_formula=body_fat_formula,
        )

        if metric == "body_fat":
            return snapshot.body_fat_percent
        if metric == "lean_mass":
            return snapshot.lean_mass_kg
        if metric == "whr":
            return snapshot.whr
        if metric == "whtr":
            return snapshot.whtr
        if metric == "bmi":
            return snapshot.bmi
        if metric == "bmr":
            return snapshot.bmr
        return snapshot.body_fat_percent

    def _metric_series_points(
        self,
        user,
        metric: str,
        start_j,
        end_j,
        *,
        body_fat_formula: str | None = None,
        circumference_records=None,
        caliper_records=None,
    ) -> list[tuple]:
        """Sorted ``(jalali_date, value)`` points for a metric within a Jalali date range."""
        series: list[tuple] = []
        age = self._resolve_age(user)
        gender = user.gender
        selected_body_fat_formula = self._resolve_body_fat_formula(body_fat_formula)
        circ_records = circumference_records if circumference_records is not None else user.circumference_records.all()
        cal_records = caliper_records if caliper_records is not None else user.caliper_records.all()

        if metric == "body_fat":
            if selected_body_fat_formula == "circumference":
                for record in circ_records:
                    j_date = self._parse_jalali_date_obj(self._record_jalali_date(record))
                    if start_j <= j_date <= end_j:
                        paired_caliper = self._find_caliper_for_datetime(user, record.recorded_at, caliper_records=cal_records)
                        height = record.height_cm if record.height_cm is not None else user.height_cm
                        value = self._body_fat_from_measurements(
                            caliper=paired_caliper,
                            circumference=record,
                            height_cm=height,
                            age=age,
                            gender=gender,
                            formula=selected_body_fat_formula,
                        )
                        if value is not None:
                            series.append((j_date, value))
            else:
                for record in cal_records:
                    j_date = self._parse_jalali_date_obj(self._record_jalali_date(record))
                    if start_j <= j_date <= end_j:
                        value = self._body_fat_from_caliper(
                            record,
                            age=age,
                            gender=gender,
                            formula=selected_body_fat_formula,
                        )
                        if value is not None:
                            series.append((j_date, value))
        elif metric in ("whr", "whtr"):
            for record in circ_records:
                j_date = self._parse_jalali_date_obj(self._jalali_from_datetime(record.recorded_at))
                if start_j <= j_date <= end_j:
                    value = (
                        self._whr_from_circumference(record)
                        if metric == "whr"
                        else self._whtr_from_circumference(user, record)
                    )
                    if value is not None:
                        series.append((j_date, value))
        elif metric == "lean_mass":
            if selected_body_fat_formula == "circumference":
                for record in circ_records:
                    j_date = self._parse_jalali_date_obj(self._record_jalali_date(record))
                    if start_j <= j_date <= end_j:
                        paired_caliper = self._find_caliper_for_datetime(user, record.recorded_at, caliper_records=cal_records)
                        height = record.height_cm if record.height_cm is not None else user.height_cm
                        body_fat = self._body_fat_from_measurements(
                            caliper=paired_caliper,
                            circumference=record,
                            height_cm=height,
                            age=age,
                            gender=gender,
                            formula=selected_body_fat_formula,
                        )
                        value = self._lean_mass_from_user(user, body_fat)
                        if value is not None:
                            series.append((j_date, value))
            else:
                for record in cal_records:
                    j_date = self._parse_jalali_date_obj(self._record_jalali_date(record))
                    if start_j <= j_date <= end_j:
                        body_fat = self._body_fat_from_caliper(
                            record,
                            age=age,
                            gender=gender,
                            formula=selected_body_fat_formula,
                        )
                        value = self._lean_mass_from_user(user, body_fat)
                        if value is not None:
                            series.append((j_date, value))
        elif metric == "bmi":
            bmi = calculate_bmi(user.weight_kg, user.height_cm)
            if bmi is not None:
                for record in circ_records:
                    j_date = self._parse_jalali_date_obj(self._jalali_from_datetime(record.recorded_at))
                    if start_j <= j_date <= end_j:
                        series.append((j_date, bmi))
        elif metric == "bmr":
            bmr = self._bmr_value(user, age)
            if bmr is not None:
                for record in circ_records:
                    j_date = self._parse_jalali_date_obj(self._jalali_from_datetime(record.recorded_at))
                    if start_j <= j_date <= end_j:
                        series.append((j_date, bmr))
        else:
            for record in circ_records:
                j_date = self._parse_jalali_date_obj(self._jalali_from_datetime(record.recorded_at))
                if start_j <= j_date <= end_j:
                    paired_caliper = self._find_caliper_for_datetime(user, record.recorded_at, caliper_records=cal_records)
                    value = self._metric_value_from_records(
                        user,
                        metric,
                        record,
                        paired_caliper,
                        body_fat_formula=selected_body_fat_formula,
                    )
                    if value is not None:
                        series.append((j_date, value))

        series.sort(key=lambda item: item[0])
        return series

    def _collect_metric_series(
        self,
        user,
        metric: str,
        start_j,
        end_j,
        *,
        body_fat_formula: str | None = None,
        circumference_records=None,
        caliper_records=None,
    ) -> list[float]:
        return [
            float(value)
            for _, value in self._metric_series_points(
                user,
                metric,
                start_j,
                end_j,
                body_fat_formula=body_fat_formula,
                circumference_records=circumference_records,
                caliper_records=caliper_records,
            )
        ]

    @staticmethod
    def _metric_round(metric: str, value: float):
        if metric in ("whr", "whtr"):
            return round(float(value), 2)
        if metric == "bmr":
            return int(round(float(value)))
        if metric in ("body_fat", "lean_mass", "bmi"):
            return round(float(value), 1)
        return round(float(value), 1)

    @staticmethod
    def _metric_unit(metric: str) -> str:
        if metric == "body_fat":
            return "%"
        if metric == "lean_mass":
            return str(_("کیلوگرم"))
        if metric == "bmr":
            return "kcal"
        return ""

    @staticmethod
    def _status_tone(text) -> str:
        """Map a Persian status label to a colour tone for the result tiles."""
        if not text:
            return "neutral"
        value = str(text)
        if any(keyword in value for keyword in ("نرمال", "مطلوب", "سالم", "ایده", "متعادل")):
            return "good"
        if any(keyword in value for keyword in ("چاق", "پرخطر", "خطر", "بالا")):
            return "danger"
        if any(keyword in value for keyword in ("اضافه", "متوسط", "کم‌وزن", "کم وزن", "لاغر")):
            return "warn"
        return "neutral"

    @staticmethod
    def _tile_number(value, *, decimals: int = 1):
        if value in (None, ""):
            return "—"
        if decimals == 0:
            return int(round(float(value)))
        return round(float(value), decimals)

    def get_analysis_metric_series(self, user, *, body_fat_formula: str | None = None) -> dict:
        """Per-metric labelled time series for the client-side metric dropdown chart."""
        default_start, default_end = self._default_analysis_date_range(user)
        start_j = self._parse_jalali_date_obj(default_start)
        end_j = self._parse_jalali_date_obj(default_end)
        selected_body_fat_formula = self._resolve_body_fat_formula(body_fat_formula)
        series: dict = {}
        for option in self.ANALYSIS_METRIC_OPTIONS:
            key = option["key"]
            points = self._metric_series_points(
                user,
                key,
                start_j,
                end_j,
                body_fat_formula=selected_body_fat_formula,
            )
            series[key] = {
                "labels": [point[0].strftime("%Y/%m/%d") for point in points],
                "values": [self._metric_round(key, point[1]) for point in points],
                "label": str(option["label"]),
                "unit": self._metric_unit(key),
            }
        return series

    @staticmethod
    def _scale_series_for_chart(metric: str, values: list[float]) -> list[int]:
        scaled = []
        for value in values:
            if metric in ("whr", "whtr"):
                scaled.append(max(1, int(value * 100)))
            elif metric == "bmi":
                scaled.append(max(1, int(value * 10)))
            elif metric == "bmr":
                scaled.append(max(1, int(value / 10)))
            else:
                scaled.append(max(1, int(value)))
        return scaled

    def _format_metric_display(self, metric: str, value) -> str:
        if value in (None, ""):
            return _("ثبت نشده")
        if metric == "body_fat":
            return f"{value}%"
        if metric == "lean_mass":
            return f"{value} {_('کیلوگرم')}"
        if metric == "bmr":
            return str(int(value))
        return str(value)

    @classmethod
    def _record_jalali_date(cls, record) -> str:
        if getattr(record, "measured_at_jalali", None):
            return record.measured_at_jalali
        return cls._jalali_from_datetime(record.recorded_at)

    @classmethod
    def _resolve_body_fat_formula(cls, value: str | None) -> str:
        valid = {option["key"] for option in cls.BODY_FAT_FORMULA_OPTIONS}
        formula = (value or "auto").strip().lower()
        return formula if formula in valid else "auto"

    @classmethod
    def _body_fat_formula_label(cls, formula_key: str) -> str:
        for option in cls.BODY_FAT_FORMULA_OPTIONS:
            if option["key"] == formula_key:
                return option["label"]
        return formula_key

    def get_analysis_context(
        self,
        user,
        *,
        metric: str | None = None,
        start: str | None = None,
        end: str | None = None,
        date: str | None = None,
        circ_date: str | None = None,
        body_fat_formula: str | None = None,
        caliper_date: str | None = None,
        use_full_chart_range: bool = False,
    ) -> dict:
        valid_metrics = {option["key"] for option in self.ANALYSIS_METRIC_OPTIONS}
        selected_metric = metric if metric in valid_metrics else "body_fat"
        default_start, default_end = self._default_analysis_date_range(user)
        start_date = self._validate_jalali_date(start) or default_start
        end_date = self._validate_jalali_date(end) or default_end

        if use_full_chart_range:
            chart_start_date, chart_end_date = default_start, default_end
        else:
            chart_start_date, chart_end_date = start_date, end_date

        start_j = self._parse_jalali_date_obj(chart_start_date)
        end_j = self._parse_jalali_date_obj(chart_end_date)
        if start_j > end_j:
            start_j, end_j = end_j, start_j
            chart_start_date, chart_end_date = chart_end_date, chart_start_date

        bmi = calculate_bmi(user.weight_kg, user.height_cm)
        bmi_label = bmi_category_label(bmi)
        age = self._resolve_age(user)
        has_data = any(
            value not in (None, "")
            for value in (user.weight_kg, user.height_cm, user.birth_date_jalali, user.blood_group, user.gender)
        ) or user.circumference_records.exists() or user.caliper_records.exists()

        circumference_records = list(user.circumference_records.all()[:120])
        caliper_records = list(user.caliper_records.all()[:120])
        circ_by_date: dict = {}
        for record in sorted(circumference_records, key=lambda r: r.recorded_at, reverse=True):
            circ_by_date.setdefault(self._record_jalali_date(record), record)
        cal_by_date: dict = {}
        for record in sorted(caliper_records, key=lambda r: r.recorded_at, reverse=True):
            cal_by_date.setdefault(self._record_jalali_date(record), record)

        circ_dates = sorted(circ_by_date.keys(), reverse=True)
        analysis_circ_dates = [{"value": value, "label": value} for value in circ_dates]
        selected_body_fat_formula = self._resolve_body_fat_formula(body_fat_formula)
        analysis_body_fat_formulas = list(self.BODY_FAT_FORMULA_OPTIONS)

        legacy_date = self._validate_jalali_date(date)
        selected_circ_date = self._validate_jalali_date(circ_date) or legacy_date
        if selected_circ_date not in circ_dates:
            selected_circ_date = circ_dates[0] if circ_dates else None

        caliper_dates = sorted(cal_by_date.keys(), reverse=True)
        selected_date = selected_circ_date or (caliper_dates[0] if caliper_dates else None)

        latest_circumference = circ_by_date.get(selected_circ_date) or (circumference_records[0] if circumference_records else None)
        paired_caliper = (
            self._find_caliper_for_datetime(user, latest_circumference.recorded_at, caliper_records=caliper_records)
            if latest_circumference
            else (caliper_records[0] if caliper_records else None)
        ) or (caliper_records[0] if caliper_records else None)

        skinfolds = CaliperSkinfolds.from_model(paired_caliper)
        measures = CircumferenceMeasures.from_model(latest_circumference)
        snapshot_weight = latest_circumference.weight_kg if latest_circumference and latest_circumference.weight_kg is not None else user.weight_kg
        snapshot_height = latest_circumference.height_cm if latest_circumference and latest_circumference.height_cm is not None else user.height_cm
        composition = build_body_composition_snapshot(
            weight_kg=snapshot_weight,
            height_cm=snapshot_height,
            age=age,
            gender=user.gender,
            skinfolds=skinfolds,
            circumference=measures,
            activity_level=user.activity_level,
            body_fat_formula=selected_body_fat_formula,
        )
        body_fat_result = resolve_body_fat_result(
            skinfolds=skinfolds,
            circumference=measures,
            height_cm=snapshot_height,
            age=age,
            gender=user.gender,
            formula=selected_body_fat_formula,
        )
        measurements = self._build_measurement_display(latest_circumference, paired_caliper)

        raw_series = self._collect_metric_series(
            user,
            selected_metric,
            start_j,
            end_j,
            body_fat_formula=selected_body_fat_formula,
            circumference_records=circumference_records,
            caliper_records=caliper_records,
        )
        chart_has_real_data = len(raw_series) >= 2
        if chart_has_real_data:
            chart_input = self._scale_series_for_chart(selected_metric, raw_series)
            chart_points, chart_path, chart_area_path = self._build_chart(chart_input)
        else:
            chart_points, chart_path, chart_area_path = [], "", ""

        body_fat = composition.body_fat_percent
        current_value = self._metric_value_from_records(
            user,
            selected_metric,
            latest_circumference,
            paired_caliper,
            body_fat_formula=selected_body_fat_formula,
        )
        analysis_value = self._format_metric_display(selected_metric, current_value)
        bmr_display = composition.bmr if composition.bmr is not None else _("ثبت نشده")
        daily_calories = composition.tdee if composition.tdee is not None else _("ثبت نشده")
        if composition.protein_min_g is not None and composition.protein_max_g is not None:
            daily_protein = _("%(min)s تا %(max)s گرم") % {
                "min": composition.protein_min_g,
                "max": composition.protein_max_g,
            }
        else:
            daily_protein = _("ثبت نشده")

        if not user.gender and selected_metric == "body_fat":
            analysis_subtitle = _("برای محاسبه درصد چربی، مربی باید جنسیت را در پروفایل ثبت کند.")
        elif body_fat is None and selected_metric == "body_fat":
            if selected_body_fat_formula == "circumference":
                analysis_subtitle = _("برای محاسبه درصد چربی دورسنجی، دور کمر، گردن و قد لازم است.")
            else:
                analysis_subtitle = _("برای محاسبه درصد چربی، اندازه‌گیری کالیپر کافی توسط مربی لازم است.")
        elif bmi is not None:
            analysis_subtitle = bmi_label
        else:
            analysis_subtitle = _("برای نمایش گزارش، وزن و قد را ثبت کنید.")

        progress = int(current_value) if isinstance(current_value, (int, float)) else (body_fat or 0)
        if selected_metric in ("whr", "whtr") and isinstance(current_value, float):
            progress = int(current_value * 100)
        elif selected_metric == "bmi" and isinstance(current_value, float):
            progress = int(min(current_value * 2.2, 96))

        filter_label = self._analysis_metric_label(selected_metric)
        if use_full_chart_range and chart_has_real_data:
            range_label = _("روند کامل اندازه‌گیری‌ها")
        else:
            range_label = _("از تاریخ %(start_date)s تا تاریخ %(end_date)s") % {
                "start_date": chart_start_date,
                "end_date": chart_end_date,
            }

        # --- Calculation result tiles (clean numeric squares; no somatotype) ----
        whr_value = composition.whr if composition.whr is not None else (
            self._whr_from_circumference(latest_circumference) if latest_circumference else None
        )
        analysis_result_tiles = [
            {
                "key": "body_fat",
                "label": _("درصد چربی بدن"),
                "value": self._tile_number(body_fat),
                "unit": "%",
                "tone": "neutral",
                "status": "",
            },
            {
                "key": "lean_mass",
                "label": _("توده عضلانی بدون چربی"),
                "value": self._tile_number(composition.lean_mass_kg),
                "unit": "kg",
                "tone": "neutral",
                "status": "",
            },
            {
                "key": "whr",
                "label": "WHR",
                "value": self._tile_number(whr_value, decimals=2),
                "unit": "",
                "tone": self._status_tone(composition.whr_status),
                "status": composition.whr_status or "",
            },
            {
                "key": "whtr",
                "label": "WHtR",
                "value": self._tile_number(composition.whtr, decimals=2),
                "unit": "",
                "tone": self._status_tone(composition.whtr_status),
                "status": composition.whtr_status or "",
            },
            {
                "key": "bmi",
                "label": "BMI",
                "value": bmi if bmi is not None else "—",
                "unit": "",
                "tone": self._status_tone(bmi_label) if bmi is not None else "neutral",
                "status": bmi_label if bmi is not None else "",
            },
            {
                "key": "bmr",
                "label": "BMR",
                "value": self._tile_number(composition.bmr, decimals=0),
                "unit": "kcal",
                "tone": "neutral",
                "status": "",
            },
            {
                "key": "calories",
                "label": _("کالری روزانه"),
                "value": self._tile_number(composition.tdee, decimals=0),
                "unit": "kcal",
                "tone": "neutral",
                "status": "",
            },
            {
                "key": "protein",
                "label": _("پروتئین روزانه"),
                "value": daily_protein,
                "unit": "",
                "tone": "neutral",
                "status": "",
            },
        ]

        return {
            "analysis_has_data": has_data,
            "analysis_selected_metric": selected_metric,
            "analysis_filter_label": filter_label,
            "analysis_metric_options": self.ANALYSIS_METRIC_OPTIONS,
            "analysis_range_label": range_label,
            "analysis_start_date": chart_start_date,
            "analysis_end_date": chart_end_date,
            "analysis_dates": [{"value": value, "label": value} for value in circ_dates],
            "analysis_selected_date": selected_date,
            "analysis_circ_dates": analysis_circ_dates,
            "analysis_selected_circ_date": selected_circ_date,
            "analysis_body_fat_formulas": analysis_body_fat_formulas,
            "analysis_selected_body_fat_formula": selected_body_fat_formula,
            "analysis_selected_body_fat_formula_label": self._body_fat_formula_label(selected_body_fat_formula),
            "analysis_result_tiles": analysis_result_tiles,
            "analysis_summary": {
                "title": filter_label,
                "value": analysis_value,
                "progress": progress,
                "subtitle": analysis_subtitle,
            },
            "analysis_chart_has_data": chart_has_real_data,
            "analysis_formula_used": body_fat_result.formula_name if body_fat_result else composition.body_fat_formula,
            "analysis_measurements": measurements,
            "analysis_body_composition": {
                "fat_mass_kg": composition.fat_mass_kg,
                "lean_mass_kg": composition.lean_mass_kg,
                "tdee": composition.tdee,
                "calories_for_loss": composition.calories_for_loss,
                "calories_for_gain": composition.calories_for_gain,
                "protein_min_g": composition.protein_min_g,
                "protein_max_g": composition.protein_max_g,
                "whr_status": composition.whr_status,
                "whtr_status": composition.whtr_status,
                "body_frame_size": composition.body_frame_size,
                "endomorphy": composition.endomorphy,
                "mesomorphy": composition.mesomorphy,
                "ectomorphy": composition.ectomorphy,
                "arm_ratio": composition.arm_ratio,
                "shoulder_hip_ratio": composition.shoulder_hip_ratio,
            },
            "analysis_metrics": [
                {
                    "label": _("درصد چربی بدن"),
                    "value": self._format_metric_display("body_fat", body_fat),
                    **self._segmented_bar(int(body_fat) if body_fat else 18),
                },
                {
                    "label": _("توده عضلانی بدون چربی"),
                    "value": self._format_metric_display(
                        "lean_mass",
                        composition.lean_mass_kg,
                    ),
                    **self._segmented_bar(58 if user.weight_kg else 16),
                },
                {
                    "label": "WHR",
                    "value": self._format_metric_display(
                        "whr",
                        self._whr_from_circumference(latest_circumference) if latest_circumference else None,
                    ),
                    **self._segmented_bar(
                        int((self._whr_from_circumference(latest_circumference) or 0.46) * 100)
                        if latest_circumference
                        else 14
                    ),
                },
                {
                    "label": _("وضعیت WHR"),
                    "value": composition.whr_status or _("ثبت نشده"),
                    **self._segmented_bar(int((composition.whr or 0.46) * 100)),
                },
                {
                    "label": _("وضعیت WHtR"),
                    "value": composition.whtr_status or _("ثبت نشده"),
                    **self._segmented_bar(int((composition.whtr or 0.46) * 100)),
                },
                {
                    "label": _("اندازه قاب بدن"),
                    "value": composition.body_frame_size or _("ثبت نشده"),
                    **self._segmented_bar(18),
                },
                {
                    "label": _("سوماتوتایپ (اندومورف/مزومورف/اکتومورف)"),
                    "value": (
                        f"{composition.endomorphy} / {composition.mesomorphy} / {composition.ectomorphy}"
                        if composition.endomorphy is not None
                        else _("ثبت نشده")
                    ),
                    **self._segmented_bar(20),
                },
                {
                    "label": "BMI",
                    "value": bmi if bmi is not None else _("ثبت نشده"),
                    **self._segmented_bar(round(min(bmi or 0, 40) * 2.2) if bmi is not None else 18),
                },
                {
                    "label": "BMR",
                    "value": bmr_display,
                    **self._segmented_bar(42 if bmi is not None else 18),
                },
                {
                    "label": _("کالری مورد نیاز روزانه"),
                    "value": daily_calories,
                    **self._segmented_bar(22 if bmi is not None else 14),
                },
                {
                    "label": _("پروتئین مورد نیاز روزانه"),
                    "value": daily_protein,
                    **self._segmented_bar(16 if user.weight_kg else 14),
                },
            ],
            "analysis_chart_points": chart_points,
            "analysis_chart_path": chart_path,
            "analysis_chart_area_path": chart_area_path,
            "analysis_age": age,
            "analysis_bmi": bmi,
        }

    def get_analysis_dashboard_data(self, user, *, body_fat_formula: str | None = None) -> dict:
        """JSON-ready time-series + gauges + history rows for the analysis dashboard (Chart.js)."""
        age = self._resolve_age(user)
        gender = user.gender
        activity_factor = activity_factor_for_level(user.activity_level)
        selected_body_fat_formula = self._resolve_body_fat_formula(body_fat_formula)

        circ_records = sorted(user.circumference_records.all()[:80], key=lambda r: r.recorded_at)
        cal_records = sorted(user.caliper_records.all()[:80], key=lambda r: r.recorded_at)

        def jdate(record) -> str:
            return self._jalali_from_datetime(record.recorded_at)

        circ_labels = [jdate(record) for record in circ_records]

        def aligned(attr):
            out = []
            for record in circ_records:
                value = getattr(record, attr, None)
                out.append(float(value) if value not in (None, "") else None)
            return out

        # --- Main trend charts -------------------------------------------------
        weight_labels, weight_values = [], []
        bmi_labels, bmi_values = [], []
        whr_labels, whr_values = [], []
        cal_labels, cal_values = [], []
        for record in circ_records:
            label = jdate(record)
            weight = record.weight_kg or user.weight_kg
            height = record.height_cm or user.height_cm
            if weight:
                weight_labels.append(label)
                weight_values.append(int(weight))
            bmi = calculate_bmi(weight, height)
            if bmi is not None:
                bmi_labels.append(label)
                bmi_values.append(bmi)
            whr = self._whr_from_circumference(record)
            if whr is not None:
                whr_labels.append(label)
                whr_values.append(round(whr, 2))
            bmr = calculate_bmr_mifflin_st_jeor(weight_kg=weight, height_cm=height, age=age, gender=gender)
            tdee = calculate_tdee(bmr, activity_factor)
            if tdee is not None:
                cal_labels.append(label)
                cal_values.append(tdee)

        fat_labels, fat_values = [], []
        if selected_body_fat_formula == "circumference":
            for record in circ_records:
                paired_caliper = self._find_caliper_for_datetime(user, record.recorded_at, caliper_records=cal_records)
                height = record.height_cm if record.height_cm is not None else user.height_cm
                value = self._body_fat_from_measurements(
                    caliper=paired_caliper,
                    circumference=record,
                    height_cm=height,
                    age=age,
                    gender=gender,
                    formula=selected_body_fat_formula,
                )
                if value is not None:
                    fat_labels.append(jdate(record))
                    fat_values.append(round(float(value), 1))
        else:
            for record in cal_records:
                value = self._body_fat_from_caliper(
                    record,
                    age=age,
                    gender=gender,
                    formula=selected_body_fat_formula,
                )
                if value is not None:
                    fat_labels.append(jdate(record))
                    fat_values.append(round(float(value), 1))

        trend_charts = {
            "weight": {"labels": weight_labels, "values": weight_values},
            "bmi": {"labels": bmi_labels, "values": bmi_values},
            "whr": {"labels": whr_labels, "values": whr_values},
            "body_fat": {"labels": fat_labels, "values": fat_values},
            "calories": {"labels": cal_labels, "values": cal_values},
        }

        # --- Selectable measurement-trend groups (shared circumference x-axis) --
        measurement_groups = {
            "chest-shoulder": {
                "labels": circ_labels,
                "datasets": [
                    {"label": str(_("دور سینه")), "data": aligned("chest_cm")},
                    {"label": str(_("دور سرشانه")), "data": aligned("shoulders_cm")},
                ],
            },
            "mid-body": {
                "labels": circ_labels,
                "datasets": [
                    {"label": str(_("دور شکم")), "data": aligned("abdomen_cm")},
                    {"label": str(_("دور کمر")), "data": aligned("waist_cm")},
                    {"label": str(_("دور باسن")), "data": aligned("hips_cm")},
                ],
            },
            "arms": {
                "labels": circ_labels,
                "datasets": [
                    {"label": str(_("بازو آزاد")), "data": aligned("arm_rest_cm")},
                    {"label": str(_("بازو منقبض")), "data": aligned("arm_flexed_cm")},
                ],
            },
            "wrist-forearm": {
                "labels": circ_labels,
                "datasets": [
                    {"label": str(_("دور مچ دست")), "data": aligned("wrist_cm")},
                    {"label": str(_("دور ساعد")), "data": aligned("forearm_cm")},
                ],
            },
            "thigh": {
                "labels": circ_labels,
                "datasets": [
                    {"label": str(_("دور ران")), "data": aligned("thigh_cm")},
                    {"label": str(_("دور ران (چپ)")), "data": aligned("thigh_left_cm")},
                ],
            },
            "calf": {
                "labels": circ_labels,
                "datasets": [
                    {"label": str(_("دور ساق پا")), "data": aligned("calf_cm")},
                    {"label": str(_("دور ساق پا (چپ)")), "data": aligned("calf_left_cm")},
                ],
            },
        }

        # --- History table (latest first) --------------------------------------
        history_rows = []
        for record in reversed(circ_records):
            weight = record.weight_kg or user.weight_kg
            height = record.height_cm or user.height_cm
            bmi = calculate_bmi(weight, height)
            paired = self._find_caliper_for_datetime(user, record.recorded_at, caliper_records=cal_records)
            fat = self._body_fat_from_measurements(
                caliper=paired,
                circumference=record,
                height_cm=height,
                age=age,
                gender=gender,
                formula=selected_body_fat_formula,
            )
            lean = self._lean_mass_from_user(user, fat) if fat is not None else None
            history_rows.append(
                {
                    "date": jdate(record),
                    "bmi": bmi if bmi is not None else "—",
                    "fat_percent": round(float(fat), 1) if fat is not None else "—",
                    "lean_mass": lean if lean is not None else "—",
                }
            )

        # --- Gauges ------------------------------------------------------------
        bmi_now = calculate_bmi(user.weight_kg, user.height_cm)
        latest_circ = circ_records[-1] if circ_records else None
        whr_now = self._whr_from_circumference(latest_circ) if latest_circ else None

        def clamp_pct(value: float) -> int:
            return int(max(2, min(98, value)))

        gauges = {
            "bmi": {
                "value": bmi_now,
                "category": bmi_category_label(bmi_now) if bmi_now is not None else None,
                "pct": clamp_pct((bmi_now - 15) / 25 * 100) if bmi_now is not None else 0,
                "has_value": bmi_now is not None,
            },
            "whr": {
                "value": round(whr_now, 2) if whr_now is not None else None,
                "status": calculate_whr_status(whr_now, gender) if whr_now is not None else None,
                "pct": clamp_pct((whr_now - 0.7) / 0.4 * 100) if whr_now is not None else 0,
                "has_value": whr_now is not None,
            },
        }

        # --- Headline body stat cards (latest values) --------------------------
        latest = circ_records[-1] if circ_records else None
        stat_cards = []

        def add_card(icon, label, value, unit):
            if value not in (None, ""):
                stat_cards.append({"icon": icon, "label": label, "value": value, "unit": unit})

        cm = str(_("سانتی‌متر"))
        add_card("weight", _("وزن"), (latest.weight_kg if latest and latest.weight_kg else user.weight_kg), str(_("کیلوگرم")))
        add_card("height", _("قد"), (latest.height_cm if latest and latest.height_cm else user.height_cm), cm)
        if latest:
            add_card("waist", _("دور کمر"), latest.waist_cm, cm)
            add_card("hip", _("دور باسن"), latest.hips_cm, cm)
            add_card("chest", _("دور سینه"), latest.chest_cm, cm)
            add_card("arm", _("دور بازو منقبض"), latest.arm_flexed_cm, cm)

        return {
            "analysis_trend_charts": trend_charts,
            "analysis_measurement_groups": measurement_groups,
            "analysis_history_rows": history_rows,
            "analysis_gauges": gauges,
            "analysis_stat_cards": stat_cards,
            "analysis_has_chart_data": any(chart["values"] for chart in trend_charts.values()),
        }

    def get_learning_courses(self, user):
        return UserSelector.get_learning_courses(user)

    def get_paid_orders(self, user):
        return UserSelector.get_paid_orders(user)

    def get_comments(self, user):
        return UserSelector.get_user_comments(user)

    def get_notifications_feed(self, user):
        return self.notification_service.get_profile_notifications(user)

    def request_phone_change(self, *, user, new_phone: str, session, otp_creator=None) -> str:
        if self.user_repository.phone_exists(new_phone, exclude_user_id=user.pk):
            raise PhoneAlreadyExistsException(_("این شماره تماس قبلا ثبت شده است."))

        if otp_creator is None:
            from account.services import create_and_send_otp as otp_creator  # Lazy import to avoid cycles.

        token = otp_creator(new_phone)
        self.session_service.set_pending_phone_change(session, token=token, phone=new_phone)
        return token

    @transaction.atomic
    def confirm_phone_change(self, *, user, token: str, code: int, session):
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

    def request_password_reset(self, *, phone: str, session, otp_creator=None) -> str:
        try:
            self.user_repository.get_by_phone(phone)
        except User.DoesNotExist as exc:
            raise PasswordResetException(_("حسابی با این شماره تماس پیدا نشد.")) from exc
        if otp_creator is None:
            from account.services import create_and_send_otp as otp_creator  # Lazy import to avoid cycles.

        token = otp_creator(phone)
        self.session_service.set_password_reset_token(session, token=token)
        return token

    @transaction.atomic
    def confirm_password_reset(self, *, token: str, code: int, new_password: str, session):
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
    def update_profile(self, *, form):
        return form.save()

    def update_profile_metric(self, *, user, field_name: str, value):
        setattr(user, field_name, value)
        user.save(update_fields=[field_name])
        return user

    @transaction.atomic
    def add_free_course_to_profile(self, *, user, series_id: int, series=None):
        from home.models import UserCourse

        series = series or CourseSelector.get_free_series(series_id)
        if series is None:
            raise AuthenticationException(_("دوره مورد نظر یافت نشد."))
        return UserCourse.objects.get_or_create(user=user, series=series)

    def create_course_request_notification(self, *, user, course):
        return self.notification_service.create_course_request_notification(user=user, course_title=course.title)
