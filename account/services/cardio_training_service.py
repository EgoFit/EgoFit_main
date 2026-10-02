from __future__ import annotations

from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from account.domain.cardio_training import calculate_target_heart_rate_zones, estimate_max_heart_rate
from account.models import DailyHeartRateEntry, User
from account.services.profile_dashboard_service import ProfileDashboardService


class CardioTrainingService:
    ZONE_COPY = {
        "fat_loss": {
            "label": _("چربی‌سوزی؛ راهنمای شدت متوسط"),
            "goal": _("بازهٔ عمومی برای فعالیت هوازی با شدت متوسط"),
            "note": _("این بازه FATmax فردی را مشخص نمی‌کند؛ کاهش چربی به تراز انرژی و برنامهٔ کلی وابسته است."),
        },
        "cardiorespiratory_endurance": {
            "label": _("استقامت قلبی‌عروقی"),
            "goal": _("تمرین هوازی نسبتاً شدید تا شدید؛ شدت را تدریجی بالا ببرید."),
            "note": _("برای بسیاری از جلسه‌های پیوسته، از پایین بازه شروع کنید و پاسخ ورزشکار را بسنجید."),
        },
        "anaerobic_power": {
            "label": _("تناوب پرفشار برای هدف توان بی‌هوازی"),
            "goal": _("راهنمای شدت بالا برای بخش‌های کاری تناوبی"),
            "note": _("در اسپرینت‌های کوتاه، ضربان با تأخیر بالا می‌رود؛ توان، سرعت یا RPE معیار اصلی باشد."),
        },
    }

    def get_dashboard_context(self, user: User) -> dict:
        age = ProfileDashboardService._parse_birth_date_jalali(user.birth_date_jalali)
        if age is None:
            age = user.age

        latest_resting_entry = (
            DailyHeartRateEntry.objects.filter(user=user, entry_date__lte=timezone.localdate())
            .order_by("-entry_date", "-id")
            .first()
        )
        resting_bpm = latest_resting_entry.bpm if latest_resting_entry else None
        estimated_max_heart_rate = (
            estimate_max_heart_rate(age, user.gender)
            if age is not None and user.gender
            else None
        )
        calculation = None
        if age is not None and resting_bpm is not None:
            calculation = calculate_target_heart_rate_zones(
                age=age,
                gender=user.gender,
                resting_heart_rate_bpm=resting_bpm,
            )

        zones = []
        if calculation:
            for zone in calculation["zones"]:
                copy = self.ZONE_COPY[zone["key"]]
                zones.append(
                    {
                        **zone,
                        "label": copy["label"],
                        "goal": copy["goal"],
                        "note": copy["note"],
                    }
                )

        return {
            "age": age,
            "gender_label": user.get_gender_display() if user.gender else _("ثبت نشده"),
            "resting_entry": latest_resting_entry,
            "resting_bpm": resting_bpm,
            "max_heart_rate_bpm": calculation["max_heart_rate_bpm"] if calculation else None,
            "heart_rate_reserve_bpm": calculation["heart_rate_reserve_bpm"] if calculation else None,
            "zones": zones,
            "can_calculate": bool(calculation),
            "has_age": age is not None,
            "age_supported": age is None or 18 <= age <= 80,
            "has_gender": user.gender in {User.GenderChoices.MALE, User.GenderChoices.FEMALE},
            "has_resting_bpm": latest_resting_entry is not None,
            "resting_bpm_valid": (
                resting_bpm is None
                or estimated_max_heart_rate is None
                or resting_bpm < estimated_max_heart_rate
            ),
            "max_heart_rate_formula": (
                "206 − (0.88 × سن)" if user.gender == User.GenderChoices.FEMALE
                else "208 − (0.7 × سن)"
            ),
        }
