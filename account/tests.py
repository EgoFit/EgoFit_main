from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from account.domain.body_composition.calculator import (
    CaliperSkinfolds,
    CircumferenceMeasures,
    build_body_composition_snapshot,
    calculate_body_fat_from_caliper,
    calculate_body_fat_from_circumference_navy,
    calculate_bmi,
    calculate_bmr_mifflin_st_jeor,
    calculate_calories_for_weight_gain,
    calculate_calories_for_weight_loss,
    calculate_lean_mass,
    calculate_protein_range,
    calculate_whr,
    calculate_whtr,
    calculate_whtr_status,
)
from account.admin import NotificationAdminForm
from account.models import Notification, Otp, User
from account.services import ProfileService, send_notification_sms_broadcast
from cart.models import Order, OrderItem
from home.models import Category, Comment, CommentSectionModel, Reply, SeriesModel, UserCourse


class AccountAccessTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(phone="09123333333", fullname="account_user")
        self.user.set_password("StrongPass123")
        self.user.save()
        self.category = Category.objects.create(title="Programming", slug="programming")
        self.image = SimpleUploadedFile("course.png", b"filecontent", content_type="image/png")

    def _create_series(self, *, title="Course 1", free=False):
        phone_suffix = abs(hash(title)) % 10000000
        author_phone = f"0912{phone_suffix:07d}"
        author = User.objects.create(phone=author_phone, fullname=f"author_{title}")
        return SeriesModel.objects.create(
            title=title,
            image=SimpleUploadedFile(f"{title}.png", b"filecontent", content_type="image/png"),
            is_compeleted=True,
            language_kinds=self.category,
            author=author,
            main_price="100000",
            discount_price="80000",
            free=free,
        )

    def test_profile_requires_authentication(self):
        response = self.client.get(reverse("register:profile"))

        self.assertEqual(response.status_code, 302)

    def test_password_login_page_renders(self):
        response = self.client.get(reverse("register:pass_login"))

        self.assertEqual(response.status_code, 200)

    def test_phone_login_page_renders(self):
        response = self.client.get(reverse("register:register"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "auth-mobile-screen")

    @patch("account.services.SmsService.send_verification_sms", return_value=True)
    def test_create_and_send_otp_sends_without_waiting_for_task_worker(self, mocked_send_sms):
        from account.services import create_and_send_otp

        token = create_and_send_otp("09121112233")

        otp = Otp.objects.get(token=token)
        mocked_send_sms.assert_called_once_with(otp.phone, otp.code)

    @patch("account.views.create_and_send_otp", return_value="login-token")
    def test_phone_login_accepts_persian_digits(self, mocked_send_otp):
        response = self.client.post(
            reverse("register:register"),
            {"phone": "۰۹۱۲۳۴۵۶۷۸۹"},
        )

        self.assertRedirects(response, reverse("register:verification") + "?token=login-token")
        mocked_send_otp.assert_called_once_with("09123456789")

    @patch("account.views.create_and_send_otp", return_value="login-token")
    def test_phone_login_accepts_spaced_local_number(self, mocked_send_otp):
        response = self.client.post(
            reverse("register:register"),
            {"phone": "912 345 6789"},
        )

        self.assertRedirects(response, reverse("register:verification") + "?token=login-token")
        mocked_send_otp.assert_called_once_with("09123456789")

    def test_verification_page_renders(self):
        response = self.client.get(reverse("register:verification"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "auth-mobile-screen")

    def test_profile_dashboard_renders_shell(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("register:profile"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "account-bottom-nav")
        self.assertContains(response, "پروفایل")
        self.assertContains(response, "profile-settings-hub")

    def test_profile_dashboard_direct_trailing_slash_url_renders(self):
        self.client.force_login(self.user)

        response = self.client.get("/accounts/profile/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "پروفایل")

    def test_profile_courses_page_renders_shell(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("register:profile_course"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "account-bottom-nav")
        self.assertContains(response, "برنامه شما")

    def test_profile_analysis_page_renders_shell(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("register:profile_analysis"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "account-bottom-nav")
        self.assertContains(response, "آنالیز")

    def test_profile_weight_edit_page_renders_compact_sheet(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("register:profile_weight_edit"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "metric-sheet")
        self.assertNotContains(response, "account-bottom-nav")

    def test_profile_blood_group_edit_page_renders_compact_sheet(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("register:profile_blood_group_edit"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "blood-group-grid")
        self.assertNotContains(response, "account-bottom-nav")

    def test_profile_edit_page_renders_shell(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("register:profile_useredit"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "account-bottom-nav")
        self.assertContains(response, "ویرایش پروفایل")

    def test_number_edit_page_renders_shell(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("register:profile_number_edit"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "account-bottom-nav")
        self.assertContains(response, "ویرایش شماره تماس")

    def test_change_password_page_renders_shell(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("register:change_password"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "account-bottom-nav")
        self.assertContains(response, "تغییر رمز عبور")

    def test_profile_coach_page_renders_left_leg_fields(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("register:profile_coach"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "دور ران (چپ)")
        self.assertContains(response, "دور ساق پا (چپ)")

    def test_dashboard_context_includes_summary_cards(self):
        free_series = self._create_series(title="free-course", free=True)
        paid_series = self._create_series(title="paid-course", free=False)
        UserCourse.objects.create(user=self.user, series=free_series)
        order = Order.objects.create(user=self.user, course=paid_series, subtotal_price=100000, total_price=80000, is_paid=True)
        OrderItem.objects.create(order=order, product=paid_series, price=80000)
        CommentSectionModel.objects.create(series=paid_series, user=self.user, text="Nice course")
        Notification.objects.create(user=self.user, title="Hello", message="Dashboard notification")

        context = ProfileService().get_dashboard_context(self.user)

        self.assertEqual(context["learning_courses_count"], 2)
        self.assertEqual(context["paid_orders_count"], 1)
        self.assertEqual(context["comments_count"], 1)
        self.assertEqual(len(context["dashboard_cards"]), 4)
        self.assertEqual(len(context["profile_overview_cards"]), 5)
        self.assertEqual(len(context["recent_courses"]), 2)
        self.assertEqual(len(context["recent_orders"]), 1)
        self.assertEqual(len(context["recent_comments"]), 1)

    def test_analysis_context_includes_chart_data(self):
        from account.models import CaliperMeasurement

        self.user.weight_kg = 78
        self.user.height_cm = 180
        self.user.birth_date_jalali = "1370/02/12"
        self.user.blood_group = "O+"
        self.user.gender = "male"
        self.user.save(update_fields=["weight_kg", "height_cm", "birth_date_jalali", "blood_group", "gender"])

        CaliperMeasurement.objects.create(
            user=self.user,
            chest_armpit_men_mm=12,
            abdominal_mm=22,
            thigh_mm=16,
        )
        CaliperMeasurement.objects.create(
            user=self.user,
            chest_armpit_men_mm=11,
            abdominal_mm=20,
            thigh_mm=15,
        )

        context = ProfileService().get_analysis_context(self.user)

        self.assertTrue(context["analysis_has_data"])
        self.assertTrue(context["analysis_chart_has_data"])
        self.assertGreater(len(context["analysis_chart_points"]), 0)
        self.assertIn("M ", context["analysis_chart_path"])
        self.assertIn("Z", context["analysis_chart_area_path"])


    @patch("account.views.create_and_send_otp", return_value="phone-change-token")
    def test_phone_change_requires_otp_confirmation_before_updating_phone(self, mocked_send_otp):
        self.client.force_login(self.user)
        response = self.client.post(reverse("register:profile_number_edit"), {"phone_number_new": "09124444444"})

        self.user.refresh_from_db()
        self.assertRedirects(response, reverse("register:profile_number_verify") + "?token=phone-change-token")
        self.assertEqual(self.user.phone, "09123333333")
        self.assertEqual(self.client.session.get("pending_phone_change"), "09124444444")

    def test_phone_change_verification_updates_phone_after_valid_otp(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["pending_phone_change_token"] = "verify-phone-token"
        session["pending_phone_change"] = "09124444444"
        session.save()
        Otp.objects.create(phone="09124444444", code=12345, token="verify-phone-token")

        response = self.client.post(
            reverse("register:profile_number_verify") + "?token=verify-phone-token",
            {"code": "12345"},
        )

        self.user.refresh_from_db()
        self.assertRedirects(response, reverse("register:profile_number_edit"))
        self.assertEqual(self.user.phone, "09124444444")

    @patch("account.views.create_and_send_otp", return_value="reset-token")
    def test_forgot_password_request_redirects_to_confirmation(self, mocked_send_otp):
        response = self.client.post(reverse("register:forgot_password"), {"phone": self.user.phone})

        self.assertRedirects(response, reverse("register:forgot_password_confirm") + "?token=reset-token")
        self.assertEqual(self.client.session.get("password_reset_token"), "reset-token")

    def test_forgot_password_confirm_resets_password(self):
        session = self.client.session
        session["password_reset_token"] = "reset-token"
        session.save()
        Otp.objects.create(phone=self.user.phone, code=54321, token="reset-token")

        response = self.client.post(
            reverse("register:forgot_password_confirm") + "?token=reset-token",
            {
                "code": "54321",
                "new_password1": "NewStrongPass1",
                "new_password2": "NewStrongPass1",
            },
        )

        self.user.refresh_from_db()
        self.assertRedirects(response, reverse("register:pass_login"))
        self.assertTrue(self.user.check_password("NewStrongPass1"))

    def test_notification_admin_form_requires_global_for_sms_broadcast(self):
        form = NotificationAdminForm(
            data={
                "title": "دوره جدید",
                "message": "یک دوره جدید منتشر شد.",
                "is_global": False,
                "send_sms_to_all": True,
                "read": False,
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("send_sms_to_all", form.errors)

    @patch("account.services.notification_service.SmsService.send_personalized_bulk_sms", return_value=True)
    def test_send_notification_sms_broadcast_updates_status_and_recipient_count(self, mocked_send):
        User.objects.create(phone="09121111111", fullname="account_user_2")
        User.objects.create(phone="09122222222", fullname="inactive_user", is_active=False)
        notification = Notification.objects.create(
            title="دوره جدید",
            message="یک دوره جدید روی سایت منتشر شد.",
            is_global=True,
            send_sms_to_all=True,
        )

        recipients_count = send_notification_sms_broadcast(notification)
        notification.refresh_from_db()

        self.assertEqual(recipients_count, 2)
        self.assertEqual(notification.sms_status, Notification.SmsStatus.SENT)
        self.assertEqual(notification.sms_recipients_count, 2)
        self.assertTrue(mocked_send.called)

        command = mocked_send.call_args.args[0]
        self.assertEqual(len(command), 2)
        payloads = {item.receptor: item.message for item in command}
        self.assertEqual(
            payloads["09123333333"],
            "کاربر account_user عزیز\n\nیک دوره جدید روی سایت منتشر شد.",
        )

    def test_send_notification_sms_broadcast_marks_failed_without_recipients(self):
        User.objects.all().update(is_active=False)
        notification = Notification.objects.create(
            title="اعلان عمومی",
            message="متن اعلان",
            is_global=True,
            send_sms_to_all=True,
        )

        recipients_count = send_notification_sms_broadcast(notification)
        notification.refresh_from_db()

        self.assertEqual(recipients_count, 0)
        self.assertEqual(notification.sms_status, Notification.SmsStatus.FAILED)

    @override_settings(DEBUG=False)
    def test_custom_404_page_renders(self):
        response = self.client.get("/missing-page/")

        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "خطای ۴۰۴", status_code=404)


class AdminPortalTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create(phone="09120000001", fullname="admin_user", is_admin=True)
        self.admin.set_password("StrongPass123")
        self.admin.save()
        self.client_user = User.objects.create(phone="09120000002", fullname="client_user")

    def test_admin_login_redirects_to_admin_search(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("register:profile"), follow=False)
        self.assertRedirects(response, reverse("register:admin_search"))

    def test_admin_search_page_renders(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("register:admin_search"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "جست و جو کاربر")
        self.assertContains(response, "admin-bottom-nav")

    def test_admin_password_change_updates_password(self):
        self.client.force_login(self.admin)
        new_password = "NewStrongPass1234567890"

        response = self.client.post(
            reverse("register:admin_password_change"),
            {
                "old_password": "StrongPass123",
                "new_password1": new_password,
                "new_password2": new_password,
            },
        )

        self.admin.refresh_from_db()
        self.assertRedirects(response, reverse("register:admin_search"))
        self.assertTrue(self.admin.check_password(new_password))

    def test_non_admin_cannot_access_admin_panel(self):
        self.client.force_login(self.client_user)
        response = self.client.get(reverse("register:admin_search"))
        self.assertRedirects(response, reverse("register:profile"))

    def test_admin_can_search_users(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("register:admin_search"), {"query": "client"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "client_user")

    def test_admin_user_hub_renders(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("register:admin_user_hub", args=[self.client_user.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ثبت اطلاعات شخصی")

    def test_otp_login_redirects_admin_to_admin_panel(self):
        Otp.objects.create(phone=self.admin.phone, code=12345, token="admin-login-token")
        response = self.client.post(
            reverse("register:verification") + "?token=admin-login-token",
            {"code": "12345"},
        )
        self.assertRedirects(response, reverse("register:admin_search"))

    def test_search_cta_links_to_user_hub(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("register:admin_search"), {"query": "client"})
        self.assertContains(response, reverse("register:admin_user_hub", args=[self.client_user.pk]))

    def test_analysis_chart_visible_with_default_dates(self):
        from account.models import CaliperMeasurement

        self.client_user.height_cm = 180
        self.client_user.weight_kg = 78
        self.client_user.gender = "male"
        self.client_user.birth_date_jalali = "1370/02/12"
        self.client_user.save(update_fields=["height_cm", "weight_kg", "gender", "birth_date_jalali"])
        CaliperMeasurement.objects.create(
            user=self.client_user,
            chest_armpit_men_mm=12,
            abdominal_mm=22,
            thigh_mm=16,
        )
        CaliperMeasurement.objects.create(
            user=self.client_user,
            chest_armpit_men_mm=11,
            abdominal_mm=20,
            thigh_mm=15,
        )
        self.client.force_login(self.admin)
        response = self.client.get(reverse("register:admin_user_analysis", args=[self.client_user.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "analysis-chart-card")

    def test_analysis_body_fat_formula_selection_updates_history_table(self):
        from account.models import BodyCircumferenceMeasurement, CaliperMeasurement

        self.client_user.height_cm = 180
        self.client_user.weight_kg = 78
        self.client_user.gender = "male"
        self.client_user.birth_date_jalali = "1370/02/12"
        self.client_user.save(update_fields=["height_cm", "weight_kg", "gender", "birth_date_jalali"])
        BodyCircumferenceMeasurement.objects.create(
            user=self.client_user,
            measured_at_jalali="1404/01/10",
            height_cm=180,
            weight_kg=78,
            waist_cm=82,
            neck_cm=38,
            hips_cm=96,
        )
        CaliperMeasurement.objects.create(
            user=self.client_user,
            measured_at_jalali="1404/01/10",
            chest_mm=10,
            axilla_mm=12,
            triceps_mm=18,
            subscapular_mm=14,
            abdominal_mm=20,
            suprailiac_mm=16,
            thigh_mm=22,
        )

        service = ProfileService()
        context = service.get_analysis_context(
            self.client_user,
            circ_date="1404/01/10",
            body_fat_formula="jp4",
            use_full_chart_range=True,
        )
        dashboard = service.get_analysis_dashboard_data(self.client_user, body_fat_formula="jp4")

        self.assertEqual(context["analysis_selected_body_fat_formula"], "jp4")
        self.assertEqual(context["analysis_formula_used"], "Jackson-Pollock 4-site")
        self.assertEqual(dashboard["analysis_history_rows"][0]["fat_percent"], context["analysis_result_tiles"][0]["value"])

        self.client.force_login(self.admin)
        response = self.client.get(
            reverse("register:admin_user_analysis", args=[self.client_user.pk]),
            {"circ_date": "1404/01/10", "body_fat_formula": "jp4"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="body_fat_formula"')
        self.assertContains(response, "Jackson-Pollock 4-site")

    def test_analysis_filter_by_metric(self):
        self.client_user.height_cm = 180
        self.client_user.weight_kg = 78
        self.client_user.save(update_fields=["height_cm", "weight_kg"])
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse("register:admin_user_analysis", args=[self.client_user.pk]),
            {"metric": "bmi", "start": "1403/01/01", "end": "1404/12/29"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "BMI")
        self.assertContains(response, 'name="metric" value="bmi"', html=False)

    def test_role_toggle_promotes_user(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("register:admin_role_toggle", args=[self.client_user.pk]),
            {"is_admin": "on"},
        )
        self.client_user.refresh_from_db()
        self.assertTrue(self.client_user.is_admin)
        self.assertRedirects(
            response,
            f"{reverse('register:admin_search')}?query={self.client_user.fullname}",
        )

    def test_circumference_save_shows_flash_message(self):
        from account.models import BodyCircumferenceMeasurement

        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("register:admin_circumference", args=[self.client_user.pk]),
            {
                "waist_cm": "82.5",
                "hips_cm": "98.0",
            },
        )
        self.assertRedirects(response, reverse("register:admin_user_hub", args=[self.client_user.pk]))
        follow = self.client.get(reverse("register:admin_user_hub", args=[self.client_user.pk]))
        self.assertContains(follow, "admin-toast")
        self.assertTrue(BodyCircumferenceMeasurement.objects.filter(user=self.client_user).exists())

    def test_circumference_form_renders_left_leg_fields(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("register:admin_circumference", args=[self.client_user.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "دور ران پا (چپ)")
        self.assertContains(response, "دور ساق پا (چپ)")


class AdminUserListViewTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create(phone="09120000003", fullname="admin_user2", is_admin=True)
        self.admin.set_password("StrongPass123")
        self.admin.save()
        self.coach = User.objects.create(phone="09120000004", fullname="coach_user", is_admin=True)
        for i in range(25):
            User.objects.create(phone=f"0912000{1000 + i}", fullname=f"client_{i:02d}", coach=self.coach)

    def test_user_list_requires_admin(self):
        non_admin = User.objects.create(phone="09120000005", fullname="plain_user")
        self.client.force_login(non_admin)
        response = self.client.get(reverse("register:admin_user_list"))
        self.assertRedirects(response, reverse("register:profile"))

    def test_user_list_paginates(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("register:admin_user_list"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["is_paginated"])
        self.assertEqual(len(response.context["clients"]), 20)

    def test_user_list_filters_by_query(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("register:admin_user_list"), {"query": "client_00"})
        self.assertContains(response, "client_00")
        self.assertNotContains(response, "client_01")

    def test_user_list_sorts_by_coach(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("register:admin_user_list"), {"sort": "coach"})
        self.assertEqual(response.status_code, 200)


class ExerciseLookupCrudTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create(phone="09120000006", fullname="admin_user3", is_admin=True)
        self.admin.set_password("StrongPass123")
        self.admin.save()

    def test_lookup_list_renders_for_valid_key(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("register:admin_lookup_list", args=["body-part"]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "بالاتنه")

    def test_lookup_list_404_for_unknown_key(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("register:admin_lookup_list", args=["not-a-real-key"]))
        self.assertEqual(response.status_code, 404)

    def test_gym_library_list_shows_twenty_items_and_supports_page_size(self):
        from account.models import Muscle

        Muscle.objects.bulk_create([Muscle(name=f"عضله {index:02d}") for index in range(25)])
        self.client.force_login(self.admin)

        response = self.client.get(reverse("register:admin_muscle_list"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["is_paginated"])
        self.assertEqual(len(response.context["muscles"]), 20)
        self.assertEqual(response.context["page_size"], 20)

        response = self.client.get(reverse("register:admin_muscle_list"), {"page_size": 10, "page": 2})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["muscles"]), 10)
        self.assertEqual(response.context["page_size"], 10)

    def test_lookup_add_creates_row(self):
        from account.models import ExerciseEquipmentType

        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("register:admin_lookup_add", args=["equipment-type"]),
            {"name": "کش مقاومتی"},
        )
        self.assertRedirects(response, reverse("register:admin_lookup_list", args=["equipment-type"]))
        self.assertTrue(ExerciseEquipmentType.objects.filter(name="کش مقاومتی").exists())

    def test_lookup_delete_blocked_when_in_use(self):
        from account.models import Exercise, ExerciseBodyPart, ExerciseDifficultyLevel, ExerciseEquipmentType, ExerciseJointType, ExerciseMovementType, ExercisePowerType, Muscle

        muscle = Muscle.objects.create(name="جلو بازو")
        body_part = ExerciseBodyPart.objects.get(name="بالاتنه")
        exercise = Exercise.objects.create(
            name="جلو بازو هالتر",
            primary_muscle=muscle,
            body_part=body_part,
            movement_type=ExerciseMovementType.objects.get(name="کشیدن"),
            joint_type=ExerciseJointType.objects.get(name="تک‌مفصلی"),
            power_type=ExercisePowerType.objects.get(name="قدرتی"),
            difficulty_level=ExerciseDifficultyLevel.objects.get(name="مبتدی"),
            equipment_type=ExerciseEquipmentType.objects.get(name="وزنه آزاد"),
        )
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("register:admin_lookup_delete", args=["body-part", body_part.pk]),
            follow=True,
        )
        self.assertContains(response, "قابل حذف نیست")
        self.assertTrue(ExerciseBodyPart.objects.filter(pk=body_part.pk).exists())
        exercise.delete()
        muscle.delete()


class AdminUserCreateViewTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create(phone="09120000007", fullname="admin_user4", is_admin=True)
        self.admin.set_password("StrongPass123")
        self.admin.save()

    def test_create_user_sets_usable_password_and_redirects_to_circumference(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("register:admin_user_add"),
            {
                "first_name": "new",
                "last_name": "client",
                "phone": "09121110000",
                "password": "ClientPass123",
                "gender": "male",
            },
        )
        new_user = User.objects.get(fullname="new client")
        self.assertRedirects(response, reverse("register:admin_circumference", args=[new_user.pk]))
        self.assertTrue(new_user.check_password("ClientPass123"))
        self.assertEqual(new_user.first_name, "new")
        self.assertEqual(new_user.last_name, "client")

    def test_create_user_duplicate_phone_shows_form_error_not_500(self):
        User.objects.create(phone="09121110001", fullname="existing_client")
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("register:admin_user_add"),
            {
                "first_name": "another",
                "last_name": "client",
                "phone": "09121110001",
                "password": "ClientPass123",
                "gender": "male",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "از قبل موجود است")

    def test_create_user_duplicate_combined_name_shows_friendly_error(self):
        User.objects.create(phone="09121110099", fullname="dup name")
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("register:admin_user_add"),
            {
                "first_name": "dup",
                "last_name": "name",
                "phone": "09121110098",
                "password": "ClientPass123",
                "gender": "male",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "قبلاً ثبت شده است")


class AdminUserDeleteViewTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create(phone="09120000008", fullname="admin_user5", is_admin=True)
        self.admin.set_password("StrongPass123")
        self.admin.save()

    def test_delete_blocked_when_user_has_paid_order(self):
        from cart.models import Order

        client_user = User.objects.create(phone="09121110002", fullname="paid_client")
        Order.objects.create(user=client_user, is_paid=True)
        self.client.force_login(self.admin)
        response = self.client.post(reverse("register:admin_user_delete", args=[client_user.pk]), follow=True)
        self.assertContains(response, "قابل حذف نیست")
        self.assertTrue(User.objects.filter(pk=client_user.pk).exists())

    def test_delete_succeeds_when_no_paid_order(self):
        client_user = User.objects.create(phone="09121110003", fullname="free_client")
        self.client.force_login(self.admin)
        response = self.client.post(reverse("register:admin_user_delete", args=[client_user.pk]), follow=True)
        self.assertContains(response, "با موفقیت حذف شد")
        self.assertFalse(User.objects.filter(pk=client_user.pk).exists())


class CircumferenceHeightWeightSyncTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create(phone="09120000009", fullname="admin_user6", is_admin=True)
        self.admin.set_password("StrongPass123")
        self.admin.save()
        self.client_user = User.objects.create(phone="09121110004", fullname="sync_client")

    def test_submitting_height_weight_syncs_to_user(self):
        self.client.force_login(self.admin)
        self.client.post(
            reverse("register:admin_circumference", args=[self.client_user.pk]),
            {"height_cm": "182", "weight_kg": "79", "wrist_left_cm": "16.4"},
        )
        self.client_user.refresh_from_db()
        self.assertEqual(self.client_user.height_cm, 182)
        self.assertEqual(self.client_user.weight_kg, 79)
        record = self.client_user.circumference_records.first()
        self.assertEqual(str(record.wrist_left_cm), "16.40")

    def test_submitting_without_height_weight_keeps_previous_values(self):
        self.client_user.height_cm = 175
        self.client_user.weight_kg = 70
        self.client_user.save(update_fields=["height_cm", "weight_kg"])
        self.client.force_login(self.admin)
        self.client.post(reverse("register:admin_circumference", args=[self.client_user.pk]), {"waist_cm": "80"})
        self.client_user.refresh_from_db()
        self.assertEqual(self.client_user.height_cm, 175)
        self.assertEqual(self.client_user.weight_kg, 70)


class MeasurementHistoryEditTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create(phone="09120000010", fullname="admin_user7", is_admin=True)
        self.admin.set_password("StrongPass123")
        self.admin.save()
        self.client_user = User.objects.create(phone="09121110005", fullname="history_client")
        self.other_user = User.objects.create(phone="09121110006", fullname="other_client")

    def test_history_lists_circumference_and_caliper_entries(self):
        from account.models import BodyCircumferenceMeasurement, CaliperMeasurement

        BodyCircumferenceMeasurement.objects.create(user=self.client_user, measured_at_jalali="1403/01/10", waist_cm=80)
        CaliperMeasurement.objects.create(user=self.client_user, measured_at_jalali="1403/02/05", chest_mm=10)
        self.client.force_login(self.admin)
        response = self.client.get(reverse("register:admin_measurement_history", args=[self.client_user.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "1403/01/10")
        self.assertContains(response, "1403/02/05")

    def test_edit_view_updates_existing_row_not_inserts_new_one(self):
        from account.models import BodyCircumferenceMeasurement

        record = BodyCircumferenceMeasurement.objects.create(user=self.client_user, measured_at_jalali="1403/01/10", waist_cm=80)
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("register:admin_circumference_edit", args=[self.client_user.pk, record.pk]),
            {"measured_at_jalali": "1403/01/12", "waist_cm": "85"},
        )
        self.assertRedirects(response, reverse("register:admin_measurement_history", args=[self.client_user.pk]))
        self.assertEqual(BodyCircumferenceMeasurement.objects.filter(user=self.client_user).count(), 1)
        record.refresh_from_db()
        self.assertEqual(str(record.waist_cm), "85.00")
        self.assertEqual(record.measured_at_jalali, "1403/01/12")

    def test_edit_view_404_for_another_users_record(self):
        from account.models import BodyCircumferenceMeasurement

        record = BodyCircumferenceMeasurement.objects.create(user=self.other_user, waist_cm=80)
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse("register:admin_circumference_edit", args=[self.client_user.pk, record.pk])
        )
        self.assertEqual(response.status_code, 404)


class AdminPersonalInfoNameSplitAgeTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create(phone="09120000011", fullname="admin_user8", is_admin=True)
        self.admin.set_password("StrongPass123")
        self.admin.save()
        self.client_user = User.objects.create(phone="09121110010", fullname="old name")

    def test_saving_first_last_name_recomputes_fullname(self):
        self.client.force_login(self.admin)
        self.client.post(
            reverse("register:admin_personal_info", args=[self.client_user.pk]),
            {"first_name": "new", "last_name": "name", "phone": self.client_user.phone, "gender": "male"},
        )
        self.client_user.refresh_from_db()
        self.assertEqual(self.client_user.first_name, "new")
        self.assertEqual(self.client_user.last_name, "name")
        self.assertEqual(self.client_user.fullname, "new name")

    def test_saving_birth_date_computes_age_automatically(self):
        import jdatetime

        today = jdatetime.date.today()
        birth_date = f"{today.year - 20}/{today.month:02d}/{today.day:02d}"
        self.client.force_login(self.admin)
        self.client.post(
            reverse("register:admin_personal_info", args=[self.client_user.pk]),
            {
                "first_name": "old",
                "last_name": "name",
                "phone": self.client_user.phone,
                "gender": "male",
                "birth_date_jalali": birth_date,
            },
        )
        self.client_user.refresh_from_db()
        self.assertEqual(self.client_user.age, 20)


class CircumferenceSitHeightLegLengthTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create(phone="09120000012", fullname="admin_user9", is_admin=True)
        self.admin.set_password("StrongPass123")
        self.admin.save()
        self.client_user = User.objects.create(phone="09121110011", fullname="leg_client")

    def test_sit_height_and_leg_length_round_trip(self):
        self.client.force_login(self.admin)
        self.client.post(
            reverse("register:admin_circumference", args=[self.client_user.pk]),
            {"sit_height_cm": "88.5", "leg_length_cm": "95.2"},
        )
        record = self.client_user.circumference_records.first()
        self.assertEqual(str(record.sit_height_cm), "88.50")
        self.assertEqual(str(record.leg_length_cm), "95.20")

    def test_caliper_form_shows_renamed_labels(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("register:admin_caliper", args=[self.client_user.pk]))
        self.assertContains(response, "سینه")
        self.assertContains(response, "شکم")
        self.assertContains(response, "سه‌تیغ خاصره")
        self.assertContains(response, "جلوبازو")


class LookupAndExerciseNewFieldsTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create(phone="09120000013", fullname="admin_user10", is_admin=True)
        self.admin.set_password("StrongPass123")
        self.admin.save()

    def test_lookup_name_en_persists_and_displays(self):
        self.client.force_login(self.admin)
        self.client.post(
            reverse("register:admin_lookup_add", args=["equipment-type"]),
            {"name": "دمبل", "name_en": "Dumbbell"},
        )
        from account.models import ExerciseEquipmentType

        item = ExerciseEquipmentType.objects.get(name="دمبل")
        self.assertEqual(item.name_en, "Dumbbell")
        response = self.client.get(reverse("register:admin_lookup_list", args=["equipment-type"]))
        self.assertContains(response, "Dumbbell")

    def test_new_lookups_persist_name_en_and_show_in_list(self):
        from account.models import ExerciseAbnormalityType, ExerciseExecutionEquipmentType, ExerciseSecondaryMovementType

        self.client.force_login(self.admin)
        cases = [
            ("abnormality-type", "گرد شانه", "Rounded Shoulders", ExerciseAbnormalityType),
            ("secondary-movement-type", "کششی", "Pull", ExerciseSecondaryMovementType),
            ("execution-equipment-type", "هالتر", "Barbell", ExerciseExecutionEquipmentType),
        ]
        for key, name_fa, name_en, model in cases:
            self.client.post(reverse("register:admin_lookup_add", args=[key]), {"name": name_fa, "name_en": name_en})
            item = model.objects.get(name=name_fa)
            self.assertEqual(item.name_en, name_en)
            response = self.client.get(reverse("register:admin_lookup_list", args=[key]))
            self.assertContains(response, name_en)

    def test_exercise_dropdown_fields_persist(self):
        from account.models import (
            Exercise,
            ExerciseBodyPart,
            ExerciseDifficultyLevel,
            ExerciseEquipmentType,
            ExerciseExecutionEquipmentType,
            ExerciseJointType,
            ExerciseMovementType,
            ExercisePowerType,
            ExercisePressureType,
            ExerciseSecondaryMovementType,
            Muscle,
        )

        muscle, _ = Muscle.objects.get_or_create(name="جلو بازو")
        body_part, _ = ExerciseBodyPart.objects.get_or_create(name="بازو")
        movement_type, _ = ExerciseMovementType.objects.get_or_create(name="ترکیبی")
        joint_type, _ = ExerciseJointType.objects.get_or_create(name="تک مفصلی")
        power_type, _ = ExercisePowerType.objects.get_or_create(name="کششی")
        difficulty, _ = ExerciseDifficultyLevel.objects.get_or_create(name="متوسط")
        equipment, _ = ExerciseEquipmentType.objects.get_or_create(name="دمبل")
        execution_equipment, _ = ExerciseExecutionEquipmentType.objects.get_or_create(name="هالتر")
        secondary_movement, _ = ExerciseSecondaryMovementType.objects.get_or_create(name="فشاری")
        pressure, _ = ExercisePressureType.objects.get_or_create(name="وزنه")

        self.client.force_login(self.admin)
        self.client.post(
            reverse("register:admin_exercise_add"),
            {
                "name": "جلو بازو دمبل",
                "primary_muscle": muscle.pk,
                "body_part": body_part.pk,
                "movement_type": movement_type.pk,
                "joint_type": joint_type.pk,
                "power_type": power_type.pk,
                "difficulty_level": difficulty.pk,
                "equipment_type": equipment.pk,
                "execution_equipment_type": execution_equipment.pk,
                "secondary_movement_type": secondary_movement.pk,
                "pressure_type": pressure.pk,
                "description": "حرکت پایه برای جلو بازو",
            },
        )
        exercise = Exercise.objects.get(name="جلو بازو دمبل")
        self.assertEqual(exercise.execution_equipment_type_id, execution_equipment.pk)
        self.assertEqual(exercise.secondary_movement_type_id, secondary_movement.pk)
        self.assertEqual(exercise.pressure_type_id, pressure.pk)
        self.assertEqual(exercise.description, "حرکت پایه برای جلو بازو")

    def test_two_field_lookup_set_type_round_trips(self):
        from account.models import ExerciseSetType

        self.client.force_login(self.admin)
        self.client.post(reverse("register:admin_lookup_add", args=["set-type"]), {"set_count": "3", "goal": "hypertrophy"})
        item = ExerciseSetType.objects.get(set_count="3", goal="hypertrophy")
        self.assertEqual(item.goal, "hypertrophy")
        response = self.client.get(reverse("register:admin_lookup_list", args=["set-type"]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "hypertrophy")

    def test_pressure_type_lookup_shows_on_exercise_form(self):
        from account.models import ExercisePressureType

        ExercisePressureType.objects.create(name="وزنه", name_en="Weight")
        self.client.force_login(self.admin)
        response = self.client.get(reverse("register:admin_exercise_add"))
        self.assertContains(response, 'name="pressure_type"')
        self.assertContains(response, "وزنه")

    def test_exercise_add_form_omits_removed_fields(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("register:admin_exercise_add"))
        self.assertNotContains(response, 'name="equipment_note_fa"')
        self.assertNotContains(response, 'name="sets_count"')
        self.assertNotContains(response, 'name="rest_minutes"')
        self.assertContains(response, 'name="execution_equipment_type"')
        self.assertContains(response, 'name="secondary_movement_type"')
        self.assertContains(response, 'name="description"')


class CorrectiveExerciseCrudTests(TestCase):
    def setUp(self):
        from account.models import ExerciseAbnormalityType, ExerciseEquipmentType

        self.admin = User.objects.create(phone="09120000015", fullname="admin_user12", is_admin=True)
        self.admin.set_password("StrongPass123")
        self.admin.save()
        self.abnormality, _ = ExerciseAbnormalityType.objects.get_or_create(name="گرد پشتی")
        self.equipment, _ = ExerciseEquipmentType.objects.get_or_create(name="کش")

    def test_create_edit_delete_corrective(self):
        from account.models import CorrectiveExercise

        self.client.force_login(self.admin)
        # create
        self.client.post(
            reverse("register:admin_corrective_add"),
            {
                "name": "کشش سینه",
                "equipment": self.equipment.pk,
                "abnormality_type": self.abnormality.pk,
                "description": "برای اصلاح گرد پشتی",
            },
        )
        corrective = CorrectiveExercise.objects.get(name="کشش سینه")
        self.assertEqual(corrective.abnormality_type_id, self.abnormality.pk)
        self.assertEqual(corrective.equipment_id, self.equipment.pk)
        # appears in list
        response = self.client.get(reverse("register:admin_corrective_list"))
        self.assertContains(response, "کشش سینه")
        # edit
        self.client.post(
            reverse("register:admin_corrective_edit", args=[corrective.pk]),
            {
                "name": "کشش سینه اصلاحی",
                "equipment": self.equipment.pk,
                "abnormality_type": self.abnormality.pk,
                "description": "ویرایش شد",
            },
        )
        corrective.refresh_from_db()
        self.assertEqual(corrective.name, "کشش سینه اصلاحی")
        self.assertEqual(corrective.description, "ویرایش شد")
        # delete
        self.client.post(reverse("register:admin_corrective_delete", args=[corrective.pk]))
        self.assertFalse(CorrectiveExercise.objects.filter(pk=corrective.pk).exists())

    def test_corrective_form_lists_abnormality_options(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("register:admin_corrective_add"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "گرد پشتی")


class MuscleNameEnAndCaliperRenameTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create(phone="09120000016", fullname="admin_user13", is_admin=True)
        self.admin.set_password("StrongPass123")
        self.admin.save()
        self.client_user = User.objects.create(phone="09121110020", fullname="caliper_client")

    def test_muscle_name_en_round_trips(self):
        from account.models import Muscle

        self.client.force_login(self.admin)
        self.client.post(reverse("register:admin_muscle_add"), {"name": "سینه‌ای بزرگ", "name_en": "Pectoralis Major"})
        muscle = Muscle.objects.get(name="سینه‌ای بزرگ")
        self.assertEqual(muscle.name_en, "Pectoralis Major")
        response = self.client.get(reverse("register:admin_muscle_list"))
        self.assertContains(response, "Pectoralis Major")

    def test_caliper_form_shows_renamed_labels(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("register:admin_caliper", args=[self.client_user.pk]))
        self.assertContains(response, "زیربغل")
        self.assertContains(response, "تحت کتفی")
        self.assertContains(response, "کمر")


class BirthdaySmsTests(TestCase):
    def setUp(self):
        import jdatetime

        self.admin = User.objects.create(phone="09120000014", fullname="admin_user11", is_admin=True)
        self.admin.set_password("StrongPass123")
        self.admin.save()
        today = jdatetime.date.today()
        self.birthday_user = User.objects.create(
            phone="09121110012",
            fullname="birthday_client",
            birth_date_jalali=f"1370/{today.month:02d}/{today.day:02d}",
        )
        self.client_user = User.objects.create(
            phone="09121110013",
            fullname="client_user",
        )

    @patch("account.services.admin_portal_service.SmsService.send_personalized_bulk_sms", return_value=True)
    def test_dashboard_load_does_not_send_birthday_sms(self, mocked_send):
        from account.models import BirthdaySmsLog

        self.client.force_login(self.admin)
        self.client.get(reverse("register:admin_search"))
        mocked_send.assert_not_called()
        self.assertEqual(BirthdaySmsLog.objects.filter(user=self.birthday_user).count(), 0)

        self.client.get(reverse("register:admin_search"))
        mocked_send.assert_not_called()

    @patch("account.services.admin_portal_service.SmsService.send_personalized_bulk_sms", return_value=True)
    def test_birthday_sms_service_sends_once(self, mocked_send):
        from account.models import BirthdaySmsLog
        from account.services.admin_portal_service import AdminPortalService

        service = AdminPortalService()
        service.send_pending_birthday_sms()
        self.assertEqual(mocked_send.call_count, 1)
        self.assertEqual(BirthdaySmsLog.objects.filter(user=self.birthday_user).count(), 1)

        service.send_pending_birthday_sms()
        self.assertEqual(mocked_send.call_count, 1)

    @patch("account.services.admin_portal_service.SmsService.send_personalized_bulk_sms", return_value=True)
    def test_notifications_view_lists_birthday_user(self, mocked_send):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("register:admin_notifications"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "birthday_client")

    def test_notifications_view_lists_pending_opinions_and_course_comments(self):
        category = Category.objects.create(title="Fitness", slug="fitness")
        series = SeriesModel.objects.create(
            title="تمرین پایه",
            image=SimpleUploadedFile("course.png", b"filecontent", content_type="image/png"),
            language_kinds=category,
            author=self.admin,
        )
        Comment.objects.create(
            name="مریم رضایی",
            email="maryam@example.com",
            comment="این یک نظر آزمایشی معتبر است.",
        )
        CommentSectionModel.objects.create(series=series, user=self.client_user, text="دیدگاه آزمایشی دوره")

        self.client.force_login(self.admin)
        response = self.client.get(reverse("register:admin_notifications"))

        self.assertContains(response, "مریم رضایی")
        self.assertContains(response, "دیدگاه آزمایشی دوره")

    def test_admin_can_approve_and_respond_to_opinion(self):
        opinion = Comment.objects.create(
            name="مریم رضایی",
            email="maryam@example.com",
            comment="این یک نظر آزمایشی معتبر است.",
        )
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("register:admin_comment_moderate"),
            {"kind": "opinion", "object_id": opinion.pk, "action": "approve", "response": "ممنون از نظر شما."},
        )

        self.assertRedirects(response, reverse("register:admin_notifications"))
        opinion.refresh_from_db()
        self.assertEqual(opinion.publication_status, Comment.PublicationStatus.APPROVED)
        self.assertTrue(opinion.is_active)
        self.assertEqual(opinion.admin_response, "ممنون از نظر شما.")

    def test_admin_can_reject_and_respond_to_course_comment(self):
        category = Category.objects.create(title="Fitness", slug="fitness")
        series = SeriesModel.objects.create(
            title="تمرین پایه",
            image=SimpleUploadedFile("course.png", b"filecontent", content_type="image/png"),
            language_kinds=category,
            author=self.admin,
        )
        comment = CommentSectionModel.objects.create(series=series, user=self.client_user, text="دیدگاه آزمایشی دوره")

        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("register:admin_comment_moderate"),
            {"kind": "comment", "object_id": comment.pk, "action": "reject", "response": "لطفاً متن را اصلاح کنید."},
        )

        self.assertRedirects(response, reverse("register:admin_notifications"))
        comment.refresh_from_db()
        self.assertEqual(comment.publication_status, CommentSectionModel.PublicationStatus.REJECTED)
        self.assertFalse(comment.is_active)
        self.assertTrue(Reply.objects.filter(comment=comment, user=self.admin, text="لطفاً متن را اصلاح کنید.", is_active=True).exists())


class BodyCompositionCalculatorTests(TestCase):
    def test_calculate_bmi(self):
        self.assertEqual(calculate_bmi(80, 180), 24.7)

    def test_calculate_whr(self):
        self.assertEqual(calculate_whr(82.0, 98.0), 0.84)

    def test_invalid_measurements_are_rejected(self):
        self.assertIsNone(calculate_bmi(-80, 180))
        self.assertIsNone(calculate_whr(-82, 98))
        self.assertIsNone(calculate_whtr(-82, 180))
        self.assertIsNone(calculate_lean_mass(80, 101))

    def test_whtr_uses_nice_style_bands(self):
        self.assertEqual(str(calculate_whtr_status(0.49)), "نرمال")
        self.assertEqual(str(calculate_whtr_status(0.50)), "نسبتا نامطلوب")
        self.assertEqual(str(calculate_whtr_status(0.60)), "پرخطر")

    def test_mifflin_st_jeor_male(self):
        bmr = calculate_bmr_mifflin_st_jeor(weight_kg=80, height_cm=180, age=30, gender="male")
        self.assertEqual(bmr, 1780)

    def test_mifflin_st_jeor_female(self):
        bmr = calculate_bmr_mifflin_st_jeor(weight_kg=65, height_cm=165, age=28, gender="female")
        self.assertEqual(bmr, 1380)

    def test_jackson_pollock_3_site_male(self):
        skinfolds = CaliperSkinfolds(
            chest_armpit_men_mm=12.0,
            abdominal_mm=22.0,
            thigh_mm=16.0,
        )
        result = calculate_body_fat_from_caliper(skinfolds, age=30, gender="male")
        self.assertIsNotNone(result)
        self.assertEqual(result.formula_name, "Jackson-Pollock 3-site")
        self.assertGreater(result.body_fat_percent, 5)
        self.assertLess(result.body_fat_percent, 40)

    def test_jackson_pollock_7_site_female(self):
        skinfolds = CaliperSkinfolds(
            chest_mm=10.0,
            axilla_mm=12.0,
            triceps_mm=18.0,
            subscapular_mm=14.0,
            abdominal_mm=20.0,
            suprailiac_mm=16.0,
            thigh_mm=22.0,
        )
        result = calculate_body_fat_from_caliper(skinfolds, age=27, gender="female")
        self.assertIsNotNone(result)
        self.assertEqual(result.formula_name, "Jackson-Pollock 7-site")
        self.assertGreater(result.body_fat_percent, 10)

    def test_jackson_pollock_4_site_uses_four_site_percent_equation(self):
        skinfolds = CaliperSkinfolds(
            abdominal_mm=22.0,
            triceps_mm=12.0,
            thigh_mm=16.0,
            suprailiac_mm=18.0,
        )
        result = calculate_body_fat_from_caliper(
            skinfolds,
            age=30,
            gender="male",
            formula="jp4",
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.formula_name, "Jackson-Pollock 4-site")
        self.assertIsNone(result.body_density)
        self.assertAlmostEqual(result.body_fat_percent, 16.6, places=1)

    def test_auto_caliper_selection_includes_four_site(self):
        skinfolds = CaliperSkinfolds(
            abdominal_mm=22.0,
            triceps_mm=12.0,
            thigh_mm=16.0,
            suprailiac_mm=18.0,
        )
        result = calculate_body_fat_from_caliper(skinfolds, age=30, gender="male")
        self.assertIsNotNone(result)
        self.assertEqual(result.formula_name, "Jackson-Pollock 4-site")

    def test_navy_formula_converts_metric_inputs_to_inches(self):
        result = calculate_body_fat_from_circumference_navy(
            CircumferenceMeasures(abdomen_cm=82.0, neck_cm=38.0),
            height_cm=180,
            gender="male",
        )
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result.body_fat_percent, 13.7, places=1)
        self.assertIsNone(result.body_density)

    def test_protein_and_calorie_targets_are_explicit(self):
        self.assertEqual(calculate_protein_range(80, activity_level="sedentary"), (64, 80))
        self.assertEqual(calculate_protein_range(80, activity_level="active"), (112, 160))
        self.assertEqual(calculate_calories_for_weight_loss(2500), 1900)
        self.assertEqual(calculate_calories_for_weight_gain(2500), 2800)

    def test_body_fat_requires_gender(self):
        skinfolds = CaliperSkinfolds(abdominal_mm=20.0, suprailiac_mm=18.0, thigh_mm=16.0)
        self.assertIsNone(calculate_body_fat_from_caliper(skinfolds, age=30, gender=None))

    def test_build_body_composition_snapshot(self):
        snapshot = build_body_composition_snapshot(
            weight_kg=80,
            height_cm=180,
            age=30,
            gender="male",
            skinfolds=CaliperSkinfolds(
                chest_armpit_men_mm=12.0,
                abdominal_mm=22.0,
                thigh_mm=16.0,
            ),
            circumference=CircumferenceMeasures(waist_cm=82.0, hips_cm=98.0),
        )
        self.assertIsNotNone(snapshot.body_fat_percent)
        self.assertIsNotNone(snapshot.lean_mass_kg)
        self.assertIsNotNone(snapshot.tdee)
        self.assertEqual(snapshot.calories_for_loss, snapshot.tdee - 600)
        self.assertEqual(snapshot.calories_for_gain, snapshot.tdee + 300)
        self.assertEqual(snapshot.protein_min_g, 64)
        self.assertEqual(snapshot.protein_max_g, 80)
        self.assertEqual(snapshot.whr, 0.84)
        self.assertEqual(snapshot.bmi, 24.7)


class GhasedakSmsServiceTests(TestCase):
    @override_settings(GHASEDAK_API_KEY="test-api-key", GHASEDAK_OTP_TEMPLATE="randcode")
    @patch("account.services.sms_service.requests.post")
    def test_send_verification_sms_uses_new_rest_api(self, mocked_post):
        mocked_post.return_value.json.return_value = {
            "isSuccess": True,
            "statusCode": 200,
            "message": "با موفقیت انجام شد",
            "data": {"items": [], "totalCost": 0},
        }
        mocked_post.return_value.status_code = 200

        from account.services.sms_service import SmsService

        self.assertTrue(SmsService().send_verification_sms("09306612130", 12345))
        mocked_post.assert_called_once()
        self.assertIn("/sendotpsms", mocked_post.call_args.args[0])
        payload = mocked_post.call_args.kwargs["json"]
        self.assertEqual(payload["templateName"], "randcode")
        self.assertEqual(payload["inputs"], [{"param": "param1", "value": "12345"}])

    @override_settings(GHASEDAK_API_KEY="test-api-key", GHASEDAK_OTP_TEMPLATE="randcode")
    @patch("account.services.sms_service.requests.post")
    def test_send_verification_sms_surfaces_provider_error_message(self, mocked_post):
        mocked_post.return_value.json.return_value = {
            "isSuccess": False,
            "statusCode": 401,
            "message": "شناسه IP سرویس مبدا با تنظیمات مطابقت ندارد",
            "data": None,
        }
        mocked_post.return_value.status_code = 401

        from account.exceptions import SMSProviderException
        from account.services.sms_service import SmsService

        with self.assertRaises(SMSProviderException) as exc:
            SmsService().send_verification_sms("09306612130", 12345)

        self.assertIn("IP", str(exc.exception))

    @override_settings(GHASEDAK_API_KEY="")
    @patch("account.services.sms_service._get_api_key", return_value=None)
    def test_send_verification_sms_requires_api_key(self, _mocked_api_key):
        from account.exceptions import SMSProviderException
        from account.services import sms_service
        from account.services.sms_service import SmsService

        sms_service._default_sms_client = None
        with self.assertRaises(SMSProviderException) as exc:
            SmsService().send_verification_sms("09306612130", 12345)

        self.assertIn("پیکربندی", str(exc.exception))
        sms_service._default_sms_client = None
