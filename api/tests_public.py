from __future__ import annotations

from django.urls import reverse

from home.models import (
    ArticleBlogModel,
    Category,
    CategoryBlog,
    CommentSectionModel,
    Reply,
    Season,
    SeriesModel,
    UserCourse,
)
from api.tests_shared import ApiTestCase


class ApiPublicEndpointTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.category = Category.objects.create(title="Fitness", slug="fitness")
        self.course = SeriesModel.objects.create(
            title="Yoga Basics",
            image="series_courses/yoga.jpg",
            author=self.user,
            language_kinds=self.category,
            free=True,
            description="A beginner yoga course",
            main_price="0",
        )
        season = Season.objects.create(series=self.course, number=1, title="Introduction")
        self.season = season
        self.article_category = CategoryBlog.objects.create(title="Training", slug="training")
        self.article = ArticleBlogModel.objects.create(
            title="Yoga at home",
            slug="yoga-at-home",
            image="articles_blog/article.jpg",
            author=self.user,
            language_kinds=self.article_category,
            reading_time=5,
            article_excerpt="Simple yoga tips",
            article_description="A longer article body",
        )

    def test_course_list_supports_limit_and_filter(self):
        response = self.client.get(reverse("api:series_list") + "?limit=1&free=true")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["limit"], 1)
        self.assertEqual(len(response.json()["data"]["items"]), 1)
        self.assertEqual(response.json()["data"]["items"][0]["id"], self.course.pk)

    def test_course_detail_exposes_seasons_and_public_access(self):
        response = self.client.get(reverse("api:series_detail", kwargs={"pk": self.course.pk}))

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["id"], self.course.pk)
        self.assertTrue(data["access"])
        self.assertEqual(data["seasons"][0]["id"], self.season.pk)

    def test_article_list_and_detail(self):
        listing = self.client.get(reverse("api:article_list") + "?limit=1")
        detail = self.client.get(reverse("api:article_detail", kwargs={"slug": self.article.slug}))

        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.json()["data"]["items"][0]["slug"], self.article.slug)
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["data"]["description"], "A longer article body")

    def test_search_returns_courses_and_rejects_empty_query(self):
        success = self.client.get(reverse("api:search") + "?q=Yoga")
        empty = self.client.get(reverse("api:search") + "?q=")

        self.assertEqual(success.status_code, 200)
        self.assertEqual(success.json()["data"]["items"][0]["id"], self.course.pk)
        self.assertEqual(empty.status_code, 400)
        self.assertEqual(empty.json()["error"]["code"], "request_rejected")

    def test_authenticated_user_can_submit_comment_and_reply_to_active_comment(self):
        comment = self.client.post(
            reverse("api:create_comment", kwargs={"pk": self.course.pk}),
            data={"text": "Great course"},
            **self.headers,
        )

        self.assertEqual(comment.status_code, 201)
        pending = CommentSectionModel.objects.get(pk=comment.json()["data"]["comment"]["id"])
        self.assertFalse(pending.is_active)

        parent = CommentSectionModel.objects.create(
            series=self.course,
            user=self.other_user,
            text="Approved question",
            is_active=True,
            publication_status=CommentSectionModel.PublicationStatus.APPROVED,
        )
        reply = self.client.post(
            reverse(
                "api:create_reply",
                kwargs={"pk": self.course.pk, "comment_id": parent.pk},
            ),
            data={"text": "Helpful answer"},
            **self.headers,
        )

        self.assertEqual(reply.status_code, 201)
        self.assertTrue(Reply.objects.filter(pk=reply.json()["data"]["reply"]["id"], comment=parent).exists())

    def test_free_enrollment_requires_authentication_and_is_idempotent(self):
        unauthenticated = self.client.post(reverse("api:enroll_free", kwargs={"pk": self.course.pk}))
        authenticated = self.client.post(
            reverse("api:enroll_free", kwargs={"pk": self.course.pk}),
            **self.headers,
        )
        repeated = self.client.post(
            reverse("api:enroll_free", kwargs={"pk": self.course.pk}),
            **self.headers,
        )

        self.assertEqual(unauthenticated.status_code, 401)
        self.assertEqual(authenticated.status_code, 200)
        self.assertEqual(repeated.status_code, 200)
        self.assertEqual(UserCourse.objects.filter(user=self.user, series=self.course).count(), 1)
