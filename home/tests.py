from __future__ import annotations

from django.core.exceptions import ValidationError
from django.contrib import admin
from django.test import RequestFactory, SimpleTestCase, TestCase

from home.admin import ArticleBlogImageInline, ArticleBlogLinkInline, ArticleBlogModelAdmin, CommentAdmin
from home.models import ArticleBlogImage, ArticleBlogLink, ArticleBlogModel, Comment
from home.rich_text import sanitize_rich_text
from home.utils import normalize_search_query
from home.validators import normalize_phone_number, validate_phone_number
from home.video_streaming import parse_http_range


class HomeUtilityTests(SimpleTestCase):
    def test_normalize_search_query_normalizes_arabic_characters_and_whitespace(self):
        self.assertEqual(
            normalize_search_query("  \u0643\u064a\u0643  \u0639\u0631\u0628\u064a  "),
            "\u06a9\u06cc\u06a9 \u0639\u0631\u0628\u06cc",
        )

    def test_normalize_phone_number_strips_common_separators(self):
        self.assertEqual(normalize_phone_number("+98 (912) 123-4567"), "989121234567")

    def test_validate_phone_number_rejects_invalid_number(self):
        with self.assertRaises(ValidationError) as context:
            validate_phone_number("12-34")
        self.assertIn("\u0634\u0645\u0627\u0631\u0647 \u062a\u0645\u0627\u0633 \u0645\u0639\u062a\u0628\u0631 \u0646\u06cc\u0633\u062a.", context.exception.messages)


class VideoStreamingTests(SimpleTestCase):
    def test_parse_http_range_supports_standard_byte_range(self):
        self.assertEqual(parse_http_range("bytes=10-19", 100), (10, 19))

    def test_parse_http_range_supports_suffix_byte_range(self):
        self.assertEqual(parse_http_range("bytes=-20", 100), (80, 99))

    def test_parse_http_range_rejects_invalid_range(self):
        self.assertIsNone(parse_http_range("bytes=200-100", 100))


class ArticleContentTests(TestCase):
    def setUp(self):
        from account.models import User

        self.author = User.objects.create(
            fullname="article_author",
            phone="09121112222",
            is_admin=True,
        )
        self.article = ArticleBlogModel.objects.create(
            title="مقاله آزمایشی",
            author=self.author,
            reading_time=4,
            slug="test-article",
            image="articles_blog/cover.jpg",
            article_description="<p><strong>متن مهم</strong></p><script>alert(1)</script>",
        )

    def test_rich_text_sanitizer_keeps_formatting_and_removes_dangerous_markup(self):
        sanitized = sanitize_rich_text(
            '<p><strong>سلام</strong> <a href="https://example.com" onclick="bad()">لینک</a></p>'
            '<script>alert("xss")</script><img src="javascript:bad()">'
        )

        self.assertIn("<strong>سلام</strong>", sanitized)
        self.assertIn('href="https://example.com"', sanitized)
        self.assertNotIn("onclick", sanitized)
        self.assertNotIn("<script", sanitized)
        self.assertNotIn("<img", sanitized)

    def test_article_detail_renders_gallery_links_and_sanitized_rich_content(self):
        ArticleBlogImage.objects.create(
            article=self.article,
            image="articles_blog/gallery/gallery.jpg",
            alt_text="تصویر تمرین",
            caption="نمونه تصویر",
            sort_order=1,
        )
        ArticleBlogLink.objects.create(
            article=self.article,
            label="منبع مقاله",
            url="https://example.com/source",
        )

        response = self.client.get("/article/detail/test-article/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<strong>متن مهم</strong>", html=True)
        self.assertContains(response, "تصویر تمرین")
        self.assertContains(response, "نمونه تصویر")
        self.assertContains(response, "https://example.com/source")
        self.assertNotContains(response, "alert(1)")

    def test_article_links_reject_unsafe_urls(self):
        link = ArticleBlogLink(
            article=self.article,
            label="ناامن",
            url="javascript:alert(1)",
        )

        with self.assertRaises(ValidationError):
            link.full_clean()

    def test_article_admin_exposes_gallery_links_and_rich_text_editor(self):
        admin_instance = ArticleBlogModelAdmin(ArticleBlogModel, admin.site)

        self.assertEqual(admin_instance.inlines, (ArticleBlogImageInline, ArticleBlogLinkInline))
        request = RequestFactory().get("/Mpannel/")
        request.user = self.author
        form = admin_instance.get_form(request, self.article)
        self.assertIn("rich-text-source", form.base_fields["article_description"].widget.attrs["class"])
        self.assertIn("js/article-editor.js", form.base_fields["article_description"].widget.media._js)


class CommentAdminSearchTests(TestCase):
    def setUp(self):
        from account.models import User

        self.user = User.objects.create(
            fullname="کاربر قابل جستجو",
            display_name="کاربر ویژه",
            phone="09125551234",
            email="searchable@example.com",
        )
        self.comment = Comment.objects.create(
            user=self.user,
            name="نام ثبت‌شده",
            email="sender@example.com",
            comment="متن نظر برای آزمایش جستجوی ادمین.",
        )
        self.admin = CommentAdmin(Comment, admin.site)

    def test_comment_admin_search_finds_comments_by_linked_user(self):
        request = RequestFactory().get("/Mpannel/home/comment/", {"q": "09125551234"})
        request.user = self.user

        queryset, distinct = self.admin.get_search_results(request, Comment.objects.all(), "09125551234")

        self.assertTrue(queryset.filter(pk=self.comment.pk).exists())
        self.assertFalse(distinct)

    def test_comment_admin_keeps_user_autocomplete_enabled(self):
        self.assertEqual(self.admin.autocomplete_fields, ("user",))
        self.assertIn("user__fullname", self.admin.search_fields)
