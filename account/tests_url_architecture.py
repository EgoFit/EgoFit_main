from django.test import SimpleTestCase
from django.urls import resolve, reverse

from account.admin_portal.views import AdminSearchView
from account.admin_portal_views import AdminSearchView as LegacyAdminSearchView
from account.profile.views import ProfileView
from account.profile_views import ProfileView as LegacyProfileView
from account.workouts.views import ProfileWorkoutProgramsView
from account.workout_views import ProfileWorkoutProgramsView as LegacyWorkoutView


class AccountFeatureArchitectureTests(SimpleTestCase):
    def test_legacy_and_feature_namespaces_keep_the_same_public_urls(self):
        self.assertEqual(reverse("register:profile"), "/accounts/profile/")
        self.assertEqual(reverse("account:profile"), "/accounts/profile/")
        self.assertEqual(reverse("register:admin_search"), "/accounts/admin/")
        self.assertEqual(reverse("account:admin_search"), "/accounts/admin/")

    def test_feature_modules_preserve_legacy_view_imports(self):
        self.assertIs(ProfileView, LegacyProfileView)
        self.assertIs(ProfileWorkoutProgramsView, LegacyWorkoutView)
        self.assertIs(AdminSearchView, LegacyAdminSearchView)

    def test_representative_feature_routes_resolve(self):
        expected_names = {
            "/accounts/profile/": "profile",
            "/accounts/profile/workout-programs/": "profile_workout_programs",
            "/accounts/admin/": "admin_search",
        }
        for route, name in expected_names.items():
            self.assertEqual(resolve(route).url_name, name)
