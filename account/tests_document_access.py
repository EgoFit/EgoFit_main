from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from account.admin_forms import AdminClientDocumentForm
from account.models import ClientDocument, User


class ClientDocumentAccessTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(phone="09120000101", fullname="document_user")

    def test_paid_option_creates_free_download_document(self):
        form = AdminClientDocumentForm(
            data={
                "title": "برنامه رایگان",
                "access_type": ["paid"],
                "price": "250000",
            },
            files={"file": SimpleUploadedFile("free.pdf", b"pdf", content_type="application/pdf")},
        )

        self.assertTrue(form.is_valid(), form.errors)
        document = form.save(commit=False)

        self.assertFalse(document.requires_payment)
        self.assertEqual(document.price, 0)

    def test_unpaid_option_requires_and_persists_price(self):
        form = AdminClientDocumentForm(
            data={
                "title": "برنامه پولی",
                "access_type": ["unpaid"],
                "price": "180000",
            },
            files={"file": SimpleUploadedFile("paid.pdf", b"pdf", content_type="application/pdf")},
        )

        self.assertTrue(form.is_valid(), form.errors)
        document = form.save(commit=False)

        self.assertTrue(document.requires_payment)
        self.assertEqual(document.price, 180000)

    def test_unpaid_option_without_price_is_invalid(self):
        form = AdminClientDocumentForm(
            data={"title": "بدون مبلغ", "access_type": ["unpaid"], "price": "0"},
            files={"file": SimpleUploadedFile("missing-price.pdf", b"pdf", content_type="application/pdf")},
        )

        self.assertFalse(form.is_valid())
        self.assertIn("price", form.errors)

    def test_both_access_options_cannot_be_selected(self):
        form = AdminClientDocumentForm(
            data={
                "title": "انتخاب اشتباه",
                "access_type": ["paid", "unpaid"],
                "price": "180000",
            },
            files={"file": SimpleUploadedFile("both.pdf", b"pdf", content_type="application/pdf")},
        )

        self.assertFalse(form.is_valid())
        self.assertIn("access_type", form.errors)
