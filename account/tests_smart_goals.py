from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from account.models import BodyCircumferenceMeasurement, CaliperMeasurement, User
from account.services.profile_analysis_service import ProfileAnalysisService


class SmartGoalTests(TestCase):
    def _create_user(self, *, fullname, phone, weight, height, gender="male"):
        return User.objects.create_user(
            fullname=fullname,
            phone=phone,
            password="StrongPass123",
            weight_kg=weight,
            height_cm=height,
            birth_date_jalali="1370/02/12",
            gender=gender,
            activity_level="moderate_active",
        )

    def _add_test_pair(self, user, *, days_ago, weight, waist, hips, abdomen, chest, thigh):
        measured_at = timezone.now() - timedelta(days=days_ago)
        circumference = BodyCircumferenceMeasurement.objects.create(
            user=user,
            weight_kg=weight,
            height_cm=user.height_cm,
            waist_cm=waist,
            hips_cm=hips,
        )
        caliper = CaliperMeasurement.objects.create(
            user=user,
            chest_armpit_men_mm=chest,
            abdominal_mm=abdomen,
            thigh_mm=thigh,
        )
        circumference.recorded_at = measured_at
        circumference.save(update_fields=["recorded_at"])
        caliper.recorded_at = measured_at
        caliper.save(update_fields=["recorded_at"])

    def test_overfat_profile_gets_loss_goal_and_test_path(self):
        user = self._create_user(
            fullname="smart_goal_loss",
            phone="09127770001",
            weight=92,
            height=180,
        )
        self._add_test_pair(
            user,
            days_ago=60,
            weight=96,
            waist=106,
            hips=104,
            abdomen=38,
            chest=28,
            thigh=30,
        )
        self._add_test_pair(
            user,
            days_ago=10,
            weight=92,
            waist=100,
            hips=103,
            abdomen=34,
            chest=25,
            thigh=27,
        )

        payload = ProfileAnalysisService().get_analysis_dashboard_data(user)["analysis_smart_goal"]

        self.assertTrue(payload["available"])
        self.assertEqual(payload["goal_type"], "loss")
        self.assertEqual(len(payload["metrics"]), 4)
        self.assertEqual(len(payload["timeline_rows"]), 2)
        self.assertTrue(payload["has_chart_data"])
        self.assertLess(payload["metrics"][0]["target"], payload["metrics"][0]["current"])

    def test_underweight_profile_gets_gain_goal(self):
        user = self._create_user(
            fullname="smart_goal_gain",
            phone="09127770002",
            weight=50,
            height=180,
        )
        self._add_test_pair(
            user,
            days_ago=5,
            weight=50,
            waist=68,
            hips=84,
            abdomen=10,
            chest=8,
            thigh=9,
        )

        payload = ProfileAnalysisService().get_analysis_dashboard_data(user)["analysis_smart_goal"]

        self.assertTrue(payload["available"])
        self.assertEqual(payload["goal_type"], "gain")
        self.assertGreater(payload["metrics"][0]["target"], payload["metrics"][0]["current"])

    def test_profile_analysis_renders_smart_goal_section(self):
        user = self._create_user(
            fullname="smart_goal_page",
            phone="09127770003",
            weight=92,
            height=180,
        )
        self._add_test_pair(
            user,
            days_ago=2,
            weight=92,
            waist=100,
            hips=103,
            abdomen=34,
            chest=25,
            thigh=27,
        )
        self.client.force_login(user)

        response = self.client.get(reverse("register:profile_analysis"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "analysis-smart-goal")
        self.assertContains(response, "هدف‌گذاری هوشمند")
        self.assertContains(response, "analysis-goal-data")
