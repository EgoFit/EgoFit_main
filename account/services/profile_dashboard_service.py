from __future__ import annotations

from datetime import date
from typing import Any

from django.utils.translation import gettext_lazy as _

from account.domain.body_composition.calculator import calculate_bmi
from account.services.notification_service import NotificationService
from account.selectors.user_selector import UserSelector
from account.utils import is_birthday_today


class ProfileDashboardService:
    """Build the lightweight profile and dashboard payloads used by account pages."""

    def __init__(self, *, notification_service: NotificationService):
        self.notification_service = notification_service

    def get_dashboard_context(self, user: Any) -> dict[str, Any]:
        """Return dashboard cards, recent activity, and profile summaries for ``user``."""
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
                {"key": "courses", "label": _("دوره‌های من"), "value": learning_courses_count},
                {"key": "orders", "label": _("سفارش‌ها"), "value": paid_orders_count},
                {"key": "comments", "label": _("دیدگاه‌ها"), "value": comments_count},
                {"key": "notifications", "label": _("اعلان‌ها"), "value": notifications_count},
            ],
            "profile_metrics": self.get_profile_metrics(user),
            "profile_overview_cards": self.get_profile_overview_cards(user),
            "is_birthday_today": is_birthday_today(user.birth_date_jalali),
            "dashboard_feed": self.get_dashboard_feed(user, recent_notifications=recent_notifications),
        }

    def get_dashboard_feed(
        self,
        user: Any,
        *,
        recent_notifications: list[Any] | None = None,
    ) -> dict[str, Any] | None:
        """Return a birthday banner or the latest dashboard notification."""
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
    def _format_value(value: Any, suffix: str = "") -> str:
        if value in (None, ""):
            return _("ثبت نشده")
        return f"{value}{suffix}"

    @staticmethod
    def _calculate_bmi(weight_kg: int | None, height_cm: int | None) -> float | None:
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
    def _parse_birth_date_jalali(birth_date: str | None) -> int | None:
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
            return today.year - gregorian_date.year - (
                (today.month, today.day) < (gregorian_date.month, gregorian_date.day)
            )
        except Exception:
            return None

    def get_profile_metrics(self, user: Any) -> list[dict[str, Any]]:
        """Return editable profile metrics plus derived BMI and age rows."""
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

    def get_profile_overview_cards(self, user: Any) -> list[dict[str, Any]]:
        """Return the compact profile cards shown above the dashboard activity."""
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
