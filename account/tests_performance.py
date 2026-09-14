from django.core.cache import cache
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext

from account.models import BodyCircumferenceMeasurement, CaliperMeasurement, User
from account.services.profile_service import ProfileService
from home.services.content_service import ContentService


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class ProfileQueryPerformanceTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            fullname="performance_user",
            phone="09126666666",
            password="StrongPass123",
        )
        self.user.weight_kg = 78
        self.user.height_cm = 180
        self.user.birth_date_jalali = "1370/02/12"
        self.user.gender = "male"
        self.user.save(update_fields=["weight_kg", "height_cm", "birth_date_jalali", "gender"])
        for index in range(10):
            BodyCircumferenceMeasurement.objects.create(
                user=self.user,
                weight_kg=78 + index,
                height_cm=180,
                wrist_cm=17,
                waist_cm=82 + index,
                abdomen_cm=85 + index,
                hips_cm=98 + index,
            )
            CaliperMeasurement.objects.create(
                user=self.user,
                chest_armpit_men_mm=12,
                abdominal_mm=22,
                thigh_mm=16,
            )

    def test_analysis_query_count_stays_bounded_with_multiple_measurements(self):
        with CaptureQueriesContext(connection) as queries:
            ProfileService().get_analysis_context(self.user)

        # This guards the analysis page from regressing into one query per record.
        self.assertLessEqual(len(queries), 20, [query["sql"] for query in queries])

    def test_analysis_dashboard_query_count_stays_bounded_with_multiple_measurements(self):
        with CaptureQueriesContext(connection) as queries:
            ProfileService().get_analysis_dashboard_data(self.user)

        self.assertLessEqual(len(queries), 8, [query["sql"] for query in queries])

    def test_home_context_uses_cache_after_first_load(self):
        cache.clear()
        with CaptureQueriesContext(connection) as first_load:
            ContentService.get_home_context()
        with CaptureQueriesContext(connection) as cached_load:
            ContentService.get_home_context()

        self.assertGreater(len(first_load), 0)
        self.assertEqual(len(cached_load), 0)

    def test_dynamic_home_response_is_gzip_compressed(self):
        response = self.client.get("/", HTTP_ACCEPT_ENCODING="gzip")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get("Content-Encoding"), "gzip")
        self.assertIn("Accept-Encoding", response.get("Vary", ""))
