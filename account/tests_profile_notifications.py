from django.test import TestCase
from django.urls import reverse

from account.models import Notification, NotificationDismissal, User


class ProfileNotificationDismissalTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(phone="09123334444", fullname="notification_user")
        self.client.force_login(self.user)
        self.notification = Notification.objects.create(
            user=self.user,
            title="Test notification",
            message="Notification body",
        )
        self.url = reverse("register:profile_notifications")

    def test_profile_notifications_render_a_dismiss_button(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "profile-notification__dismiss")
        self.assertContains(response, f"notification:{self.notification.pk}")

    def test_dismissing_notification_hides_it_for_the_current_user(self):
        response = self.client.post(
            self.url,
            {"notification_key": f"notification:{self.notification.pk}"},
        )

        self.assertRedirects(response, self.url)
        self.assertTrue(
            NotificationDismissal.objects.filter(
                user=self.user,
                notification_key=f"notification:{self.notification.pk}",
            ).exists()
        )
        self.assertTrue(Notification.objects.filter(pk=self.notification.pk).exists())
        self.assertNotContains(self.client.get(self.url), "Test notification")
