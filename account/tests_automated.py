"""Focused automated coverage for account models, forms, views and permissions."""

import tempfile
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import Http404, HttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse

from account.admin_forms import AdminClientDocumentForm, AdminClientMediaForm
from account.froms import FormRegister, validate_coach_request_file
from account.models import User
from cart.models import Order
from home.forms import CommentForm
from sport_shop.media_views import ResilientMediaView
from sport_shop.security_headers import SecurityHeadersMiddleware


class UserModelTests(TestCase):
    def test_create_user_normalizes_phone_and_hashes_password(self):
        user = User.objects.create_user(
            fullname="مدل آزمایشی",
            phone="912 345 6789",
            password="StrongPass123",
        )

        self.assertEqual(user.phone, "09123456789")
        self.assertTrue(user.check_password("StrongPass123"))
        self.assertNotEqual(user.password, "StrongPass123")
        self.assertTrue(user.password.startswith("pbkdf2_"))

    def test_only_active_admin_has_admin_permissions(self):
        regular = User.objects.create_user(
            fullname="کاربر مجوز",
            phone="09120000104",
            password="StrongPass123",
        )
        admin = User.objects.create_user(
            fullname="مدیر مجوز",
            phone="09120000105",
            password="StrongPass123",
            is_admin=True,
        )
        inactive_admin = User.objects.create_user(
            fullname="مدیر غیرفعال",
            phone="09120000106",
            password="StrongPass123",
            is_admin=True,
            is_active=False,
        )

        self.assertFalse(regular.has_perm("account.change_user"))
        self.assertFalse(regular.has_module_perms("account"))
        self.assertTrue(admin.has_perm("account.change_user"))
        self.assertTrue(admin.has_module_perms("account"))
        self.assertFalse(inactive_admin.has_perm("account.change_user"))
        self.assertFalse(inactive_admin.is_staff)


class OrderModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            fullname="مالک سفارش",
            phone="09120000101",
            password="StrongPass123",
        )

    def test_order_generates_number_and_transitions_through_payment_states(self):
        order = Order.objects.create(user=self.user, subtotal_price=120000, total_price=120000)

        self.assertEqual(len(order.order_number), 16)
        self.assertEqual(order.status, Order.PaymentStatus.PENDING)

        order.mark_payment_initiated("AUTH-123")
        order.refresh_from_db()
        self.assertEqual(order.status, Order.PaymentStatus.PAYMENT_INITIATED)
        self.assertEqual(order.authority, "AUTH-123")

        order.mark_paid("REF-123")
        order.refresh_from_db()
        self.assertTrue(order.is_paid)
        self.assertEqual(order.status, Order.PaymentStatus.PAID)
        self.assertEqual(order.ref_id, "REF-123")


