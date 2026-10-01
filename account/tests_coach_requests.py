from django import forms
from django.test import TestCase
from django.urls import reverse

from account.froms import CoachRequestForm
from account.models import BodyCircumferenceMeasurement, CaliperMeasurement, CoachRequest, User, UserHealthRecord
from account.services.admin_portal_service import AdminPortalService


class CoachRequestDataTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(phone="09124444444", fullname="coach_request_user")
        self.admin = User.objects.create(phone="09125555555", fullname="coach_request_admin", is_admin=True)

    def test_workout_types_render_as_touch_friendly_checkboxes(self):
        field = CoachRequestForm().fields["workout_types"]
        rendered = str(CoachRequestForm()["workout_types"])

        self.assertIsInstance(field.widget, forms.CheckboxSelectMultiple)
        self.assertEqual(field.widget.attrs["aria-describedby"], "coach-workout-types-help")
        self.assertEqual(field.widget.attrs["aria-labelledby"], "coach-workout-types-label")
        self.assertIn('id="id_workout_types"', rendered)
        self.assertEqual(rendered.count('type="checkbox"'), 6)

    def test_form_accepts_save_only_and_multiple_workout_types(self):
        form = CoachRequestForm(data={
            "sessions_per_week": "3",
            "save_only": "on",
            "workout_types": ["home", "outdoor_running", "outdoor_cycling"],
            "height_cm": "180",
            "weight_kg": "80",
            "wrist_cm": "17",
            "waist_cm": "82",
            "abdomen_cm": "85",
            "hips_cm": "98",
        })

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["workout_types"], ["home", "outdoor_running", "outdoor_cycling"])

    def test_form_accepts_training_history(self):
        form = CoachRequestForm(data={
            "sessions_per_week": "3",
            "save_only": "on",
            "training_experience_years": "5",
            "training_sports": "بدنسازی و شنا",
            "height_cm": "180",
            "weight_kg": "80",
            "wrist_cm": "17",
            "waist_cm": "82",
            "abdomen_cm": "85",
            "hips_cm": "98",
        })

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["training_experience_years"], 5)
        self.assertEqual(form.cleaned_data["training_sports"], "بدنسازی و شنا")

    def test_admin_save_copies_body_and_caliper_data_once(self):
        request = CoachRequest.objects.create(
            user=self.user,
            sessions_per_week="3",
            save_only=True,
            height_cm=180,
            weight_kg=80,
            waist_cm=82,
            chest_armpit_men_mm=12,
            abdominal_mm=22,
            thigh_mm=16,
            pain_notes="زانو درد",
            illness_notes="کم‌خونی",
        )

        result = AdminPortalService().save_coach_request_to_database(
            coach_request=request,
            uploaded_by=self.admin,
        )

        self.assertIsNotNone(result["measurements"])
        self.assertIsNotNone(result["caliper"])
        self.assertEqual(BodyCircumferenceMeasurement.objects.filter(user=self.user).count(), 1)
        self.assertEqual(CaliperMeasurement.objects.filter(user=self.user).count(), 1)
        self.assertEqual(UserHealthRecord.objects.filter(user=self.user).count(), 2)
        request.refresh_from_db()
        self.assertTrue(request.pushed_to_measurements)
        self.assertTrue(request.pushed_to_caliper)
        self.assertTrue(request.pushed_health_to_records)
        self.assertTrue(request.pushed_attachments_to_files)

        second_result = AdminPortalService().save_coach_request_to_database(
            coach_request=request,
            uploaded_by=self.admin,
        )

        self.assertIsNone(second_result["measurements"])
        self.assertIsNone(second_result["caliper"])
        self.assertEqual(BodyCircumferenceMeasurement.objects.filter(user=self.user).count(), 1)
        self.assertEqual(CaliperMeasurement.objects.filter(user=self.user).count(), 1)
        self.assertEqual(UserHealthRecord.objects.filter(user=self.user).count(), 2)

    def test_admin_user_hub_displays_request_data_and_save_action(self):
        CoachRequest.objects.create(
            user=self.user,
            sessions_per_week="3",
            save_only=True,
            workout_types=["home", "outdoor_swimming"],
            chest_armpit_men_mm=14,
            training_experience_years=5,
            training_sports="بدنسازی و شنا",
        )
        self.client.force_login(self.admin)

        response = self.client.get(reverse("register:admin_user_hub", args=[self.user.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "صرفا جهت ذخیره سازی در دیتابیس")
        self.assertContains(response, "تمرین در خانه")
        self.assertContains(response, "ذخیره اطلاعات در دیتابیس")
        self.assertContains(response, "14")
        self.assertContains(response, "سوابق تمرینی")
        self.assertContains(response, "بدنسازی و شنا")
        self.assertContains(response, "5 سال")
