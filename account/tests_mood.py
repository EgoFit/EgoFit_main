from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from account.models import DailyHeartRateEntry, DailyMoodEntry, User, UserHealthRecord


class MoodAndHealthPortalTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create(phone="09120000101", fullname="mood_admin", is_admin=True)
        self.user = User.objects.create(phone="09120000102", fullname="mood_client")

    def test_user_can_create_and_update_daily_mood(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("register:profile_mood"))
        self.assertEqual(response.status_code, 200)
        entry_date = timezone.localdate().isoformat()
        payload = {
            "entry_date": entry_date,
            "anxiety_score": 4,
            "motivation_score": 8,
            "sleep_quality_score": 7,
            "training_satisfaction_score": 9,
            "resting_heart_rate_bpm": 68,
        }
        response = self.client.post(reverse("register:profile_mood"), payload)
        self.assertRedirects(response, reverse("register:profile_mood"))
        payload["anxiety_score"] = 2
        self.client.post(reverse("register:profile_mood"), payload)
        self.assertEqual(DailyMoodEntry.objects.filter(user=self.user).count(), 1)
        self.assertEqual(DailyMoodEntry.objects.get(user=self.user).anxiety_score, 2)
        self.assertEqual(DailyHeartRateEntry.objects.get(user=self.user).bpm, 68)

    def test_admin_can_crud_health_records_and_follow_mood(self):
        DailyMoodEntry.objects.create(
            user=self.user,
            entry_date=timezone.localdate(),
            anxiety_score=3,
            motivation_score=8,
            sleep_quality_score=7,
            training_satisfaction_score=9,
        )
        DailyHeartRateEntry.objects.create(user=self.user, entry_date=timezone.localdate(), bpm=68)
        self.client.force_login(self.admin)
        health_url = reverse("register:admin_health", args=[self.user.pk])
        response = self.client.get(health_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.status_code, 200)
        response = self.client.post(health_url, {"category": "injury", "title": "زانو", "details": "درد خفیف", "recorded_at": timezone.localdate().isoformat()})
        self.assertRedirects(response, health_url)
        record = UserHealthRecord.objects.get(user=self.user)
        edit_url = reverse("register:admin_health_edit", args=[self.user.pk, record.pk])
        self.client.post(edit_url, {"category": "medication", "title": "ویتامین", "details": "روزانه", "recorded_at": "2026-09-24"})
        record.refresh_from_db()
        self.assertEqual(record.category, "medication")
        delete_url = reverse("register:admin_health_delete", args=[self.user.pk, record.pk])
        self.client.post(delete_url)
        self.assertFalse(UserHealthRecord.objects.filter(pk=record.pk).exists())