class FormValidationTests(TestCase):
    def test_register_form_rejects_password_mismatch_and_invalid_phone(self):
        form = FormRegister(
            data={
                "fullname": "کاربر فرم",
                "password": "StrongPass123",
                "password_confirm": "DifferentPass123",
                "phone": "123",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("phone", form.errors)
        self.assertIn("password_confirm", form.errors)

    def test_contact_form_rejects_empty_required_fields(self):
        form = CommentForm(data={"comment": "", "name": "", "email": "", "phone": ""})

        self.assertFalse(form.is_valid())
        self.assertIn("comment", form.errors)
        self.assertIn("name", form.errors)
        self.assertIn("email", form.errors)

    def test_coach_request_file_allows_pdf_and_rejects_executable(self):
        allowed = SimpleUploadedFile("plan.pdf", b"%PDF-1.4", content_type="application/pdf")
        self.assertIs(validate_coach_request_file(allowed), allowed)

        executable = SimpleUploadedFile("payload.exe", b"MZ", content_type="application/x-msdownload")
        with self.assertRaises(ValidationError):
            validate_coach_request_file(executable)

    def test_upload_forms_reject_html_even_when_mime_is_spoofed(self):
        html_file = SimpleUploadedFile(
            "profile.html",
            b"<!doctype html><script>alert(1)</script>",
            content_type="image/png",
        )
        media_form = AdminClientMediaForm(files={"image": html_file})
        self.assertFalse(media_form.is_valid())
        self.assertIn("image", media_form.errors)

        document_form = AdminClientDocumentForm(
            data={"title": "فایل تست"},
            files={
                "file": SimpleUploadedFile(
                    "page.html",
                    b"<html>unsafe</html>",
                    content_type="text/html",
                )
            },
        )
        self.assertFalse(document_form.is_valid())
        self.assertIn("file", document_form.errors)

    def test_coach_request_requires_safe_extension_for_allowed_mime(self):
        spoofed = SimpleUploadedFile("payload.html", b"<html>", content_type="image/png")
        with self.assertRaises(ValidationError):
            validate_coach_request_file(spoofed)


class ViewPermissionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            fullname="کاربر عادی",
            phone="09120000102",
            password="StrongPass123",
        )
        self.admin = User.objects.create_user(
            fullname="مدیر سامانه",
            phone="09120000103",
            password="StrongPass123",
            is_admin=True,
        )

    def test_anonymous_user_is_redirected_from_profile(self):
        response = self.client.get(reverse("register:profile"))

        self.assertRedirects(
            response,
            f"{reverse('register:register')}?next={reverse('register:profile')}",
            fetch_redirect_response=False,
        )

    def test_regular_user_cannot_open_admin_portal(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("register:admin_search"))

        self.assertRedirects(response, reverse("register:profile"))

    def test_admin_can_open_admin_portal_and_regular_portal_is_restricted(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("register:admin_search"))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse("register:profile"))
        self.assertRedirects(response, reverse("register:admin_search"))

    def test_logout_removes_authenticated_session(self):
        self.client.force_login(self.user)
        self.client.get(reverse("register:logout"))

        response = self.client.get(reverse("register:profile"))
        self.assertEqual(response.status_code, 302)


class ViewBehaviorTests(TestCase):
    def test_invalid_password_login_renders_form_error_without_server_error(self):
        response = self.client.post(
            reverse("register:pass_login"),
            {"fullname": "missing-user", "password": "WrongPass123"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "نام کاربری یا کلمه عبور اشتباه است")

    def test_search_and_contact_validation_return_user_facing_responses(self):
        search_response = self.client.post(reverse("home:search"), {"search": ""})
        contact_response = self.client.post(
            reverse("home:contact_us"),
            {"comment": "", "name": "", "email": "", "phone": ""},
        )

        self.assertEqual(search_response.status_code, 200)
        self.assertEqual(contact_response.status_code, 200)


class MediaSecurityTests(SimpleTestCase):
    def test_media_path_traversal_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            media_root = f"{temp_dir}/media"
            request = RequestFactory().get("/media-files/../outside.txt")
            with self.settings(MEDIA_ROOT=media_root):
                with self.assertRaises(Http404):
                    ResilientMediaView.as_view()(request, path="../outside.txt")

    def test_markup_media_is_downloaded_instead_of_rendered_inline(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            media_root = f"{temp_dir}/media"
            html_path = f"{media_root}/unsafe.html"

            Path(html_path).parent.mkdir(parents=True, exist_ok=True)
            Path(html_path).write_text("<script>alert(1)</script>", encoding="utf-8")
            with self.settings(MEDIA_ROOT=media_root):
                response = ResilientMediaView.as_view()(
                    RequestFactory().get("/media-files/unsafe.html"),
                    path="unsafe.html",
                )

            self.assertEqual(response.status_code, 200)
            self.assertTrue(response["Content-Disposition"].startswith("attachment;"))
            response.close()


class SecurityHeadersTests(SimpleTestCase):
    def test_content_security_policy_is_present(self):
        request = RequestFactory().get("/")
        response = SecurityHeadersMiddleware(lambda request: HttpResponse("ok"))(request)

        self.assertIn("default-src 'self'", response["Content-Security-Policy"])
