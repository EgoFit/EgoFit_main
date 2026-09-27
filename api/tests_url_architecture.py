from django.test import SimpleTestCase
from django.urls import resolve, reverse

from api import views as legacy_views
from api.v1.auth import views as auth_views
from api.v1.commerce import views as commerce_views
from api.v1.content import views as content_views
from api.v1.profile import views as profile_views


class ApiFeatureArchitectureTests(SimpleTestCase):
    def test_versioned_routes_keep_existing_names_and_paths(self):
        routes = {
            "api:health": "/api/v1/health/",
            "api:me": "/api/v1/me/",
            "api:series_list": "/api/v1/courses/",
            "api:order_create": "/api/v1/orders/",
            "api:library:catalog": "/api/v1/library/",
            "api:library:exercise_list": "/api/v1/library/exercises/",
        }
        for name, path in routes.items():
            self.assertEqual(reverse(name), path)
            self.assertEqual(resolve(path).url_name, name.rsplit(":", 1)[-1])

    def test_feature_modules_preserve_legacy_handlers(self):
        self.assertIs(auth_views.login, legacy_views.login)
        self.assertIs(profile_views.me, legacy_views.me)
        self.assertIs(content_views.series_detail, legacy_views.series_detail)
        self.assertIs(commerce_views.order_payment, legacy_views.order_payment)
